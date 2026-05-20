"use client";

import { Canvas } from "@react-three/fiber";
import { OrbitControls, Grid } from "@react-three/drei";
import { Physics } from "@react-three/rapier";
import { ReactNode, RefObject } from "react";
import ScreenshotCapture, {
  ScreenshotCaptureHandle,
} from "../tools/ScreenshotCapture";
import CameraZoom, { CameraZoomHandle } from "../camera/CameraZoom";
import { useClearSelection } from "@/states/slices/selection/hooks";
import { useViewMode } from "@/states/slices/view/hooks";
import {
  useIsWallEditMode,
  useSelectWall,
} from "@/states/slices/wallEditor/hooks";
import DropHandler from "@/components/drag-n-drop/DropHandler";
import PasteGhost from "@/components/drag-n-drop/PasteGhost";
import DragGhost from "@/components/drag-n-drop/DragGhost";
import MouseDragSelect from "@/components/drag-n-drop/MouseDragSelect";
import WallDrawingTool from "@/components/tools/WallDrawingTool";
import MeasureToolScene from "@/components/tools/MeasureToolScene";
import Walls from "@/components/scene/Walls";
import DebugSplitOverlay from "@/components/scene/DebugSplitOverlay";
import DoorPlanSymbols from "@/components/scene/DoorPlanSymbols";
import PerformanceMonitor from "@/components/dev/PerformanceMonitor";
import CameraMovement from "@/components/camera/CameraMovement";
import CameraReset from "@/components/camera/CameraReset";
import CameraController, {
  type CameraControlHandle,
  type MinimapCameraState,
} from "@/components/camera/CameraController";

interface SceneProps {
  children?: ReactNode;
  screenshotRef?: RefObject<ScreenshotCaptureHandle | null>;
  cameraZoomRef?: RefObject<CameraZoomHandle | null>;
  cameraControlRef?: RefObject<CameraControlHandle | null>;
  onCameraStateChange?: (state: MinimapCameraState) => void;
}

/**
 * Main 3D Scene wrapper component
 * Sets up Canvas with orthographic or perspective camera based on view mode
 */
export default function Scene({
  children,
  screenshotRef,
  cameraZoomRef,
  cameraControlRef,
  onCameraStateChange,
}: SceneProps) {
  const clearSelection = useClearSelection();
  const selectWall = useSelectWall();
  const isWallEditMode = useIsWallEditMode();
  const viewMode = useViewMode();

  const is2D = viewMode === "2D";

  // Handle clicks on empty space - clear object or wall selection
  const handlePointerMissed = () => {
    if (isWallEditMode) {
      selectWall(null);
    } else {
      clearSelection();
    }
  };

  return (
    <Canvas
      style={{ width: "100%", height: "100%" }}
      gl={{
        alpha: false,
        antialias: true,
        powerPreference: "high-performance",
        preserveDrawingBuffer: true,
      }}
      camera={{ position: [15, 15, 15], fov: 50 }}
      dpr={[1, 2]} // Limit pixel ratio: 1x on low-end, 2x on high-end devices
      frameloop="demand" // Only render when needed (on interaction/changes)
      onPointerMissed={handlePointerMissed}
      onCreated={({ gl }) => {
        const canvas = gl.domElement;
        const handleContextLost = (e: Event) => {
          e.preventDefault(); // allow the browser to restore the context
        };
        const handleContextRestored = () => {
          gl.resetState(); // re-sync Three.js internal state after restoration
        };
        canvas.addEventListener("webglcontextlost", handleContextLost);
        canvas.addEventListener("webglcontextrestored", handleContextRestored);
        // Cleanup is handled by R3F when the Canvas unmounts
      }}
    >
      {/* Scene background tuned to the UI warm-neutral theme */}
      <color attach="background" args={["#f2f2f2"]} />

      <ambientLight intensity={2} />
      {!is2D && (
        <>
          {/* Key light with shadows */}
          <directionalLight
            position={[10, 10, 5]}
            intensity={1}
            castShadow
            shadow-mapSize={[1024, 1024]}
            shadow-camera-far={50}
            shadow-bias={-0.0001}
          />
          {/* Fill light from opposite side — no shadows, cheap */}
          <directionalLight position={[-8, 6, -6]} intensity={0.6} />
        </>
      )}

      {/* Camera Controls - rotation disabled in 2D mode */}
      <OrbitControls
        makeDefault
        enableDamping
        dampingFactor={0.05}
        enableRotate={!is2D}
      />

      {/* Resets camera position when switching to 2D mode */}
      <CameraReset />

      {/* Camera Movement - WASD/Arrow keys */}
      <CameraMovement />

      {/* Performance monitoring - logs FPS to console */}
      <PerformanceMonitor />

      {/* Converts overlay drop (clientX/clientY) to 3D position and adds object */}
      <DropHandler />

      {/* Shows ghost preview when pasting (Ctrl+V) - click to place */}
      <PasteGhost />

      {/* Shows ghost preview when dragging from palette - release to place */}
      <DragGhost />

      {/* Marquee drag-to-select — 2D mode only; draws a blue dashed rectangle */}
      <MouseDragSelect />

      {/* Wall drawing tool - shows ghost line while drawing new walls */}
      <WallDrawingTool />

      {/* Distance measure tool — orange dashed lines with distance labels (2D only) */}
      <MeasureToolScene />

      {/* Walls - rendered outside Physics to avoid coordinate transform issues */}
      <Walls />

      {/* Temporary normalize-run split marker, shown only when backend debug is enabled */}
      <DebugSplitOverlay />

      {/* 2D-only door swing / open-leaf plan symbols */}
      <DoorPlanSymbols />

      {/* Floor grid - visible from all angles */}
      <Grid
        position={[0, -0.05, 0]}
        args={[100, 100]}
        cellSize={1}
        cellThickness={0.5}
        cellColor="#ddd4c8"
        sectionSize={5}
        sectionThickness={1}
        sectionColor="#bfb5a7"
        fadeDistance={100}
        fadeStrength={1}
        followCamera={false}
        infiniteGrid
      />

      {/* Physics World - only for movable objects */}
      <Physics gravity={[0, -9.81, 0]}>{children}</Physics>

      {/* Screenshot capture — renders nothing, exposes capture() to the outer panel */}
      {screenshotRef && <ScreenshotCapture ref={screenshotRef} />}

      {/* Camera zoom — renders nothing, exposes zoomIn/zoomOut/reset to the toolbar */}
      {cameraZoomRef && <CameraZoom ref={cameraZoomRef} />}

      {/* Camera control — renders nothing, exposes setCameraXZ/setAzimuth/setHeight/setElevation */}
      {cameraControlRef && (
        <CameraController
          ref={cameraControlRef}
          onStateChange={onCameraStateChange}
        />
      )}
    </Canvas>
  );
}
