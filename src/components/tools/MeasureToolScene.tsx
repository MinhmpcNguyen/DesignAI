"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { useThree } from "@react-three/fiber";
import { Html, Line } from "@react-three/drei";
import { Plane, Raycaster, Vector2, Vector3 } from "three";
import { useViewMode } from "@/states/slices/view/hooks";
import {
  useIsMeasureActive,
  useMeasurePendingStart,
  useMeasureLines,
  useDeactivateMeasure,
  useSetMeasurePendingStart,
  useCancelMeasurePending,
  useAddMeasureLine,
} from "@/states/slices/measure/hooks";

const GRID_SNAP = 0.1;
const MEASURE_COLOR = "#00ff00"; // green (same as wall drawing tool)

function formatDistance(meters: number): string {
  if (meters < 1) {
    return `${Math.round(meters * 1000)}mm`;
  }
  return `${meters.toFixed(2)}m`;
}

export default function MeasureToolScene() {
  const viewMode = useViewMode();
  const isActive = useIsMeasureActive();
  const pendingStart = useMeasurePendingStart();
  const lines = useMeasureLines();

  const deactivate = useDeactivateMeasure();
  const setPendingStart = useSetMeasurePendingStart();
  const cancelPending = useCancelMeasurePending();
  const addMeasureLine = useAddMeasureLine();

  const { camera, gl } = useThree();

  const [cursorPos, setCursorPos] = useState<[number, number] | null>(null);

  // Refs for stable event handlers without re-registration on every render
  const pendingStartRef = useRef(pendingStart);
  const isActiveRef = useRef(isActive);
  const is2DRef = useRef(viewMode === "2D");

  useEffect(() => {
    pendingStartRef.current = pendingStart;
  }, [pendingStart]);
  useEffect(() => {
    isActiveRef.current = isActive;
  }, [isActive]);
  useEffect(() => {
    is2DRef.current = viewMode === "2D";
  }, [viewMode]);

  const raycasterRef = useRef(new Raycaster());
  const ndcRef = useRef(new Vector2());
  const floorPlaneRef = useRef(new Plane(new Vector3(0, 1, 0), 0));

  const screenToWorld = useCallback(
    (clientX: number, clientY: number): [number, number] | null => {
      const raycaster = raycasterRef.current;
      const ndc = ndcRef.current;
      const canvas = gl.domElement;
      const rect = canvas.getBoundingClientRect();

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

  const snapToGrid = useCallback(
    (point: [number, number]): [number, number] => {
      return [
        Math.round(point[0] / GRID_SNAP) * GRID_SNAP,
        Math.round(point[1] / GRID_SNAP) * GRID_SNAP,
      ];
    },
    [],
  );

  // Pointer move — update ghost cursor
  const handlePointerMove = useCallback(
    (e: PointerEvent) => {
      if (!isActiveRef.current || !is2DRef.current) return;
      const raw = screenToWorld(e.clientX, e.clientY);
      if (!raw) return;
      setCursorPos(snapToGrid(raw));
    },
    [screenToWorld, snapToGrid],
  );

  // Click — place start or complete a line
  const handleClick = useCallback(
    (e: MouseEvent) => {
      if (!isActiveRef.current || !is2DRef.current) return;

      // Ignore clicks on toolbar/UI elements
      const target = e.target as HTMLElement;
      if (target.tagName === "BUTTON" || target.closest("button")) return;

      const raw = screenToWorld(e.clientX, e.clientY);
      if (!raw) return;
      const snapped = snapToGrid(raw);

      const current = pendingStartRef.current;
      if (!current) {
        // First click — set start
        setPendingStart(snapped);
      } else {
        // Second click — complete line if not zero-length
        const dist = Math.hypot(
          snapped[0] - current[0],
          snapped[1] - current[1],
        );
        if (dist < 0.01) {
          cancelPending();
          return;
        }
        addMeasureLine({
          id: `m-${Date.now()}`,
          start: current,
          end: snapped,
        });
      }
    },
    [screenToWorld, snapToGrid, setPendingStart, cancelPending, addMeasureLine],
  );

  // ESC — cancel pending or deactivate
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key !== "Escape" || !isActiveRef.current) return;
      if (pendingStartRef.current) {
        cancelPending();
        setCursorPos(null);
      } else {
        deactivate();
        setCursorPos(null);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [cancelPending, deactivate]);

  // Attach/detach mouse event listeners
  useEffect(() => {
    if (isActive && viewMode === "2D") {
      window.addEventListener("pointermove", handlePointerMove);
      window.addEventListener("click", handleClick);
      return () => {
        window.removeEventListener("pointermove", handlePointerMove);
        window.removeEventListener("click", handleClick);
        // Reset cursor in the cleanup so the stale position is gone if the
        // tool is re-activated later — this is an external system cleanup,
        // not a synchronous setState-in-body call.
        setCursorPos(null);
      };
    }
  }, [isActive, viewMode, handlePointerMove, handleClick]);

  if (!isActive || viewMode !== "2D") return null;

  return (
    <>
      {/* Completed measurement lines */}
      {lines.map((line) => {
        const p1: [number, number, number] = [
          line.start[0],
          0.05,
          line.start[1],
        ];
        const p2: [number, number, number] = [line.end[0], 0.05, line.end[1]];
        const dx = line.end[0] - line.start[0];
        const dz = line.end[1] - line.start[1];
        const dist = Math.hypot(dx, dz);
        const midX = (line.start[0] + line.end[0]) / 2;
        const midZ = (line.start[1] + line.end[1]) / 2;
        // Offset label perpendicular to the line
        const perpX = dist > 0 ? (-dz / dist) * 0.4 : 0;
        const perpZ = dist > 0 ? (dx / dist) * 0.4 : 0;
        let labelAngle = Math.atan2(dz, dx) * (180 / Math.PI);
        if (labelAngle > 90) labelAngle -= 180;
        if (labelAngle < -90) labelAngle += 180;

        return (
          <group key={line.id}>
            <Line
              points={[p1, p2]}
              color={MEASURE_COLOR}
              lineWidth={2}
              dashed
              dashScale={10}
              dashSize={0.25}
              gapSize={0.15}
            />
            {/* Start cap */}
            <mesh position={p1}>
              <sphereGeometry args={[0.08, 12, 12]} />
              <meshBasicMaterial color={MEASURE_COLOR} />
            </mesh>
            {/* End cap */}
            <mesh position={p2}>
              <sphereGeometry args={[0.08, 12, 12]} />
              <meshBasicMaterial color={MEASURE_COLOR} />
            </mesh>
            {/* Distance label */}
            {dist > 0.01 && (
              <Html
                position={[midX + perpX, 0.05, midZ + perpZ]}
                center
                zIndexRange={[40, 0]}
              >
                <div
                  style={{
                    transform: `rotate(${labelAngle}deg)`,
                    textShadow: "0 0 4px rgba(0,0,0,0.9)",
                  }}
                  className="text-[11px] font-semibold text-white whitespace-nowrap pointer-events-none select-none"
                >
                  {formatDistance(dist)}
                </div>
              </Html>
            )}
          </group>
        );
      })}

      {/* Ghost line from pending start to current cursor */}
      {pendingStart && cursorPos && (
        <>
          <Line
            points={[
              [pendingStart[0], 0.05, pendingStart[1]],
              [cursorPos[0], 0.05, cursorPos[1]],
            ]}
            color={MEASURE_COLOR}
            lineWidth={2}
            dashed
            dashScale={10}
            dashSize={0.25}
            gapSize={0.15}
          />
          {/* Pending start indicator */}
          <mesh position={[pendingStart[0], 0.05, pendingStart[1]]}>
            <sphereGeometry args={[0.1, 12, 12]} />
            <meshBasicMaterial color={MEASURE_COLOR} />
          </mesh>
          {/* Cursor indicator */}
          <mesh position={[cursorPos[0], 0.05, cursorPos[1]]}>
            <sphereGeometry args={[0.1, 12, 12]} />
            <meshBasicMaterial
              color={MEASURE_COLOR}
              transparent
              opacity={0.6}
            />
          </mesh>
          {/* Live ghost distance label */}
          {(() => {
            const dx = cursorPos[0] - pendingStart[0];
            const dz = cursorPos[1] - pendingStart[1];
            const dist = Math.hypot(dx, dz);
            if (dist < 0.01) return null;
            const midX = (pendingStart[0] + cursorPos[0]) / 2;
            const midZ = (pendingStart[1] + cursorPos[1]) / 2;
            const perpX = (-dz / dist) * 0.4;
            const perpZ = (dx / dist) * 0.4;
            let labelAngle = Math.atan2(dz, dx) * (180 / Math.PI);
            if (labelAngle > 90) labelAngle -= 180;
            if (labelAngle < -90) labelAngle += 180;
            return (
              <Html
                position={[midX + perpX, 0.05, midZ + perpZ]}
                center
                zIndexRange={[40, 0]}
              >
                <div
                  style={{
                    transform: `rotate(${labelAngle}deg)`,
                    textShadow: "0 0 4px rgba(0,0,0,0.9)",
                  }}
                  className="text-[11px] font-semibold text-white whitespace-nowrap pointer-events-none select-none"
                >
                  {formatDistance(dist)}
                </div>
              </Html>
            );
          })()}
        </>
      )}

      {/* Crosshair cursor when no pending start yet */}
      {!pendingStart && cursorPos && (
        <mesh position={[cursorPos[0], 0.05, cursorPos[1]]}>
          <sphereGeometry args={[0.1, 12, 12]} />
          <meshBasicMaterial color={MEASURE_COLOR} transparent opacity={0.5} />
        </mesh>
      )}
    </>
  );
}
