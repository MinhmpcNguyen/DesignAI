"use client";

import { forwardRef, useCallback, useImperativeHandle } from "react";
import { useThree } from "@react-three/fiber";
import { OrthographicCamera, Vector3 } from "three";

export interface CameraZoomHandle {
  zoomIn: () => void;
  zoomOut: () => void;
  reset: () => void;
}

/** How much each zoom step scales the distance / ortho.zoom */
const ZOOM_FACTOR = 1.25;

/**
 * Invisible R3F child that exposes camera zoom controls via an imperative ref.
 * Must live inside <Canvas>. Works with both the OrthographicCamera (2D mode)
 * and the PerspectiveCamera (3D mode) without needing to know the current mode.
 */
const CameraZoom = forwardRef<CameraZoomHandle>((_, ref) => {
  const get = useThree((s) => s.get);
  const invalidate = useThree((s) => s.invalidate);

  /**
   * distanceFactor < 1 → zoom in (shorter distance / higher ortho.zoom)
   * distanceFactor > 1 → zoom out
   */
  const applyZoom = useCallback(
    (distanceFactor: number) => {
      const { camera, controls } = get();
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const ctrl = controls as any;

      if (camera instanceof OrthographicCamera) {
        camera.zoom = Math.max(0.2, Math.min(50, camera.zoom / distanceFactor));
        camera.updateProjectionMatrix();
      } else {
        // Move camera along the target → camera direction
        const target: Vector3 = ctrl?.target ?? new Vector3();
        const dir = new Vector3().subVectors(camera.position, target);
        const newDist = Math.max(1, dir.length() * distanceFactor);
        camera.position.copy(target).addScaledVector(dir.normalize(), newDist);
      }

      ctrl?.update?.();
      invalidate();
    },
    [get, invalidate],
  );

  useImperativeHandle(
    ref,
    () => ({
      zoomIn() {
        applyZoom(1 / ZOOM_FACTOR);
      },
      zoomOut() {
        applyZoom(ZOOM_FACTOR);
      },
      reset() {
        const { camera, controls } = get();
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const ctrl = controls as any;

        if (camera instanceof OrthographicCamera) {
          camera.zoom = 2.5; // matches the default set in CameraReset.tsx
          camera.position.set(0, 50, 0);
          camera.updateProjectionMatrix();
        } else {
          camera.position.set(15, 15, 15); // matches canvas camera prop
        }

        ctrl?.target?.set(0, 0, 0);
        ctrl?.update?.();
        invalidate();
      },
    }),
    [applyZoom, get, invalidate],
  );

  return null;
});

CameraZoom.displayName = "CameraZoom";
export default CameraZoom;
