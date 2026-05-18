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
  buildDoorSwingFillGeometry,
  computeDoorSwingPlanGeometry,
} from "@/lib/doorPlanGeometry";

export type DoorSwingPlanOverlayProps = {
  wall: Wall;
  position: [number, number, number];
  rotation: [number, number, number, number] | undefined;
  size: [number, number, number];
  /** When set (2D door symbols), clicking the swing fill selects this scene object. */
  selectableObjectId?: string;
};

/**
 * White-filled swing sector + stroke (2D plan style), world-space XZ.
 */
export default function DoorSwingPlanOverlay({
  wall,
  position,
  rotation,
  size,
  selectableObjectId,
}: DoorSwingPlanOverlayProps) {
  const isCtrlPressed = useIsCtrlPressed();
  const selectObjectOrGroup = useSelectObjectOrGroup();
  const toggleObjectOrGroup = useToggleObjectOrGroup();

  const handleSwingClick = useCallback(
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

  const swing = useMemo(() => {
    return computeDoorSwingPlanGeometry(wall, position, rotation, size);
  }, [position, rotation, size, wall]);

  const fillGeometry = useMemo(() => {
    if (!swing) return null;
    return buildDoorSwingFillGeometry(swing.hingeX, swing.hingeZ, swing.arcPts);
  }, [swing]);

  useEffect(() => {
    return () => fillGeometry?.dispose();
  }, [fillGeometry]);

  if (!swing || !fillGeometry) return null;
  const { arcPts, leafPts } = swing;

  return (
    <group>
      <mesh
        geometry={fillGeometry}
        renderOrder={1}
        onClick={selectableObjectId ? handleSwingClick : undefined}
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
      <Line
        points={arcPts}
        color="#1a1a1a"
        lineWidth={1.5}
        dashed={false}
        depthTest={false}
        transparent
        opacity={0.92}
        renderOrder={2}
      />
      <Line
        points={leafPts}
        color="#1a1a1a"
        lineWidth={2}
        depthTest={false}
        transparent
        opacity={0.92}
        renderOrder={2}
      />
    </group>
  );
}
