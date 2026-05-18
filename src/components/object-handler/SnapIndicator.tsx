/**
 * SnapIndicator Component
 *
 * Visual feedback for snapping system showing where objects will snap.
 * Shows colored indicators for floor (green) and walls (blue).
 *
 * Performance optimizations:
 * - Memoized geometry and materials (created once)
 * - Conditional rendering (only when snapping is active)
 * - Low-poly geometry for minimal GPU load
 */

"use client";

import { useMemo } from "react";
import {
  DoubleSide,
  Euler,
  PlaneGeometry,
  Quaternion,
  RingGeometry,
} from "three";
import { useWalls } from "@/states/slices/walls/hooks";

interface SnapIndicatorProps {
  /** Type of snap indicator */
  type: "floor" | "wall" | "ceiling";
  /** Position where snap will occur */
  position: [number, number, number];
  /** Whether this snap is currently active/nearest */
  isActive: boolean;
  /** Snap rotation quaternion [x,y,z,w] — used to orient the wall indicator */
  rotation?: [number, number, number, number];
  /** Distance to snap target (for opacity/intensity feedback) */
  distance?: number;
}

/**
 * Floor Snap Indicator
 * Shows a circular ring at floor level where object will snap
 */
function FloorSnapIndicator({
  position,
  isActive,
  distance = 0,
}: {
  position: [number, number, number];
  isActive: boolean;
  distance: number;
}) {
  // Memoized geometry - ring shape for floor
  const geometry = useMemo(() => {
    return new RingGeometry(0.3, 0.4, 32);
  }, []);

  // Calculate opacity based on distance (closer = more opaque)
  const opacity = isActive ? Math.max(0.3, 1 - distance * 0.5) : 0.2;

  return (
    <mesh
      position={[position[0], 0.01, position[2]]} // Slightly above floor to prevent z-fighting
      rotation={[-Math.PI / 2, 0, 0]} // Rotate to lay flat
      geometry={geometry}
    >
      <meshBasicMaterial
        color="#10b981" // Green (Tailwind green-500)
        transparent
        opacity={opacity}
        side={DoubleSide}
        depthWrite={false} // Prevent depth buffer artifacts
      />
    </mesh>
  );
}

/**
 * Ceiling Snap Indicator
 * Shows an amber ring at ceiling level where the object will snap.
 */
function CeilingSnapIndicator({
  position,
  isActive,
  distance = 0,
}: {
  position: [number, number, number];
  isActive: boolean;
  distance: number;
}) {
  const walls = useWalls();
  const ceilingHeight = useMemo(
    () => (walls.length > 0 ? Math.max(...walls.map((w) => w.height)) : 3),
    [walls],
  );

  const geometry = useMemo(() => new RingGeometry(0.3, 0.4, 32), []);
  const opacity = isActive ? Math.max(0.3, 1 - distance * 0.5) : 0.2;

  return (
    <mesh
      position={[position[0], ceilingHeight - 0.01, position[2]]}
      rotation={[Math.PI / 2, 0, 0]} // Rotate to lay flat against ceiling (face down)
      geometry={geometry}
    >
      <meshBasicMaterial
        color="#f59e0b" // Amber (Tailwind amber-400)
        transparent
        opacity={opacity}
        side={DoubleSide}
        depthWrite={false}
      />
    </mesh>
  );
}

/**
 * Wall Snap Indicator
 * Shows a rectangular highlight on the wall where object will snap.
 * Orientation is derived from the snap rotation quaternion.
 */
function WallSnapIndicator({
  position,
  isActive,
  rotation,
  distance = 0,
}: {
  position: [number, number, number];
  isActive: boolean;
  rotation?: [number, number, number, number];
  distance: number;
}) {
  const geometry = useMemo(() => new PlaneGeometry(0.8, 0.8), []);

  // Derive Euler rotation from the snap quaternion so the indicator
  // lies flush against the snapped wall surface (any angle).
  const eulerRotation = useMemo((): [number, number, number] => {
    if (!rotation) return [0, 0, 0];
    const q = new Quaternion(
      rotation[0],
      rotation[1],
      rotation[2],
      rotation[3],
    );
    const e = new Euler().setFromQuaternion(q, "YXZ");
    return [e.x, e.y, e.z];
  }, [rotation]);

  const opacity = isActive ? Math.max(0.4, 1 - distance * 0.8) : 0.2;

  return (
    <mesh position={position} rotation={eulerRotation} geometry={geometry}>
      <meshBasicMaterial
        color="#3b82f6"
        transparent
        opacity={opacity}
        side={DoubleSide}
        depthWrite={false}
      />
    </mesh>
  );
}

/**
 * Main SnapIndicator Component
 * Renders appropriate indicator based on snap type
 */
export default function SnapIndicator({
  type,
  position,
  isActive,
  rotation,
  distance = 0,
}: SnapIndicatorProps) {
  if (type === "floor") {
    return (
      <FloorSnapIndicator
        position={position}
        isActive={isActive}
        distance={distance}
      />
    );
  }

  if (type === "wall") {
    return (
      <WallSnapIndicator
        position={position}
        isActive={isActive}
        rotation={rotation}
        distance={distance}
      />
    );
  }

  if (type === "ceiling") {
    return (
      <CeilingSnapIndicator
        position={position}
        isActive={isActive}
        distance={distance}
      />
    );
  }

  return null;
}
