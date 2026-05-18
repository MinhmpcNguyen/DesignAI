"use client";

import { useCallback, useEffect, useMemo } from "react";
import { Line } from "@react-three/drei";
import type { ThreeEvent } from "@react-three/fiber";
import {
  useIsCtrlPressed,
  useSelectObjectOrGroup,
  useToggleObjectOrGroup,
} from "@/states/slices/selection/hooks";
import type { Wall } from "@/states/slices/walls/types";
import {
  buildWindowPlanFillGeometry,
  computeWindowPlanGeometry,
} from "@/lib/doorPlanGeometry";

export type WindowPlanOverlayProps = {
  wall: Wall;
  position: [number, number, number];
  rotation: [number, number, number, number] | undefined;
  size: [number, number, number];
  /** When set (2D window symbols), clicking the fill selects this scene object. */
  selectableObjectId?: string;
};

/**
 * Architectural 2D plan symbol for a window: two parallel lines spanning
 * the opening width, offset by ±(wallThickness × 0.35) from the wall centre.
 */
export default function WindowPlanOverlay({
  wall,
  position,
  size,
  selectableObjectId,
}: WindowPlanOverlayProps) {
  const isCtrlPressed = useIsCtrlPressed();
  const selectObjectOrGroup = useSelectObjectOrGroup();
  const toggleObjectOrGroup = useToggleObjectOrGroup();

  const handleClick = useCallback(
    (e: ThreeEvent<MouseEvent>) => {
      if (!selectableObjectId) return;
      e.stopPropagation();
      if (isCtrlPressed) toggleObjectOrGroup(selectableObjectId);
      else selectObjectOrGroup(selectableObjectId);
    },
    [
      selectableObjectId,
      isCtrlPressed,
      selectObjectOrGroup,
      toggleObjectOrGroup,
    ],
  );

  const geom = useMemo(
    () => computeWindowPlanGeometry(wall, position, size),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [
      wall.id,
      wall.startPoint[0],
      wall.startPoint[1],
      wall.endPoint[0],
      wall.endPoint[1],
      wall.thickness,
      position[0],
      position[1],
      position[2],
      size[0],
      size[1],
      size[2],
    ],
  );

  const fillGeometry = useMemo(() => {
    if (!geom) return null;
    return buildWindowPlanFillGeometry(geom.corners);
  }, [geom]);

  useEffect(() => {
    return () => fillGeometry?.dispose();
  }, [fillGeometry]);

  if (!geom || !fillGeometry) return null;
  const { outerLine, innerLine } = geom;

  return (
    <group>
      {/* White fill rectangle */}
      <mesh
        geometry={fillGeometry}
        renderOrder={1}
        onClick={selectableObjectId ? handleClick : undefined}
        onPointerOver={
          selectableObjectId
            ? (e) => {
                e.stopPropagation();
                if (typeof document !== "undefined") {
                  document.body.style.cursor = "pointer";
                }
              }
            : undefined
        }
        onPointerOut={
          selectableObjectId
            ? (e) => {
                e.stopPropagation();
                if (typeof document !== "undefined") {
                  document.body.style.cursor = "default";
                }
              }
            : undefined
        }
      >
        <meshBasicMaterial
          color="#ffffff"
          transparent
          opacity={0.94}
          depthTest={false}
          polygonOffset
          polygonOffsetFactor={-1}
          polygonOffsetUnits={-1}
        />
      </mesh>

      {/* Outer glass line */}
      <Line
        points={outerLine}
        color="#1a1a1a"
        lineWidth={1.5}
        dashed={false}
        depthTest={false}
        transparent
        opacity={0.92}
        renderOrder={2}
      />

      {/* Inner glass line */}
      <Line
        points={innerLine}
        color="#1a1a1a"
        lineWidth={1.5}
        dashed={false}
        depthTest={false}
        transparent
        opacity={0.92}
        renderOrder={2}
      />
    </group>
  );
}
