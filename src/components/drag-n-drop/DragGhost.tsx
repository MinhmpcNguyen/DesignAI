"use client";

import { useEffect, useRef, useState, useMemo } from "react";
import { useThree } from "@react-three/fiber";
import {
  useDragValue,
  useSetIsDragging,
  useSetDraggingShape,
} from "@/states/slices/drag/hooks";
import {
  useAddMultipleObjects,
  useAddObject,
  useReplaceAllObjects,
} from "@/states/slices/objects/hooks";
import type { SceneObject } from "@/states/slices/objects/types";
import {
  useCalculateSnap,
  useShowSnapIndicators,
  getFurnitureMetadata,
  type SnapResult,
} from "@/states/slices/snapping";
import SnapIndicator from "../object-handler/SnapIndicator";
import DoorSwingPlanOverlay from "@/components/scene/DoorSwingPlanOverlay";
import { getSnapFurnitureType } from "@/lib/doorModels";
import { useWalls } from "@/states/slices/walls/hooks";
import { Plane, Vector2, Vector3 } from "three";

/** Plane y=1 for drag placement (object center height) */
const DRAG_PLANE = new Plane(new Vector3(0, 1, 0), -1);

/**
 * Shows a ghost preview of the dragged object that follows the mouse cursor.
 * Similar to PasteGhost but for drag-and-drop from the palette.
 * Click or release to place the object at the current position.
 *
 * Snapping integration:
 * - Calculates snap position in real-time during drag
 * - Shows visual snap indicators (floor/wall highlights)
 * - Places object at snapped position on release
 */
export default function DragGhost() {
  const { isDragging, draggingShape } = useDragValue();
  const setIsDragging = useSetIsDragging();
  const setDraggingShape = useSetDraggingShape();
  const addObject = useAddObject();
  const replaceAllObjects = useReplaceAllObjects();
  const walls = useWalls();
  const { camera, gl, raycaster } = useThree();

  // Snapping hooks
  const calculateSnap = useCalculateSnap();
  const showSnapIndicators = useShowSnapIndicators();
  const addMultipleObject = useAddMultipleObjects();

  const [ghostPosition, setGhostPosition] = useState<[number, number, number]>([
    0, 1, 0,
  ]);
  const [snapResult, setSnapResult] = useState<SnapResult | null>(null);
  const intersectionRef = useRef(new Vector3());

  // Ref mirrors snapResult so handleMouseUp always reads the latest value
  // without needing snapResult in the effect dependency array.  Putting
  // mutable intermediate state (ghostPosition, snapResult) in the deps caused
  // the effect to re-run on every mousemove, tearing down and re-adding
  // window listeners each frame — creating a race window where mouseup could
  // be missed and isDragging would stay true indefinitely.
  const snapResultRef = useRef<SnapResult | null>(null);

  useEffect(() => {
    if (!isDragging || !draggingShape) return;

    const handleMouseMove = (event: MouseEvent) => {
      // Convert client coordinates to NDC
      const rect = gl.domElement.getBoundingClientRect();
      const x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
      const y = -((event.clientY - rect.top) / rect.height) * 2 + 1;

      const mouse = new Vector2(x, y);
      raycaster.setFromCamera(mouse, camera);

      const hit = raycaster.ray.intersectPlane(
        DRAG_PLANE,
        intersectionRef.current,
      );

      if (hit) {
        // Raw cursor position.
        // For ceiling objects: Y = ceilingHeight - halfHeight so the ghost immediately
        // appears at the ceiling, matching what calculateSnap will force anyway.
        // For wall opening types (door/window): Y = wallMountHeight + halfHeight so the object
        // sits at the correct height from the first frame (matching the snap result).
        // For other wall objects: start Y at center height (~eye level, min 1.0m).
        // For floor objects: Y = half height so the bottom rests on the floor.
        const snapType = getSnapFurnitureType(
          draggingShape.shape,
          draggingShape.objectRole,
        );
        const snapMeta = getFurnitureMetadata(snapType);
        let initialY: number;
        if (draggingShape.placementType === "ceiling") {
          const ceilingHeight =
            walls.length > 0 ? Math.max(...walls.map((w) => w.height)) : 3;
          initialY = ceilingHeight - draggingShape.size[1] / 2;
        } else if (
          draggingShape.placementType === "wall" &&
          snapMeta?.wallMountHeight != null
        ) {
          initialY = snapMeta.wallMountHeight + draggingShape.size[1] / 2;
        } else if (draggingShape.placementType === "wall") {
          initialY = Math.max(draggingShape.size[1] / 2, 1.0);
        } else {
          initialY = draggingShape.size[1] / 2;
        }
        const cursorPos: [number, number, number] = [hit.x, initialY, hit.z];

        // Calculate snapped position, passing per-item placement override
        const draggingDoor = draggingShape.objectRole === "door";
        const draggingWindow = draggingShape.objectRole === "window";
        const snap = calculateSnap(
          snapType,
          cursorPos,
          draggingShape.size,
          draggingShape.placementType,
          draggingDoor || draggingWindow ? Number.POSITIVE_INFINITY : undefined,
        );

        // Update ref first (synchronous, no re-render) then state (visual)
        snapResultRef.current = snap;
        setSnapResult(snap);
        setGhostPosition(snap.position);
      }
    };

    const handleMouseUp = (event: MouseEvent) => {
      // Check if mouse is over the canvas
      const rect = gl.domElement.getBoundingClientRect();
      const isOverCanvas =
        event.clientX >= rect.left &&
        event.clientX <= rect.right &&
        event.clientY >= rect.top &&
        event.clientY <= rect.bottom;

      // Read from ref — always current even if state update hasn't flushed yet
      const currentSnap = snapResultRef.current;

      const isWallOpeningObject =
        draggingShape.objectRole === "door" ||
        draggingShape.objectRole === "window";
      const skipDoorOffWall =
        isWallOpeningObject && currentSnap?.snappedTo !== "wall";

      if (isOverCanvas && currentSnap) {
        // Collection drop: replace all scene objects with the collection's objects
        // offset so their centroid lands at the drop position.
        if (
          draggingShape.collectionObjects &&
          draggingShape.collectionObjects.length > 0
        ) {
          const colObjs = draggingShape.collectionObjects;
          const centroidX =
            colObjs.reduce((s, o) => s + o.position[0], 0) / colObjs.length;
          const centroidZ =
            colObjs.reduce((s, o) => s + o.position[2], 0) / colObjs.length;
          const dx = currentSnap.position[0] - centroidX;
          const dz = currentSnap.position[2] - centroidZ;
          const placed = colObjs.map((o, i) => ({
            ...o,
            id: `col-${Date.now()}-${i}`,
            position: [
              o.position[0] + dx,
              o.position[1],
              o.position[2] + dz,
            ] as [number, number, number],
          }));
          // TODO: check this later replace all objects vs add multiple objects.  Replace all is simpler and ensures no legacy objects remain, but if we want to support multi-collection drops in the future we'll need addMultipleObject which can append to existing scene objects without wiping them out.
          // replaceAllObjects(placed);
          addMultipleObject(placed);
        } else if (!skipDoorOffWall) {
          // Single-item drop: existing logic
          const newObject: SceneObject = {
            id: `obj-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
            name: draggingShape.name,
            type: draggingShape.shape,
            position: currentSnap.position,
            rotation: currentSnap.rotation ?? [0, 0, 0, 1],
            color: draggingShape.color,
            size: draggingShape.size,
            modelUrl: draggingShape.modelUrl,
            placementType: currentSnap.snappedTo ?? undefined,
            snappedToWall: currentSnap.wallType,
            objectRole: draggingShape.objectRole,
            catalogItemId: draggingShape.catalogItemId,
          };
          addObject(newObject);
        }
      }

      // Exit drag mode
      snapResultRef.current = null;
      setIsDragging(false);
      setDraggingShape(null);
      setSnapResult(null);
    };

    // Handle drag cancel (Escape key)
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        snapResultRef.current = null;
        setIsDragging(false);
        setDraggingShape(null);
        setSnapResult(null);
      }
    };

    window.addEventListener("mousemove", handleMouseMove);
    window.addEventListener("mouseup", handleMouseUp);
    window.addEventListener("keydown", handleKeyDown);

    // Change cursor to indicate drag mode
    document.body.style.cursor = "crosshair";

    return () => {
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("mouseup", handleMouseUp);
      window.removeEventListener("keydown", handleKeyDown);
      document.body.style.cursor = "default";
    };
  }, [
    // ghostPosition and snapResult deliberately excluded:
    // they are intermediate visual state read via snapResultRef, not triggers.
    // Including them caused the effect to re-run every mousemove, creating a
    // listener churn race condition where mouseup could be swallowed.
    isDragging,
    draggingShape,
    camera,
    raycaster,
    gl,
    addObject,
    replaceAllObjects,
    addMultipleObject,
    setIsDragging,
    setDraggingShape,
    calculateSnap,
    walls,
  ]);

  // Memoize geometry to prevent recreation on every render
  const geometry = useMemo(() => {
    if (!draggingShape) return null;
    return <boxGeometry args={draggingShape.size} />;
  }, [draggingShape]);

  // Don't render anything if not in drag mode or no dragging shape
  if (!isDragging || !draggingShape) return null;

  const ghostIsDoor = draggingShape.objectRole === "door";
  const ghostWall =
    snapResult?.snappedTo === "wall" && snapResult.wallType
      ? walls.find((w) => w.id === snapResult.wallType)
      : undefined;

  return (
    <>
      {/* Ghost preview at snapped position */}
      <group position={ghostPosition}>
        <mesh>
          {geometry}
          <meshStandardMaterial
            color={draggingShape.color}
            transparent
            opacity={0.5}
            wireframe
          />
        </mesh>
      </group>

      {ghostIsDoor && ghostWall && snapResult?.snappedTo === "wall" && (
        <DoorSwingPlanOverlay
          wall={ghostWall}
          position={snapResult.position}
          rotation={snapResult.rotation}
          size={draggingShape.size}
        />
      )}

      {/* Snap indicators (visual feedback) */}
      {showSnapIndicators && snapResult && snapResult.snappedTo && (
        <SnapIndicator
          type={snapResult.snappedTo}
          position={snapResult.position}
          isActive={true}
          rotation={snapResult.rotation}
          distance={snapResult.distance}
        />
      )}
    </>
  );
}
