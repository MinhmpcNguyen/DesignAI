"use client";

import Scene from "@/components/scene/Scene";
import Floor from "@/components/scene/Floor";
import Ceiling from "@/components/scene/Ceiling";
import MovableObject from "@/components/object-handler/MovableObject";
import type { ScreenshotCaptureHandle } from "@/components/tools/ScreenshotCapture";
import type { CameraZoomHandle } from "@/components/camera/CameraZoom";
import type {
  CameraControlHandle,
  MinimapCameraState,
} from "@/components/camera/CameraController";
import type { SceneObject } from "@/states/slices/objects/types";
import type { Dispatch, RefObject, SetStateAction } from "react";

type DesignSceneCanvasProps = {
  screenshotRef: RefObject<ScreenshotCaptureHandle | null>;
  cameraZoomRef: RefObject<CameraZoomHandle | null>;
  cameraControlRef: RefObject<CameraControlHandle | null>;
  setCameraState: Dispatch<SetStateAction<MinimapCameraState>>;
  objects: SceneObject[];
  isAIGenMode?: boolean;
};

export default function DesignSceneCanvas({
  screenshotRef,
  cameraZoomRef,
  cameraControlRef,
  setCameraState,
  objects,
  isAIGenMode,
}: DesignSceneCanvasProps) {
  return (
    <div className="w-full h-full">
      <Scene
        screenshotRef={screenshotRef}
        cameraZoomRef={cameraZoomRef}
        cameraControlRef={cameraControlRef}
        onCameraStateChange={setCameraState}
      >
        {/* Static Environment */}
        <Floor hideSelection={isAIGenMode} />
        <Ceiling />
        {/* Walls now rendered directly in Scene.tsx outside Physics */}

        {/* Movable Objects - Rendered from state */}
        {objects.map((obj) => (
          <MovableObject
            key={obj.id}
            id={obj.id}
            position={obj.position}
            rotation={obj.rotation}
            shape={obj.type}
            color={obj.color}
            size={obj.size}
            name={obj.name}
            modelUrl={obj.modelUrl}
            placementType={obj.placementType}
            objectRole={obj.objectRole}
            snappedToWall={obj.snappedToWall}
            collisionLayer={obj.collisionLayer}
            placeOn={obj.placeOn}
          />
        ))}
      </Scene>
    </div>
  );
}
