"use client";

import { useMemo, useEffect } from "react";
import { BackSide, Shape, ShapeGeometry } from "three";
import { useWalls } from "@/states/slices/walls/hooks";
import { useViewMode } from "@/states/slices/view/hooks";
import { findRoomPolygons } from "@/lib/roomPolygons";

// ---------------------------------------------------------------------------
// RoomCeiling — one ceiling panel per room polygon.
//
// Uses BackSide so the mesh is visible when the camera looks UP from inside
// the room, but invisible when looking DOWN (top-down 3D or 2D plan view).
// ---------------------------------------------------------------------------
function RoomCeiling({
  polygon,
  ceilingHeight,
}: {
  polygon: [number, number][];
  ceilingHeight: number;
}) {
  const geometry = useMemo(() => {
    const shape = new Shape();
    // Mirror the same winding as Floor.tsx: wall [x,z] → shape (x, -z)
    // After rotation={[-Math.PI/2, 0, 0]} this maps to world (x, ceilingHeight, z)
    shape.moveTo(polygon[0][0], -polygon[0][1]);
    for (let i = 1; i < polygon.length; i++) {
      shape.lineTo(polygon[i][0], -polygon[i][1]);
    }
    shape.closePath();
    return new ShapeGeometry(shape);
  }, [polygon]);

  useEffect(() => () => geometry.dispose(), [geometry]);

  return (
    <mesh
      rotation={[-Math.PI / 2, 0, 0]}
      position={[0, ceilingHeight, 0]}
    >
      <primitive object={geometry} attach="geometry" />
      {/* BackSide: face normals point DOWN (into the room).
          Visible from below (looking up), invisible from above (looking down or 2D). */}
      <meshStandardMaterial
        color="#F0EDE8"
        roughness={0.9}
        metalness={0}
        side={BackSide}
      />
    </mesh>
  );
}

// ---------------------------------------------------------------------------
// Ceiling — root component; reads walls from Redux, computes polygons.
// Only rendered in 3D view (returns null in 2D).
// ---------------------------------------------------------------------------
export default function Ceiling() {
  const walls = useWalls();
  const viewMode = useViewMode();

  const roomPolygons = useMemo(() => findRoomPolygons(walls), [walls]);
  const ceilingHeight = useMemo(
    () => (walls.length > 0 ? Math.max(...walls.map((w) => w.height)) : 3),
    [walls],
  );

  // Ceiling is invisible in 2D top-down plan view — don't render at all.
  if (viewMode === "2D" || roomPolygons.length === 0) return null;

  return (
    <>
      {roomPolygons.map((polygon, i) => (
        <RoomCeiling
          key={i}
          polygon={polygon}
          ceilingHeight={ceilingHeight}
        />
      ))}
    </>
  );
}
