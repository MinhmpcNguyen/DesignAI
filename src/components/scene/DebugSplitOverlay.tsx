"use client";

import { memo } from "react";
import { useDebugSplitWalls } from "@/states/slices/floor/hooks";
import { useViewMode } from "@/states/slices/view/hooks";
import type { AutoFillDebugSplitWall } from "@/types/api";

type DebugSplitWallMeshProps = {
  wall: AutoFillDebugSplitWall;
};

const DebugSplitWallMesh = memo(function DebugSplitWallMesh({
  wall,
}: DebugSplitWallMeshProps) {
  const [sx, sz] = wall.startPoint;
  const [ex, ez] = wall.endPoint;
  const centerX = (sx + ex) / 2;
  const centerZ = (sz + ez) / 2;
  const length = Math.hypot(ex - sx, ez - sz);
  if (length < 1e-6) return null;

  const angle = -Math.atan2(ez - sz, ex - sx);
  const thickness = Math.max(wall.thickness ?? 0.08, 0.08);

  return (
    <group
      position={[centerX, 0.08, centerZ]}
      rotation={[0, angle, 0]}
      renderOrder={80}
    >
      <mesh renderOrder={80}>
        <boxGeometry args={[length, 0.035, thickness + 0.08]} />
        <meshBasicMaterial
          color="#48e6f2"
          transparent
          opacity={0.55}
          depthTest={false}
        />
      </mesh>
      <mesh position={[0, 0.004, 0]} renderOrder={81}>
        <boxGeometry args={[length, 0.04, Math.max(thickness * 0.35, 0.035)]} />
        <meshBasicMaterial
          color="#ffffff"
          transparent
          opacity={0.95}
          depthTest={false}
        />
      </mesh>
    </group>
  );
});

export default function DebugSplitOverlay() {
  const viewMode = useViewMode();
  const debugSplitWalls = useDebugSplitWalls();
  if (viewMode !== "2D") return null;

  const walls = Object.values(debugSplitWalls);
  if (walls.length === 0) return null;

  return (
    <>
      {walls.map((wall) => (
        <DebugSplitWallMesh key={wall.id} wall={wall} />
      ))}
    </>
  );
}
