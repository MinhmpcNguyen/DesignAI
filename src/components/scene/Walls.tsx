"use client";

import { memo, useState, useEffect, useCallback, useMemo, useRef } from "react";
import { Html } from "@react-three/drei";
import { useThree } from "@react-three/fiber";
import { useViewMode } from "@/states/slices/view/hooks";
import {
  useWalls,
  useUpdateWall,
  useUpdateManyWalls,
  useBeginWallEdit,
} from "@/states/slices/walls/hooks";
import {
  useIsWallEditMode,
  useSelectedWallId,
  useSelectWall,
} from "@/states/slices/wallEditor/hooks";
import type { ThreeEvent } from "@react-three/fiber";
import type { Wall } from "@/states/slices/walls/types";
import { useObjectsValue } from "@/states/slices/objects/hooks";
import {
  buildWallSubMeshes,
  collectDoorIntervalsFromS,
  intervalsToLocalX,
} from "@/lib/wallOpenings";
import {
  MeshStandardMaterial,
  Plane,
  Raycaster,
  Vector2,
  Vector3,
} from "three";

interface WallMeshProps {
  wall: Wall;
  is2D: boolean;
  isEditable: boolean;
  isSelected: boolean;
  onWallClick: (e: ThreeEvent<MouseEvent>, wallId: string) => void;
  onMidpointPointerDown: (e: ThreeEvent<PointerEvent>, wallId: string) => void;
  onEndpointPointerDown: (
    e: ThreeEvent<PointerEvent>,
    wallId: string,
    endpoint: "start" | "end",
  ) => void;
}

const WallMesh = memo(function WallMesh({
  wall,
  is2D,
  isEditable,
  isSelected,
  onWallClick,
  onMidpointPointerDown,
  onEndpointPointerDown,
}: WallMeshProps) {
  const { objects } = useObjectsValue();
  const [sx, sz] = wall.startPoint;
  const [ex, ez] = wall.endPoint;
  const centerX = (sx + ex) / 2;
  const centerZ = (sz + ez) / 2;
  const length = Math.sqrt((ex - sx) ** 2 + (ez - sz) ** 2);
  const angle = -Math.atan2(ez - sz, ex - sx);
  const perpX = length > 0 ? (-(ez - sz) / length) * 0.5 : 0;
  const perpZ = length > 0 ? ((ex - sx) / length) * 0.5 : 0;
  let labelAngleDeg = Math.atan2(ez - sz, ex - sx) * (180 / Math.PI);
  if (labelAngleDeg > 90) labelAngleDeg -= 180;
  if (labelAngleDeg < -90) labelAngleDeg += 180;

  const wallColor = isSelected && isEditable ? "#4a90e2" : wall.color;
  const topColor = "#494949";

  const subMeshes = useMemo(() => {
    if (length < 1e-6) return [];
    const raw = collectDoorIntervalsFromS(wall, objects);
    const intervals = intervalsToLocalX(raw, length);
    return buildWallSubMeshes(length, wall.height, wall.thickness, intervals);
  }, [wall, objects, length]);

  // Materials created once per wallColor change — not on every parent render
  const materials3D = useMemo(() => {
    const sideMat = new MeshStandardMaterial({ color: wallColor });
    const topMat = new MeshStandardMaterial({ color: topColor });
    return [sideMat, sideMat, topMat, sideMat, sideMat, sideMat];
  }, [wallColor]);

  // Dispose GPU memory when wallColor changes or the wall is removed
  useEffect(() => {
    return () => {
      (materials3D[0] as MeshStandardMaterial).dispose();
      (materials3D[2] as MeshStandardMaterial).dispose();
    };
  }, [materials3D]);

  const wallKey = `${length.toFixed(4)}-${wall.height}-${wall.thickness}-${subMeshes.length}`;
  // One box → outline helps read the mass. Several boxes (door cutout) → per-segment

  return (
    <group>
      <group
        position={[centerX, wall.height / 2, centerZ]}
        rotation={[0, angle, 0]}
      >
        {subMeshes.map((sm, i) => (
          <mesh
            key={`${wallKey}-${i}`}
            position={sm.position}
            castShadow={!is2D}
            material={is2D ? undefined : materials3D}
            onClick={(e) => onWallClick(e, wall.id)}
            onPointerDown={(e) => onMidpointPointerDown(e, wall.id)}
          >
            <boxGeometry args={sm.size} />
            {is2D && <meshBasicMaterial color={topColor} />}
          </mesh>
        ))}
      </group>

      {is2D && (
        <Html
          position={[centerX + perpX, 0, centerZ + perpZ]}
          center
          zIndexRange={[40, 0]}
        >
          <div
            style={{
              transform: `rotate(${labelAngleDeg}deg)`,
              textShadow: "0 0 4px rgba(0,0,0,0.85)",
            }}
            className="text-[11px] font-semibold text-white whitespace-nowrap pointer-events-none select-none"
          >
            {Math.round(length * 1000)}mm
          </div>
        </Html>
      )}

      {isEditable && isSelected && (
        <>
          <mesh
            position={[sx, 0.1, sz]}
            onPointerDown={(e) => onEndpointPointerDown(e, wall.id, "start")}
          >
            <sphereGeometry args={[0.5, 16, 16]} />
            <meshBasicMaterial color="#ff6b6b" />
          </mesh>
          <mesh
            position={[ex, 0.1, ez]}
            onPointerDown={(e) => onEndpointPointerDown(e, wall.id, "end")}
          >
            <sphereGeometry args={[0.5, 16, 16]} />
            <meshBasicMaterial color="#ff6b6b" />
          </mesh>
        </>
      )}
    </group>
  );
});

/**
 * Room boundary walls component
 * Renders walls from Redux state (dynamically editable)
 * Shows dimension labels in 2D mode
 * In wall edit mode (2D only): walls are selectable and draggable
 */
export default function Walls() {
  const viewMode = useViewMode();
  const walls = useWalls();
  // Log walls as pretty JSON for easier inspection in consoles
  const isWallEditMode = useIsWallEditMode();
  const selectedWallId = useSelectedWallId();
  const selectWall = useSelectWall();
  const updateWall = useUpdateWall();
  const updateManyWalls = useUpdateManyWalls();
  const beginWallEdit = useBeginWallEdit();
  const is2D = viewMode === "2D";

  const [draggingWall, setDraggingWall] = useState<{
    wallId: string;
    isMidpoint: boolean;
    isStartPoint: boolean;
    startMouse: [number, number];
    startWorldPos: [number, number] | null;
    startPoints: { start: [number, number]; end: [number, number] };
    /** Other walls sharing the dragged endpoint, computed once at drag start */
    connectedEndpoints: Array<{ wallId: string; endpoint: "start" | "end" }>;
  } | null>(null);

  const { camera, gl } = useThree();

  // Raycasting for accurate screen-to-world conversion
  const raycasterRef = useRef(new Raycaster());
  const ndcRef = useRef(new Vector2());
  const floorPlaneRef = useRef(new Plane(new Vector3(0, 1, 0), 0));
  const intersectionRef = useRef(new Vector3());

  const screenToWorld = useCallback(
    (clientX: number, clientY: number): [number, number] | null => {
      const rect = gl.domElement.getBoundingClientRect();
      ndcRef.current.x = ((clientX - rect.left) / rect.width) * 2 - 1;
      ndcRef.current.y = -((clientY - rect.top) / rect.height) * 2 + 1;
      raycasterRef.current.setFromCamera(ndcRef.current, camera);
      const hit = raycasterRef.current.ray.intersectPlane(
        floorPlaneRef.current,
        intersectionRef.current,
      );
      return hit ? [hit.x, hit.z] : null;
    },
    [camera, gl],
  );

  const snapToGrid = useCallback(
    (point: [number, number]): [number, number] => {
      const gridSize = 0.1;
      return [
        Math.round(point[0] / gridSize) * gridSize,
        Math.round(point[1] / gridSize) * gridSize,
      ];
    },
    [],
  );

  // Find nearest wall endpoint within threshold, excluding all endpoints of the wall being dragged
  const findNearestEndpoint = useCallback(
    (
      point: [number, number],
      excludeWallId?: string,
      threshold = 0.2,
    ): [number, number] | null => {
      let nearest: [number, number] | null = null;
      let minDist = threshold;
      for (const wall of walls) {
        // Skip the entire wall being edited — snapping to its own endpoints
        // would collapse it to zero length.
        if (wall.id === excludeWallId) continue;
        const ds = Math.hypot(
          point[0] - wall.startPoint[0],
          point[1] - wall.startPoint[1],
        );
        if (ds < minDist) {
          minDist = ds;
          nearest = wall.startPoint;
        }
        const de = Math.hypot(
          point[0] - wall.endPoint[0],
          point[1] - wall.endPoint[1],
        );
        if (de < minDist) {
          minDist = de;
          nearest = wall.endPoint;
        }
      }
      return nearest;
    },
    [walls],
  );

  const getSnappedPosition = useCallback(
    (rawPos: [number, number], excludeWallId?: string): [number, number] => {
      return findNearestEndpoint(rawPos, excludeWallId) ?? snapToGrid(rawPos);
    },
    [findNearestEndpoint, snapToGrid],
  );

  // Handle wall click - select wall in edit mode
  const handleWallClick = useCallback(
    (e: ThreeEvent<MouseEvent>, wallId: string) => {
      if (!is2D || !isWallEditMode) return;
      e.stopPropagation();
      selectWall(wallId);
    },
    [is2D, isWallEditMode, selectWall],
  );

  // Handle endpoint drag start
  const handleEndpointPointerDown = useCallback(
    (
      e: ThreeEvent<PointerEvent>,
      wallId: string,
      endpoint: "start" | "end",
    ) => {
      if (!is2D || !isWallEditMode) return;
      e.stopPropagation();

      const wall = walls.find((w) => w.id === wallId);
      if (!wall) return;

      const isStartPoint = endpoint === "start";
      const originalEndpoint = isStartPoint ? wall.startPoint : wall.endPoint;

      // Find every other wall whose startPoint or endPoint coincides with the
      // dragged endpoint. These will move together to keep rooms sealed.
      const COORD_EPS = 1e-4;
      const connectedEndpoints: Array<{
        wallId: string;
        endpoint: "start" | "end";
      }> = [];
      for (const w of walls) {
        if (w.id === wallId) continue;
        if (
          Math.abs(w.startPoint[0] - originalEndpoint[0]) < COORD_EPS &&
          Math.abs(w.startPoint[1] - originalEndpoint[1]) < COORD_EPS
        ) {
          connectedEndpoints.push({ wallId: w.id, endpoint: "start" });
        }
        if (
          Math.abs(w.endPoint[0] - originalEndpoint[0]) < COORD_EPS &&
          Math.abs(w.endPoint[1] - originalEndpoint[1]) < COORD_EPS
        ) {
          connectedEndpoints.push({ wallId: w.id, endpoint: "end" });
        }
      }

      beginWallEdit();
      setDraggingWall({
        wallId,
        isMidpoint: false,
        isStartPoint,
        startMouse: [e.clientX, e.clientY],
        startWorldPos: null,
        startPoints: { start: wall.startPoint, end: wall.endPoint },
        connectedEndpoints,
      });
      selectWall(wallId);
    },
    [is2D, isWallEditMode, walls, selectWall, beginWallEdit],
  );

  // Handle midpoint drag start
  const handleMidpointPointerDown = useCallback(
    (e: ThreeEvent<PointerEvent>, wallId: string) => {
      if (!is2D || !isWallEditMode) return;
      e.stopPropagation();

      const wall = walls.find((w) => w.id === wallId);
      if (!wall) return;

      // Capture the world-space position of the mouse at drag start so we can
      // compute a world-space delta in handlePointerMove (avoids pixel-ratio issues).
      const startWorldPos = screenToWorld(e.clientX, e.clientY);

      beginWallEdit();
      setDraggingWall({
        wallId,
        isMidpoint: true,
        isStartPoint: false,
        startMouse: [e.clientX, e.clientY],
        startWorldPos,
        startPoints: { start: wall.startPoint, end: wall.endPoint },
        connectedEndpoints: [],
      });
      selectWall(wallId);
    },
    [is2D, isWallEditMode, walls, screenToWorld, selectWall, beginWallEdit],
  );

  // Handle pointer move - drag endpoints or midpoint
  const handlePointerMove = useCallback(
    (e: PointerEvent) => {
      if (!draggingWall) return;

      if (draggingWall.isMidpoint) {
        // Midpoint drag: compute world-space delta via raycasting so the wall
        // tracks the cursor exactly regardless of zoom or camera changes.
        const currentWorldPos = screenToWorld(e.clientX, e.clientY);
        if (!currentWorldPos || !draggingWall.startWorldPos) return;
        const worldDx = currentWorldPos[0] - draggingWall.startWorldPos[0];
        const worldDz = currentWorldPos[1] - draggingWall.startWorldPos[1];
        const { start, end } = draggingWall.startPoints;
        updateWall(draggingWall.wallId, {
          startPoint: [start[0] + worldDx, start[1] + worldDz],
          endPoint: [end[0] + worldDx, end[1] + worldDz],
        });
      } else {
        // Endpoint drag: raycasting + snapping
        const rawPos = screenToWorld(e.clientX, e.clientY);
        if (!rawPos) return;
        const snappedPos = getSnappedPosition(rawPos, draggingWall.wallId);

        // Batch update: primary wall + every connected wall
        updateManyWalls([
          {
            id: draggingWall.wallId,
            updates: draggingWall.isStartPoint
              ? { startPoint: snappedPos }
              : { endPoint: snappedPos },
          },
          ...draggingWall.connectedEndpoints.map(({ wallId, endpoint }) => ({
            id: wallId,
            updates:
              endpoint === "start"
                ? { startPoint: snappedPos }
                : { endPoint: snappedPos },
          })),
        ]);
      }
    },
    [
      draggingWall,
      updateWall,
      updateManyWalls,
      screenToWorld,
      getSnappedPosition,
    ],
  );

  // Handle pointer up - stop dragging
  const handlePointerUp = useCallback(() => {
    if (draggingWall) {
      setDraggingWall(null);
    }
  }, [draggingWall]);

  // Attach global pointer event listeners for dragging
  useEffect(() => {
    if (draggingWall) {
      window.addEventListener("pointermove", handlePointerMove);
      window.addEventListener("pointerup", handlePointerUp);
      return () => {
        window.removeEventListener("pointermove", handlePointerMove);
        window.removeEventListener("pointerup", handlePointerUp);
      };
    }
  }, [draggingWall, handlePointerMove, handlePointerUp]);

  // Handle cursor changes
  useEffect(() => {
    if (typeof document !== "undefined") {
      document.body.style.cursor = draggingWall ? "grabbing" : "default";
    }
  }, [draggingWall]);

  return (
    <>
      {walls.map((wall) => (
        <WallMesh
          key={wall.id}
          wall={wall}
          is2D={is2D}
          isEditable={is2D && isWallEditMode}
          isSelected={selectedWallId === wall.id}
          onWallClick={handleWallClick}
          onMidpointPointerDown={handleMidpointPointerDown}
          onEndpointPointerDown={handleEndpointPointerDown}
        />
      ))}
    </>
  );
}
