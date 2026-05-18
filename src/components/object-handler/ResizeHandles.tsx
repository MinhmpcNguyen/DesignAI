"use client";

import { useRef, useState, useCallback, useMemo, useLayoutEffect } from "react";
import { ThreeEvent, useThree } from "@react-three/fiber";
import { Euler, Quaternion, Vector3 } from "three";
import {
  useResizeAndRepositionLive,
  useCommitResizeAfterDrag,
} from "@/states/slices/objects/hooks";
import { objectInteractionFlag } from "@/states/objectInteractionFlag";

interface ResizeHandlesProps {
  id: string;
  position: [number, number, number];
  rotation: [number, number, number, number];
  size: [number, number, number];
  is2D: boolean;
  placementType?: "floor" | "wall" | "ceiling";
  onDragStart?: () => void;
  onDragEnd?: () => void;
}

/**
 * Normalized corner offsets (±1 in each axis).
 * Index encodes sign bits: bit0 = X, bit1 = Y, bit2 = Z.
 */
const CORNER_OFFSETS: [number, number, number][] = [
  [-1, -1, -1], // 0
  [+1, -1, -1], // 1
  [-1, +1, -1], // 2
  [+1, +1, -1], // 3
  [-1, -1, +1], // 4
  [+1, -1, +1], // 5
  [-1, +1, +1], // 6
  [+1, +1, +1], // 7
];

/** Minimum visual half-extent so handles on tiny objects are still grabbable. */
const MIN_VISUAL_HALF = 0.15;
/** Minimum allowed size per axis (meters). */
const MIN_SIZE = 0.05;
/** Sphere handle radius. */
const HANDLE_RADIUS = 0.07;
/** Large invisible plane for drag capture. */
const DRAG_PLANE_SIZE = 2000;

/** Flip all three axis-sign bits to get the diagonally opposite corner index. */
const opposite = (i: number) => i ^ 7;

/**
 * Draggable corner handles that resize the selected object.
 *
 * Math:
 *   - At pointer-down, the OPPOSITE anchor corner is recorded in both world space
 *     and local space. These are fixed for the entire drag.
 *   - On each pointer-move, the drag point D (world space, from e.point on the
 *     invisible capture plane) is mapped into object-local space:
 *       D_local = Q_inv * (D - A_world) + A_local
 *   - New half-sizes and new world center are derived from A_local and D_local.
 *   - The object's rotation Q never changes — only size and position.
 *
 * Axis locking:
 *   - 2D mode: Y axis locked (only XZ resize).
 *   - Wall objects: Z (depth) locked to preserve mount depth.
 *
 * Tiny-object handling:
 *   - Handle positions use max(halfSize, MIN_VISUAL_HALF) for display only,
 *     so handles are always grabbable regardless of how small the object is.
 */
export default function ResizeHandles({
  id,
  position,
  rotation,
  size,
  is2D,
  placementType,
  onDragStart,
  onDragEnd,
}: ResizeHandlesProps) {
  const resizeLive = useResizeAndRepositionLive();
  const commitResize = useCommitResizeAfterDrag();
  // Get the R3F store's `get` function — called inside event handlers to
  // access OrbitControls imperatively without triggering the React compiler's
  // "cannot mutate hook return value" restriction.
  const getThree = useThree((state) => state.get);

  // Per-drag state stored in refs — avoids stale closures in event handlers.
  const activeHandleRef = useRef<number | null>(null);
  /** World-space position of the anchor (opposite) corner — fixed during drag. */
  const anchorWorldRef = useRef(new Vector3());
  /** Local-space position of the anchor corner — fixed during drag. */
  const anchorLocalRef = useRef(new Vector3());
  /** Center and orientation of the drag-capture plane — state for JSX. */
  const [dragPlaneCenter, setDragPlaneCenter] = useState<
    [number, number, number]
  >([0, 0, 0]);
  const [dragPlaneQuat, setDragPlaneQuat] = useState(() => new Quaternion());

  // Live size/position refs so every drag frame has up-to-date values
  // without waiting for Redux → prop roundtrip.
  const liveSizeRef = useRef<[number, number, number]>([...size]);
  const livePosRef = useRef<[number, number, number]>([...position]);

  const [hoveredHandle, setHoveredHandle] = useState<number | null>(null);
  const [isDragging, setIsDragging] = useState(false);

  // Sync refs from props only when not dragging (during drag the refs are
  // updated manually in handlePointerMove and must not be overwritten).
  useLayoutEffect(() => {
    if (!isDragging) {
      liveSizeRef.current = [...size];
      livePosRef.current = [...position];
    }
  });

  const objectQuat = useMemo(
    () => new Quaternion(rotation[0], rotation[1], rotation[2], rotation[3]),
    [rotation],
  );

  // In 2D top-down view only show 4 bottom-Y corners (y sign = -1, indices 0,1,4,5).
  const visibleCornerIndices = useMemo(
    () => (is2D ? [0, 1, 4, 5] : [0, 1, 2, 3, 4, 5, 6, 7]),
    [is2D],
  );

  /** World-space position of a corner handle, pushing handles outward for tiny objects. */
  const cornerWorldPos = useCallback(
    (
      cornerIndex: number,
      currentSize: [number, number, number],
      currentPos: [number, number, number],
      q: Quaternion,
    ): Vector3 => {
      const [cx, cy, cz] = CORNER_OFFSETS[cornerIndex];
      const [w, h, d] = currentSize;
      // Visual: push handle outward at least MIN_VISUAL_HALF from center.
      const local = new Vector3(
        Math.max(w / 2, MIN_VISUAL_HALF) * cx,
        Math.max(h / 2, MIN_VISUAL_HALF) * cy,
        Math.max(d / 2, MIN_VISUAL_HALF) * cz,
      ).applyQuaternion(q);
      return local.add(new Vector3(...currentPos));
    },
    [],
  );

  const handlePointerDown = useCallback(
    (cornerIndex: number, e: ThreeEvent<PointerEvent>) => {
      e.stopPropagation();
      const orbitControls = getThree().controls as { enabled: boolean } | null;
      if (orbitControls) orbitControls.enabled = false;
      objectInteractionFlag.active = true;
      onDragStart?.();

      activeHandleRef.current = cornerIndex;

      // Anchor = the diagonally OPPOSITE corner, fixed in both local and world space.
      const oppIdx = opposite(cornerIndex);
      const [cx, cy, cz] = CORNER_OFFSETS[oppIdx];
      const [w, h, d] = liveSizeRef.current;
      const [px, py, pz] = livePosRef.current;

      const aLocal = new Vector3((w / 2) * cx, (h / 2) * cy, (d / 2) * cz);
      anchorLocalRef.current.copy(aLocal);

      const aWorld = aLocal
        .clone()
        .applyQuaternion(objectQuat)
        .add(new Vector3(px, py, pz));
      anchorWorldRef.current.copy(aWorld);

      // Grabbed corner world position — used as the plane's center.
      const [gcx, gcy, gcz] = CORNER_OFFSETS[cornerIndex];
      const grabbedWorld = new Vector3(
        (w / 2) * gcx,
        (h / 2) * gcy,
        (d / 2) * gcz,
      )
        .applyQuaternion(objectQuat)
        .add(new Vector3(px, py, pz));

      if (is2D) {
        // Horizontal XZ plane in 2D — Y is locked anyway in handlePointerMove.
        setDragPlaneCenter([px, py, pz]);
        setDragPlaneQuat(
          new Quaternion().setFromEuler(new Euler(-Math.PI / 2, 0, 0)),
        );
      } else {
        // Camera-facing plane so dragging maps to all 3 axes including Y.
        const camera = getThree().camera;
        const normal = camera.position.clone().sub(grabbedWorld).normalize();
        setDragPlaneCenter([grabbedWorld.x, grabbedWorld.y, grabbedWorld.z]);
        setDragPlaneQuat(
          new Quaternion().setFromUnitVectors(new Vector3(0, 0, 1), normal),
        );
      }
      setIsDragging(true);
      (e.target as HTMLElement).setPointerCapture?.(e.pointerId);
    },
    [getThree, is2D, objectQuat, onDragStart],
  );

  const handlePointerMove = useCallback(
    (e: ThreeEvent<PointerEvent>) => {
      if (activeHandleRef.current === null) return;
      e.stopPropagation();

      const D = e.point; // world-space drag point
      const A_world = anchorWorldRef.current; // fixed anchor world pos
      const A_local = anchorLocalRef.current; // fixed anchor local pos
      const invQ = objectQuat.clone().invert();

      // Derive the stable object center from the fixed anchor:
      // C = A_world - Q * A_local
      const C = A_world.clone().sub(
        A_local.clone().applyQuaternion(objectQuat),
      );

      // Dragged corner in local space:
      // D_local = Q_inv * (D - A_world) + A_local
      const D_local = D.clone().sub(A_world).applyQuaternion(invQ).add(A_local);

      // Lock axes that must not change.
      if (is2D) D_local.y = -A_local.y; // keep Y size unchanged
      if (placementType === "wall") D_local.z = -A_local.z; // keep depth unchanged

      // New half-sizes (always positive, minimum clamped).
      const newHalfX = Math.max(
        MIN_SIZE / 2,
        Math.abs(D_local.x - A_local.x) / 2,
      );
      const newHalfY = Math.max(
        MIN_SIZE / 2,
        Math.abs(D_local.y - A_local.y) / 2,
      );
      const newHalfZ = Math.max(
        MIN_SIZE / 2,
        Math.abs(D_local.z - A_local.z) / 2,
      );
      const newSize: [number, number, number] = [
        newHalfX * 2,
        newHalfY * 2,
        newHalfZ * 2,
      ];

      // New object center in world space:
      // local center offset = midpoint of anchor and drag corners in local space.
      const centerOffset = new Vector3(
        (D_local.x + A_local.x) / 2,
        (D_local.y + A_local.y) / 2,
        (D_local.z + A_local.z) / 2,
      );
      const newCenterWorld = C.clone().add(
        centerOffset.applyQuaternion(objectQuat),
      );
      const newPos: [number, number, number] = [
        newCenterWorld.x,
        newCenterWorld.y,
        newCenterWorld.z,
      ];

      // Update live refs so next frame's cornerWorldPos renders correctly.
      liveSizeRef.current = newSize;
      livePosRef.current = newPos;

      resizeLive({ id, size: newSize, position: newPos });
    },
    [id, is2D, objectQuat, placementType, resizeLive],
  );

  const handlePointerUp = useCallback(
    (e: ThreeEvent<PointerEvent>) => {
      if (activeHandleRef.current === null) return;
      e.stopPropagation();

      commitResize({
        id,
        size: liveSizeRef.current,
        position: livePosRef.current,
      });

      activeHandleRef.current = null;
      setIsDragging(false);
      const orbitControls = getThree().controls as { enabled: boolean } | null;
      if (orbitControls) orbitControls.enabled = true;
      objectInteractionFlag.active = false;
      onDragEnd?.();
    },
    [id, commitResize, getThree, onDragEnd],
  );

  return (
    <group>
      {/* Invisible drag-capture plane — only active during a drag.
          Floor/ceiling: horizontal XZ plane. Wall: vertical plane. */}
      {isDragging && (
        <mesh
          position={dragPlaneCenter}
          quaternion={dragPlaneQuat}
          onPointerMove={handlePointerMove}
          onPointerUp={handlePointerUp}
          visible={false}
        >
          <planeGeometry args={[DRAG_PLANE_SIZE, DRAG_PLANE_SIZE]} />
          <meshBasicMaterial />
        </mesh>
      )}

      {/* Corner sphere handles */}
      {visibleCornerIndices.map((cornerIndex) => {
        const worldPos = cornerWorldPos(
          cornerIndex,
          size,
          position,
          objectQuat,
        );
        const isHovered = hoveredHandle === cornerIndex;

        return (
          <mesh
            key={cornerIndex}
            position={[worldPos.x, worldPos.y, worldPos.z]}
            onPointerDown={(e) => handlePointerDown(cornerIndex, e)}
            onPointerEnter={(e) => {
              e.stopPropagation();
              setHoveredHandle(cornerIndex);
              document.body.style.cursor = "grab";
            }}
            onPointerLeave={(e) => {
              e.stopPropagation();
              setHoveredHandle(null);
              document.body.style.cursor = "";
            }}
            renderOrder={999}
          >
            <sphereGeometry args={[HANDLE_RADIUS, 12, 8]} />
            <meshBasicMaterial
              color={isHovered ? "#60a5fa" : "#3b82f6"}
              depthTest={false}
              transparent
              opacity={0.9}
            />
          </mesh>
        );
      })}
    </group>
  );
}
