"use client";

import { useCallback, useMemo, useRef } from "react";
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
import { useWalls } from "@/states/slices/walls/hooks";
import { useSetViewMode } from "@/states/slices/view/hooks";
import { SVG_SIZE, FOV_LENGTH_PX, FOV_STANDARD } from "./constants";
import { buildWorldToSvg } from "./buildWorldToSvg";

interface MinimapViewProps {
  cameraControlRef: RefObject<CameraControlHandle | null>;
  cameraState: Pick<MinimapCameraState, "x" | "z" | "azimuth" | "fov">;
}

export default function MinimapView({
  cameraControlRef,
  cameraState,
}: MinimapViewProps) {
  const walls = useWalls();
  const setViewMode = useSetViewMode();

  // World→SVG mapping — recomputed when walls or camera position changes
  const proj = useMemo(
    () => buildWorldToSvg(walls, [[cameraState.x, cameraState.z]]),
    [walls, cameraState.x, cameraState.z],
  );

  // Wall XZ bounding box — used to clamp camera dot dragging to map bounds
  const wallBounds = useMemo(() => {
    const xs: number[] = [];
    const zs: number[] = [];
    for (const w of walls) {
      xs.push(w.startPoint[0], w.endPoint[0]);
      zs.push(w.startPoint[1], w.endPoint[1]);
    }
    if (xs.length === 0) return null;
    return {
      minX: Math.min(...xs),
      maxX: Math.max(...xs),
      minZ: Math.min(...zs),
      maxZ: Math.max(...zs),
    };
  }, [walls]);

  // Camera SVG position (derived)
  const camSvg = useMemo<[number, number]>(
    () => proj.toSvg(cameraState.x, cameraState.z),
    [cameraState.x, cameraState.z, proj],
  );

  const fovPoints = useMemo(() => {
    const [cx, cy] = camSvg;
    const dir = cameraState.azimuth + Math.PI / 2;
    // Use live vertical FOV from camera; half-angle drives the cone width
    const fovHalfAngle =
      ((cameraState.fov ?? FOV_STANDARD) / 2) * (Math.PI / 180);

    const tipX = cx + FOV_LENGTH_PX * Math.cos(dir);
    const tipY = cy + FOV_LENGTH_PX * Math.sin(dir);
    const leftX = cx + FOV_LENGTH_PX * Math.cos(dir - fovHalfAngle);
    const leftY = cy + FOV_LENGTH_PX * Math.sin(dir - fovHalfAngle);
    const rightX = cx + FOV_LENGTH_PX * Math.cos(dir + fovHalfAngle);
    const rightY = cy + FOV_LENGTH_PX * Math.sin(dir + fovHalfAngle);

    return { tipX, tipY, leftX, leftY, rightX, rightY };
  }, [camSvg, cameraState.azimuth, cameraState.fov]);

  // ── Drag: camera dot (pan) ────────────────────────────────────────────────
  const camDragStart = useRef<{
    svgRect: DOMRect;
    startSvgX: number;
    startSvgY: number;
    startWorldX: number;
    startWorldZ: number;
  } | null>(null);

  const handleCamPointerDown = useCallback(
    (e: React.PointerEvent<SVGCircleElement>) => {
      e.stopPropagation();
      e.currentTarget.setPointerCapture(e.pointerId);
      const svg = e.currentTarget.ownerSVGElement!;
      camDragStart.current = {
        svgRect: svg.getBoundingClientRect(),
        startSvgX: camSvg[0],
        startSvgY: camSvg[1],
        startWorldX: cameraState.x,
        startWorldZ: cameraState.z,
      };
    },
    [camSvg, cameraState.x, cameraState.z],
  );

  const handleCamPointerMove = useCallback(
    (e: React.PointerEvent<SVGCircleElement>) => {
      if (!camDragStart.current) return;
      const { svgRect, startSvgX, startSvgY } = camDragStart.current;

      const svgX = ((e.clientX - svgRect.left) / svgRect.width) * SVG_SIZE;
      const svgY = ((e.clientY - svgRect.top) / svgRect.height) * SVG_SIZE;

      const deltaSvgX = svgX - startSvgX;
      const deltaSvgY = svgY - startSvgY;

      // Convert the SVG delta to world delta using inverse transform
      const [dx] = proj.toWorld(deltaSvgX, 0);
      const [, dz] = proj.toWorld(0, deltaSvgY);
      const [ox] = proj.toWorld(0, 0);

      const rawX = camDragStart.current.startWorldX + (dx - ox);
      const rawZ = camDragStart.current.startWorldZ + (dz - ox);

      // Clamp camera position to map bounds (15 m margin outside walls)
      const margin = 15;
      const newX = wallBounds
        ? Math.max(
            wallBounds.minX - margin,
            Math.min(wallBounds.maxX + margin, rawX),
          )
        : rawX;
      const newZ = wallBounds
        ? Math.max(
            wallBounds.minZ - margin,
            Math.min(wallBounds.maxZ + margin, rawZ),
          )
        : rawZ;

      setViewMode("3D");
      cameraControlRef.current?.setCameraXZ(newX, newZ);
    },
    [proj, wallBounds, setViewMode, cameraControlRef],
  );

  const handleCamPointerUp = useCallback(() => {
    camDragStart.current = null;
  }, []);

  // ── Drag: rotation handle (azimuth) ──────────────────────────────────────
  const rotDragActive = useRef(false);

  const handleRotPointerDown = useCallback(
    (e: React.PointerEvent<SVGGElement>) => {
      e.stopPropagation();
      e.currentTarget.setPointerCapture(e.pointerId);
      rotDragActive.current = true;
    },
    [],
  );

  const handleRotPointerMove = useCallback(
    (e: React.PointerEvent<SVGGElement>) => {
      if (!rotDragActive.current) return;
      const svg = e.currentTarget.ownerSVGElement!;
      const rect = svg.getBoundingClientRect();

      const svgX = ((e.clientX - rect.left) / rect.width) * SVG_SIZE;
      const svgY = ((e.clientY - rect.top) / rect.height) * SVG_SIZE;

      // atan2 from camera dot to pointer gives the desired facing SVG angle.
      // SVG dir = azimuth + π/2, so azimuth = svgAngle - π/2
      const svgAngle = Math.atan2(svgY - camSvg[1], svgX - camSvg[0]);
      const azimuth = svgAngle - Math.PI / 2;

      setViewMode("3D");
      cameraControlRef.current?.setAzimuth(azimuth);
    },
    [camSvg, setViewMode, cameraControlRef],
  );

  const handleRotPointerUp = useCallback(() => {
    rotDragActive.current = false;
  }, []);

  const { tipX, tipY, leftX, leftY, rightX, rightY } = fovPoints;
  // Rotation handle center — halfway along the inner edge of the cone tip
  const rotHandleX = (leftX + rightX) / 2;
  const rotHandleY = (leftY + rightY) / 2;

  return (
    <Collapsible defaultOpen className="bg-white rounded-md p-4 mb-1.5">
      <CollapsibleTrigger asChild>
        <span className="group text-sm font-semibold mb-2 px-1 cursor-pointer flex items-center justify-between w-full">
          <span>Góc đặt máy quay</span>
          <ChevronDown className="h-4 w-4 transition-transform duration-200 group-data-[state=open]:rotate-180" />
        </span>
      </CollapsibleTrigger>
      <CollapsibleContent>
        <svg
          width="100%"
          viewBox={`0 0 ${SVG_SIZE} ${SVG_SIZE}`}
          style={{ display: "block", overflow: "hidden", aspectRatio: "1" }}
          className="border border-gray-200 rounded-md"
        >
          {/* Room walls */}
          {walls.map((w) => {
            const [x1, y1] = proj.toSvg(w.startPoint[0], w.startPoint[1]);
            const [x2, y2] = proj.toSvg(w.endPoint[0], w.endPoint[1]);
            return (
              <line
                key={w.id}
                x1={x1}
                y1={y1}
                x2={x2}
                y2={y2}
                strokeWidth={2.5}
                strokeLinecap="round"
                style={{ stroke: "var(--search-border-color)" }}
              />
            );
          })}

          {/* FOV cone */}
          <polygon
            points={`${camSvg[0]},${camSvg[1]} ${leftX},${leftY} ${tipX},${tipY} ${rightX},${rightY}`}
            strokeWidth={1}
            style={{
              fill: "var(--primary-color)",
              fillOpacity: 0.35,
              stroke: "var(--primary-color)",
              strokeOpacity: 0.8,
            }}
          />

          {/* Camera dot — draggable */}
          <circle
            cx={camSvg[0]}
            cy={camSvg[1]}
            r={7}
            stroke="#fff"
            strokeWidth={2}
            style={{ fill: "var(--primary-color)", cursor: "grab" }}
            onPointerDown={handleCamPointerDown}
            onPointerMove={handleCamPointerMove}
            onPointerUp={handleCamPointerUp}
          />

          {/* Rotation handle — draggable group at cone tip arc midpoint */}
          <g
            style={{ cursor: "ew-resize" }}
            onPointerDown={handleRotPointerDown}
            onPointerMove={handleRotPointerMove}
            onPointerUp={handleRotPointerUp}
          >
            {/* Handle circle */}
            <circle
              cx={rotHandleX}
              cy={rotHandleY}
              r={6}
              stroke="#fff"
              strokeWidth={1.5}
              style={{ fill: "var(--primary-color)" }}
            />
            {/* Left arrow triangle */}
            <polygon
              points={`
                ${rotHandleX - 10},${rotHandleY}
                ${rotHandleX - 6},${rotHandleY - 4}
                ${rotHandleX - 6},${rotHandleY + 4}
              `}
              fill="#fff"
            />
            {/* Right arrow triangle */}
            <polygon
              points={`
                ${rotHandleX + 10},${rotHandleY}
                ${rotHandleX + 6},${rotHandleY - 4}
                ${rotHandleX + 6},${rotHandleY + 4}
              `}
              fill="#fff"
            />
          </g>
        </svg>
      </CollapsibleContent>
    </Collapsible>
  );
}
