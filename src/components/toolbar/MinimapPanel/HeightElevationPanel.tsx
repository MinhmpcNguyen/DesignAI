"use client";

import { useCallback, useRef, useState } from "react";
import type { RefObject } from "react";
import { ChevronDown } from "lucide-react";
import type {
  CameraControlHandle,
  MinimapCameraState,
} from "@/components/camera/CameraController";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { useSetViewMode } from "@/states/slices/view/hooks";
import {
  MIN_HEIGHT,
  MAX_HEIGHT,
  FOV_MIN,
  FOV_MAX,
  FOV_STANDARD,
  PROFILE_AXIS_X,
  PROFILE_AXIS_TOP,
  PROFILE_AXIS_BOT,
  PROFILE_CONE_LEN,
  PROFILE_CONE_HALF,
} from "./constants";

interface HeightElevationPanelProps {
  cameraControlRef: RefObject<CameraControlHandle | null>;
  cameraState: Pick<MinimapCameraState, "y" | "elevation" | "fov">;
}

export default function HeightElevationPanel({
  cameraControlRef,
  cameraState,
}: HeightElevationPanelProps) {
  const setViewMode = useSetViewMode();

  // ── Derived display values ───────────────────────────────────────────────
  const heightMm = Math.round(cameraState.y * 1000);
  const elevDeg = Math.round(cameraState.elevation);
  const heightFraction =
    (cameraState.y - MIN_HEIGHT) / (MAX_HEIGHT - MIN_HEIGHT);

  // ── Side-profile derived values ──────────────────────────────────────────
  const profileAxisH = PROFILE_AXIS_BOT - PROFILE_AXIS_TOP;
  const profileCamY = PROFILE_AXIS_BOT - heightFraction * profileAxisH;
  const profileElevRad = (elevDeg * Math.PI) / 180;
  // SVG convention: left = π, positive elevation = tilt downward (+y in SVG)
  const profileConeDir = Math.PI - profileElevRad;
  const profileRay1X =
    PROFILE_AXIS_X +
    PROFILE_CONE_LEN * Math.cos(profileConeDir + PROFILE_CONE_HALF);
  const profileRay1Y =
    profileCamY +
    PROFILE_CONE_LEN * Math.sin(profileConeDir + PROFILE_CONE_HALF);
  const profileRay2X =
    PROFILE_AXIS_X +
    PROFILE_CONE_LEN * Math.cos(profileConeDir - PROFILE_CONE_HALF);
  const profileRay2Y =
    profileCamY +
    PROFILE_CONE_LEN * Math.sin(profileConeDir - PROFILE_CONE_HALF);

  // ── Drag: height track ───────────────────────────────────────────────────
  const heightDragStart = useRef<{
    trackRect: DOMRect;
    startY: number;
    startHeight: number;
  } | null>(null);

  const handleHeightPointerDown = useCallback(
    (e: React.PointerEvent<HTMLDivElement>) => {
      e.currentTarget.setPointerCapture(e.pointerId);
      heightDragStart.current = {
        trackRect: e.currentTarget.getBoundingClientRect(),
        startY: e.clientY,
        startHeight: cameraState.y,
      };
    },
    [cameraState.y],
  );

  const handleHeightPointerMove = useCallback(
    (e: React.PointerEvent<HTMLDivElement>) => {
      if (!heightDragStart.current) return;
      const { startY, startHeight, trackRect } = heightDragStart.current;

      // dragging UP = higher = positive world Y
      const deltaY = startY - e.clientY; // positive when dragging up
      const deltaMeters =
        (deltaY / trackRect.height) * (MAX_HEIGHT - MIN_HEIGHT);
      const newHeight = Math.max(
        MIN_HEIGHT,
        Math.min(MAX_HEIGHT, startHeight + deltaMeters),
      );

      setViewMode("3D");
      cameraControlRef.current?.setHeight(newHeight);
    },
    [setViewMode, cameraControlRef],
  );

  const handleHeightPointerUp = useCallback(() => {
    heightDragStart.current = null;
  }, []);

  // ── Drag: elevation scrubber ─────────────────────────────────────────────
  const elevDragStart = useRef<{ startX: number; startElev: number } | null>(
    null,
  );

  const handleElevPointerDown = useCallback(
    (e: React.PointerEvent<HTMLElement>) => {
      e.currentTarget.setPointerCapture(e.pointerId);
      elevDragStart.current = {
        startX: e.clientX,
        startElev: cameraState.elevation,
      };
    },
    [cameraState.elevation],
  );

  const handleElevPointerMove = useCallback(
    (e: React.PointerEvent<HTMLElement>) => {
      if (!elevDragStart.current) return;
      const { startX, startElev } = elevDragStart.current;
      // 1 degree per 2px horizontal drag
      const delta = (e.clientX - startX) * 0.5;
      const newElev = Math.max(-89, Math.min(89, startElev + delta));

      setViewMode("3D");
      cameraControlRef.current?.setElevation(newElev);
    },
    [setViewMode, cameraControlRef],
  );

  const handleElevPointerUp = useCallback(() => {
    elevDragStart.current = null;
  }, []);

  // ── Elevation input state ────────────────────────────────────────────────
  // null = show live camera value; string = user is actively editing
  const [elevDraft, setElevDraft] = useState<string | null>(null);

  const commitElev = useCallback(
    (val: string) => {
      const v = parseInt(val, 10);
      if (!isNaN(v)) {
        setViewMode("3D");
        cameraControlRef.current?.setElevation(Math.max(-89, Math.min(89, v)));
      }
    },
    [setViewMode, cameraControlRef],
  );

  // ── FOV state + handlers ─────────────────────────────────────────────────
  const [fovDraft, setFovDraft] = useState<string | null>(null);
  const fovDeg = Math.round(cameraState.fov ?? FOV_STANDARD);
  const fovFraction = (fovDeg - FOV_MIN) / (FOV_MAX - FOV_MIN);
  const fovDragActive = useRef(false);

  const applyFov = useCallback(
    (clientX: number, rect: DOMRect) => {
      const fraction = Math.max(
        0,
        Math.min(1, (clientX - rect.left) / rect.width),
      );
      const newFov = Math.round(FOV_MIN + fraction * (FOV_MAX - FOV_MIN));
      setViewMode("3D");
      cameraControlRef.current?.setFov(newFov);
    },
    [setViewMode, cameraControlRef],
  );

  const handleFovTrackPointerDown = useCallback(
    (e: React.PointerEvent<HTMLDivElement>) => {
      e.currentTarget.setPointerCapture(e.pointerId);
      fovDragActive.current = true;
      applyFov(e.clientX, e.currentTarget.getBoundingClientRect());
    },
    [applyFov],
  );

  const handleFovTrackPointerMove = useCallback(
    (e: React.PointerEvent<HTMLDivElement>) => {
      if (!fovDragActive.current) return;
      applyFov(e.clientX, e.currentTarget.getBoundingClientRect());
    },
    [applyFov],
  );

  const handleFovTrackPointerUp = useCallback(() => {
    fovDragActive.current = false;
  }, []);

  const commitFov = useCallback(
    (val: string) => {
      const v = parseInt(val, 10);
      if (!isNaN(v)) {
        setViewMode("3D");
        cameraControlRef.current?.setFov(v);
      }
    },
    [setViewMode, cameraControlRef],
  );

  return (
    <Collapsible defaultOpen className="bg-white rounded-md p-4">
      <CollapsibleTrigger asChild>
        <span className="group text-sm font-semibold  mb-2 cursor-pointer flex items-center justify-between w-full ">
          <span>Chiều cao, góc &amp; góc nhìn</span>
          <ChevronDown className="h-4 w-4 transition-transform duration-200 group-data-[state=open]:rotate-180" />
        </span>
      </CollapsibleTrigger>

      <CollapsibleContent>
        <div>
          <div className="border border-gray-200 rounded-md p-2">
            {/* ── Side-profile SVG (display only) ──────────────────────── */}
            <svg
              width="100%"
              viewBox="0 0 200 160"
              style={{ display: "block", overflow: "visible" }}
            >
              {/* Axis line */}
              <line
                x1={PROFILE_AXIS_X}
                y1={PROFILE_AXIS_TOP}
                x2={PROFILE_AXIS_X}
                y2={PROFILE_AXIS_BOT}
                strokeWidth={1.5}
                style={{ stroke: "var(--sub-color)" }}
              />
              {/* Top tick */}
              <line
                x1={PROFILE_AXIS_X - 4}
                y1={PROFILE_AXIS_TOP}
                x2={PROFILE_AXIS_X + 4}
                y2={PROFILE_AXIS_TOP}
                strokeWidth={1.5}
                style={{ stroke: "var(--sub-color)" }}
              />
              {/* Bottom tick */}
              <line
                x1={PROFILE_AXIS_X - 4}
                y1={PROFILE_AXIS_BOT}
                x2={PROFILE_AXIS_X + 4}
                y2={PROFILE_AXIS_BOT}
                strokeWidth={1.5}
                style={{ stroke: "var(--sub-color)" }}
              />
              {/* Top axis label */}
              <text
                x={PROFILE_AXIS_X + 8}
                y={PROFILE_AXIS_TOP + 4}
                fontSize={9}
                style={{ fill: "var(--sub-color)" }}
              >
                {MAX_HEIGHT * 1000}mm
              </text>
              {/* Bottom axis label */}
              <text
                x={PROFILE_AXIS_X + 8}
                y={PROFILE_AXIS_BOT + 4}
                fontSize={9}
                style={{ fill: "var(--sub-color)" }}
              >
                0mm
              </text>

              {/* Elevation cone — extends left from camera */}
              <polygon
                points={`${PROFILE_AXIS_X},${profileCamY} ${profileRay1X},${profileRay1Y} ${profileRay2X},${profileRay2Y}`}
                strokeWidth={0}
                style={{ fill: "var(--primary-color)", fillOpacity: 0.5 }}
              />

              {/* Camera icon — diamond on the axis */}
              <polygon
                points={`
                  ${PROFILE_AXIS_X - 7},${profileCamY}
                  ${PROFILE_AXIS_X},${profileCamY - 7}
                  ${PROFILE_AXIS_X + 7},${profileCamY}
                  ${PROFILE_AXIS_X},${profileCamY + 7}
                `}
                stroke="#fff"
                strokeWidth={1.5}
                style={{ fill: "var(--sub-color)" }}
              />

              {/* Angle badge */}
              <rect
                x={8}
                y={8}
                width={52}
                height={22}
                rx={5}
                style={{ fill: "var(--option-highlight-color)" }}
              />
              <text
                x={34}
                y={23}
                fontSize={11}
                fontWeight="600"
                textAnchor="middle"
                style={{ fill: "var(--secondary-color)" }}
              >
                {elevDeg}°
              </text>

              {/* Height badge */}
              <rect
                x={8}
                y={34}
                width={66}
                height={22}
                rx={5}
                style={{ fill: "var(--option-highlight-color)" }}
              />
              <text
                x={41}
                y={49}
                fontSize={11}
                fontWeight="600"
                textAnchor="middle"
                style={{ fill: "var(--secondary-color)" }}
              >
                {heightMm}mm
              </text>
            </svg>

            {/* ── Compact controls ─────────────────────────────────────── */}
            <div className="flex items-center gap-3 mt-1 mb-1">
              {/* Height track (compact) */}
              <div className="flex flex-col items-center gap-0.5">
                <span className="text-[8px] text-(--sub-color) font-mono leading-none">
                  {MAX_HEIGHT * 1000}
                </span>
                <div
                  className="relative bg-(--option-highlight-color) rounded-full"
                  style={{ width: 14, height: 60, cursor: "ns-resize" }}
                  onPointerDown={handleHeightPointerDown}
                  onPointerMove={handleHeightPointerMove}
                  onPointerUp={handleHeightPointerUp}
                >
                  <div
                    className="absolute bottom-0 left-0 right-0 rounded-full bg-(--primary-color)"
                    style={{ height: `${heightFraction * 100}%` }}
                  />
                  <div
                    className="absolute left-1/2 -translate-x-1/2 w-3 h-3 rounded-full bg-white border-2 border-(--primary-color) shadow-sm z-10"
                    style={{ top: 60 - heightFraction * 60 - 6 }}
                  />
                </div>
                <span className="text-[8px] text-(--sub-color) font-mono leading-none">
                  0
                </span>
              </div>

              {/* Elevation input with ew-drag scrubber */}
              <div className="flex flex-col gap-1">
                <span
                  className="text-[9px] text-(--sub-color) uppercase tracking-wide leading-none cursor-ew-resize select-none"
                  title="Drag left/right to change angle"
                  onPointerDown={handleElevPointerDown}
                  onPointerMove={handleElevPointerMove}
                  onPointerUp={handleElevPointerUp}
                >
                  Góc ↔
                </span>
                <div className="flex items-baseline gap-0.5">
                  <input
                    type="number"
                    min={-89}
                    max={89}
                    value={elevDraft ?? String(elevDeg)}
                    onChange={(e) => setElevDraft(e.target.value)}
                    onFocus={() => {
                      setElevDraft(String(elevDeg));
                    }}
                    onBlur={(e) => {
                      commitElev(e.target.value);
                      setElevDraft(null);
                    }}
                    onKeyDown={(e) => {
                      e.stopPropagation();
                      if (e.key === "Enter") {
                        commitElev((e.target as HTMLInputElement).value);
                        (e.target as HTMLInputElement).blur();
                      }
                    }}
                    className="w-16 bg-(--option-highlight-color) text-(--secondary-color) font-mono text-sm rounded px-2 py-0.5 border border-(--primary-border-color) focus:border-(--primary-color) outline-none text-center"
                  />
                  <span className="text-(--sub-color) font-mono text-xs">
                    °
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* ── Field of View panel ──────────────────────────────────────── */}
          <div className="border border-gray-200 rounded-md p-2 mt-2">
            <div className="flex items-center justify-between mb-3">
              <span className="text-[10px] font-semibold text-(--sub-color) uppercase tracking-widest">
                Trường nhìn (FOV)
              </span>
              <div className="flex items-baseline gap-0.5">
                <input
                  type="number"
                  min={FOV_MIN}
                  max={FOV_MAX}
                  value={fovDraft ?? String(fovDeg)}
                  onChange={(e) => setFovDraft(e.target.value)}
                  onFocus={() => setFovDraft(String(fovDeg))}
                  onBlur={(e) => {
                    commitFov(e.target.value);
                    setFovDraft(null);
                  }}
                  onKeyDown={(e) => {
                    e.stopPropagation();
                    if (e.key === "Enter") {
                      commitFov((e.target as HTMLInputElement).value);
                      (e.target as HTMLInputElement).blur();
                    }
                  }}
                  className="w-16 bg-(--option-highlight-color) text-(--secondary-color) font-mono text-sm rounded px-2 py-0.5 border border-(--primary-border-color) focus:border-(--primary-color) outline-none text-center"
                />
                <span className="text-(--sub-color) font-mono text-xs">°</span>
              </div>
            </div>

            {/* Slider track */}
            <div
              className="relative h-5 flex items-center cursor-ew-resize"
              onPointerDown={handleFovTrackPointerDown}
              onPointerMove={handleFovTrackPointerMove}
              onPointerUp={handleFovTrackPointerUp}
            >
              <div className="w-full h-1.5 bg-(--option-highlight-color) rounded-full overflow-hidden">
                <div
                  className="h-full bg-(--primary-color) rounded-full"
                  style={{ width: `${fovFraction * 100}%` }}
                />
              </div>
              {/* Standard (60°) marker line */}
              <div
                className="absolute w-px h-3 bg-(--sub-color)/50 rounded-full pointer-events-none"
                style={{
                  left: `${((FOV_STANDARD - FOV_MIN) / (FOV_MAX - FOV_MIN)) * 100}%`,
                }}
              />
              {/* Thumb */}
              <div
                className="absolute w-3.5 h-3.5 rounded-full bg-white border-2 border-(--primary-color) shadow-sm pointer-events-none"
                style={{ left: `calc(${fovFraction * 100}% - 7px)` }}
              />
            </div>

            {/* Labels */}
            <div className="flex justify-between mt-1.5">
              <span className="text-[12px] text-(--sub-color)">Hẹp</span>
              <span className="text-[12px] text-(--sub-color)">Tiêu chuẩn</span>
              <span className="text-[12px] text-(--sub-color)">Rộng</span>
            </div>
          </div>
        </div>
      </CollapsibleContent>
    </Collapsible>
  );
}
