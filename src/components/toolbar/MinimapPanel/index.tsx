"use client";

import type { RefObject } from "react";
import type {
  CameraControlHandle,
  MinimapCameraState,
} from "@/components/camera/CameraController";
import type { CameraAnglePreset } from "@/types/global";
import MinimapView from "./MinimapView";
import HeightElevationPanel from "./HeightElevationPanel";
import CameraAnglesPanel from "./CameraAnglesPanel";

const SVG_SIZE = 200;

interface CameraControlPanelProps {
  cameraControlRef: RefObject<CameraControlHandle | null>;
  cameraState: MinimapCameraState;
  /** Override the outer wrapper's positioning classes. Defaults to fixed bottom-right. */
  className?: string;
  /** Preset camera angles for AI generation. Section is hidden when empty/undefined. */
  cameraAngles?: CameraAnglePreset[];
  /** Index of the currently active (previewed) angle. */
  activeAngleIdx?: number;
  /** Called when the user clicks ← or → to cycle angles. */
  onNavigate?: (delta: -1 | 1) => void;
  /** Called when the user toggles the checkmark on the active angle. */
  onToggleSelect?: (idx: number) => void;
}

export default function CameraControlPanel({
  cameraControlRef,
  cameraState,
  className,
  cameraAngles,
  activeAngleIdx = 0,
  onNavigate,
  onToggleSelect,
}: CameraControlPanelProps) {
  return (
    <div
      className={`${className ?? "fixed bottom-20 right-4 z-40 bg-white rounded-2xl overflow-hidden"} select-none flex flex-col`}
      style={{
        ...(className == null
          ? { width: SVG_SIZE + 16, boxShadow: "0 4px 16px rgba(0,0,0,0.1)" }
          : {}),
        userSelect: "none",
      }}
    >
      <MinimapView
        cameraControlRef={cameraControlRef}
        cameraState={cameraState}
      />
      {cameraAngles && cameraAngles.length > 0 && (
        <CameraAnglesPanel
          cameraAngles={cameraAngles}
          activeAngleIdx={activeAngleIdx}
          onNavigate={onNavigate}
          onToggleSelect={onToggleSelect}
        />
      )}
      <HeightElevationPanel
        cameraControlRef={cameraControlRef}
        cameraState={cameraState}
      />
    </div>
  );
}
