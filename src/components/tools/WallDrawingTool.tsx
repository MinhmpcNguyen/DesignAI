"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { useThree } from "@react-three/fiber";
import { Html, Line } from "@react-three/drei";
import { useViewMode } from "@/states/slices/view/hooks";
import { useWalls, useAddWall } from "@/states/slices/walls/hooks";
import {
  useIsWallEditMode,
  useIsDrawing,
  useDrawingStartPoint,
  useStartDrawingWall,
  useCancelDrawingWall,
  useWallDefaults,
} from "@/states/slices/wallEditor/hooks";
import { Plane, Raycaster, Vector2, Vector3 } from "three";

/**
 * Wall Drawing Tool
 *
 * Handles drawing new walls in 2D mode:
 * - Click to place start point
 * - Click again to place end point and create wall
 * - Shows ghost line preview while drawing
 * - ESC to cancel
 * - Snaps to nearby endpoints and grid
 */
export default function WallDrawingTool() {
  const viewMode = useViewMode();
  const walls = useWalls();
  const isWallEditMode = useIsWallEditMode();
  const isDrawing = useIsDrawing();
  const drawingStartPoint = useDrawingStartPoint();
  const startDrawingWall = useStartDrawingWall();
  const cancelDrawingWall = useCancelDrawingWall();
  const addWall = useAddWall();
  const wallDefaults = useWallDefaults();

  const [currentMousePos, setCurrentMousePos] = useState<
    [number, number] | null
  >(null);
  const is2D = viewMode === "2D";

  const { camera, gl } = useThree();
  const raycasterRef = useRef(new Raycaster());
  const ndcRef = useRef(new Vector2());

  // Floor plane at y=0 for wall placement
  const floorPlaneRef = useRef(new Plane(new Vector3(0, 1, 0), 0));

  /**
   * Convert screen coordinates to world coordinates using raycasting
   */
  const screenToWorld = useCallback(
    (clientX: number, clientY: number): [number, number] | null => {
      const raycaster = raycasterRef.current;
      const ndc = ndcRef.current;
      const canvas = gl.domElement;
      const rect = canvas.getBoundingClientRect();

      // Convert screen coordinates to normalized device coordinates
      ndc.x = ((clientX - rect.left) / rect.width) * 2 - 1;
      ndc.y = -((clientY - rect.top) / rect.height) * 2 + 1;

      raycaster.setFromCamera(ndc, camera);
      const intersection = new Vector3();
      const hit = raycaster.ray.intersectPlane(
        floorPlaneRef.current,
        intersection,
      );

      if (!hit) return null;

      return [hit.x, hit.z];
    },
    [camera, gl],
  );

  /**
   * Snap point to grid (0.5m grid)
   */
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

  /**
   * Find nearest wall endpoint within snap threshold
   */
  const findNearestEndpoint = useCallback(
    (
      point: [number, number],
      threshold: number = 0.2,
    ): [number, number] | null => {
      let nearest: [number, number] | null = null;
      let minDist = threshold;

      for (const wall of walls) {
        // Check start point
        const distToStart = Math.hypot(
          point[0] - wall.startPoint[0],
          point[1] - wall.startPoint[1],
        );
        if (distToStart < minDist) {
          minDist = distToStart;
          nearest = wall.startPoint;
        }

        // Check end point
        const distToEnd = Math.hypot(
          point[0] - wall.endPoint[0],
          point[1] - wall.endPoint[1],
        );
        if (distToEnd < minDist) {
          minDist = distToEnd;
          nearest = wall.endPoint;
        }
      }

      return nearest;
    },
    [walls],
  );

  /**
   * Get snapped position (priority: endpoint > grid)
   */
  const getSnappedPosition = useCallback(
    (rawPos: [number, number]): [number, number] => {
      // First try to snap to endpoint
      const endpointSnap = findNearestEndpoint(rawPos);
      if (endpointSnap) return endpointSnap;

      // Otherwise snap to grid
      return snapToGrid(rawPos);
    },
    [findNearestEndpoint, snapToGrid],
  );

  /**
   * Handle mouse move - track cursor for ghost line
   */
  const handlePointerMove = useCallback(
    (e: PointerEvent) => {
      if (!is2D || !isWallEditMode || !isDrawing) return;

      const rawPos = screenToWorld(e.clientX, e.clientY);
      if (!rawPos) return;

      const snappedPos = getSnappedPosition(rawPos);
      setCurrentMousePos(snappedPos);
    },
    [is2D, isWallEditMode, isDrawing, screenToWorld, getSnappedPosition],
  );

  /**
   * Handle floor click - place wall points
   */
  const handleFloorClick = useCallback(
    (e: MouseEvent) => {
      if (!is2D || !isWallEditMode) return;

      // Ignore if clicking on UI elements
      const target = e.target as HTMLElement;
      if (target.tagName === "BUTTON" || target.closest("button")) {
        return;
      }

      const rawPos = screenToWorld(e.clientX, e.clientY);
      if (!rawPos) return;

      const snappedPos = getSnappedPosition(rawPos);

      if (!isDrawing) {
        // Not in drawing mode - do nothing (user must click "Draw Wall" button first)
        return;
      }

      // Check if this is first click (start point is dummy [0,0]) or has not been properly set
      const isFirstClick =
        !drawingStartPoint ||
        (drawingStartPoint[0] === 0 && drawingStartPoint[1] === 0);

      if (isFirstClick) {
        // First click - set start point
        startDrawingWall(snappedPos);
      } else {
        // Second click - complete wall
        const [sx, sz] = drawingStartPoint;
        const [ex, ez] = snappedPos;

        // Don't create zero-length walls
        if (Math.abs(sx - ex) < 0.01 && Math.abs(sz - ez) < 0.01) return;

        // Create new wall with generated ID
        const newWallId = `wall-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
        addWall({
          id: newWallId,
          startPoint: [sx, sz],
          endPoint: [ex, ez],
          thickness: wallDefaults.thickness,
          height: wallDefaults.height,
          color: "#cccccc",
        });

        // Immediately start next wall from the endpoint just placed
        startDrawingWall(snappedPos);
      }
    },
    [
      is2D,
      isWallEditMode,
      isDrawing,
      drawingStartPoint,
      screenToWorld,
      getSnappedPosition,
      startDrawingWall,
      addWall,
      wallDefaults,
    ],
  );

  /**
   * Handle ESC key - cancel drawing
   */
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isDrawing) {
        cancelDrawingWall();
        setCurrentMousePos(null);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isDrawing, cancelDrawingWall]);

  // // Ensure any transient preview markers are cleared immediately when
  // // leaving wall-draw context (ESC, mode switch, or view switch).
  // useEffect(() => {
  //   if (!is2D || !isWallEditMode || !isDrawing) {
  //     setCurrentMousePos(null);
  //   }
  // }, [is2D, isWallEditMode, isDrawing]);

  /**
   * Attach global mouse event listeners
   */
  useEffect(() => {
    if (is2D && isWallEditMode) {
      window.addEventListener("pointermove", handlePointerMove);
      window.addEventListener("click", handleFloorClick);
      return () => {
        window.removeEventListener("pointermove", handlePointerMove);
        window.removeEventListener("click", handleFloorClick);
      };
    }
  }, [is2D, isWallEditMode, handlePointerMove, handleFloorClick]);

  // Only render ghost line if we have a valid start point (not the dummy [0,0])
  const hasValidStartPoint =
    drawingStartPoint &&
    !(drawingStartPoint[0] === 0 && drawingStartPoint[1] === 0);

  // Only render in 2D wall edit mode while drawing with valid start point
  if (
    !is2D ||
    !isWallEditMode ||
    !isDrawing ||
    !hasValidStartPoint ||
    !currentMousePos
  ) {
    return null;
  }

  // Ghost line from start to current mouse position
  const startPoint3D: [number, number, number] = [
    drawingStartPoint[0],
    0.1,
    drawingStartPoint[1],
  ];
  const endPoint3D: [number, number, number] = [
    currentMousePos[0],
    0.1,
    currentMousePos[1],
  ];

  // Length label calculations (mirrors Walls.tsx)
  const [sx, sz] = drawingStartPoint;
  const [ex, ez] = currentMousePos;
  const ghostLength = Math.sqrt((ex - sx) ** 2 + (ez - sz) ** 2);
  const centerX = (sx + ex) / 2;
  const centerZ = (sz + ez) / 2;
  const perpX = ghostLength > 0 ? (-(ez - sz) / ghostLength) * 0.5 : 0;
  const perpZ = ghostLength > 0 ? ((ex - sx) / ghostLength) * 0.5 : 0;
  let labelAngleDeg = Math.atan2(ez - sz, ex - sx) * (180 / Math.PI);
  if (labelAngleDeg > 90) labelAngleDeg -= 180;
  if (labelAngleDeg < -90) labelAngleDeg += 180;

  return (
    <>
      {/* Ghost line preview */}
      <Line
        points={[startPoint3D, endPoint3D]}
        color="#00ff00"
        lineWidth={3}
        dashed
        dashScale={10}
        dashSize={0.3}
        gapSize={0.2}
      />

      {/* Start point indicator - GREEN SPHERE */}
      <mesh position={startPoint3D}>
        <sphereGeometry args={[0.15, 16, 16]} />
        <meshBasicMaterial color="#00ff00" />
      </mesh>

      {/* End point indicator - GREEN SPHERE (follows mouse) */}
      <mesh position={endPoint3D}>
        <sphereGeometry args={[0.15, 16, 16]} />
        <meshBasicMaterial color="#00ff00" transparent opacity={0.7} />
      </mesh>

      {/* Live length label */}
      {ghostLength > 0.01 && (
        <Html
          position={[centerX + perpX, 0.1, centerZ + perpZ]}
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
            {Math.round(ghostLength * 1000)}mm
          </div>
        </Html>
      )}
    </>
  );
}
