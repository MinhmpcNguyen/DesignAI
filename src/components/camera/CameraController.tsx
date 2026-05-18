"use client";

import { forwardRef, useCallback, useImperativeHandle, useRef } from "react";
import { useFrame, useThree } from "@react-three/fiber";
import { PerspectiveCamera, Vector3 } from "three";

export interface MinimapCameraState {
  /** Camera world X */
  x: number;
  /** Camera world Y (height) */
  y: number;
  /** Camera world Z */
  z: number;
  /** OrbitControls target X */
  targetX: number;
  /** OrbitControls target Z */
  targetZ: number;
  /**
   * Azimuth angle in radians — the horizontal compass direction the camera
   * faces (0 = looking toward –Z, increases clockwise when viewed from above)
   */
  azimuth: number;
  /**
   * Elevation angle in degrees — the vertical angle of the camera above the
   * horizontal plane through the target (0° = level, 90° = straight down)
   */
  elevation: number;
  /**
   * Vertical field of view in degrees (same as Three.js PerspectiveCamera.fov).
   * Narrow = telephoto (zoomed in), wide = wide-angle.
   */
  fov: number;
}

export interface CameraControlHandle {
  /**
   * Move the camera to a new XZ world position, keeping the same XZ offset
   * from the OrbitControls target (pans both together).
   */
  setCameraXZ: (x: number, z: number) => void;
  /**
   * Rotate the camera horizontally around its current target.
   * @param radians — absolute azimuth angle (0 = –Z direction)
   */
  setAzimuth: (radians: number) => void;
  /**
   * Set absolute camera height (Y axis), clamped to [0, 3] metres.
   */
  setHeight: (meters: number) => void;
  /**
   * Set camera elevation angle in degrees relative to target.
   * Adjusts camera.position.y, keeping distXZ constant.
   */
  setElevation: (degrees: number) => void;
  /**
   * Set the vertical field of view in degrees, clamped to [20, 100].
   * Narrow FOV (telephoto) = zoomed in. Wide FOV = wide-angle.
   */
  setFov: (degrees: number) => void;
}

interface CameraControlProps {
  onStateChange?: (state: MinimapCameraState) => void;
}

const EPS = 0.001;

/** Invisible R3F child — reads camera + controls state and exposes camera control methods */
const CameraControl = forwardRef<CameraControlHandle, CameraControlProps>(
  ({ onStateChange }, ref) => {
    const get = useThree((s) => s.get);
    const invalidate = useThree((s) => s.invalidate);

    // Last-emitted state for change detection
    const lastState = useRef<MinimapCameraState | null>(null);

    // ── State polling ────────────────────────────────────────────────────────
    useFrame(() => {
      if (!onStateChange) return;
      const { camera, controls } = get();
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const ctrl = controls as any;
      const target: Vector3 = ctrl?.target ?? new Vector3();

      const dx = camera.position.x - target.x;
      const dz = camera.position.z - target.z;
      const distXZ = Math.sqrt(dx * dx + dz * dz);

      // Azimuth: angle of camera-from-target in XZ plane, measured clockwise from –Z
      const azimuth = Math.atan2(dx, -dz);

      // Elevation: angle above horizontal (0° = level, positive = looking down)
      const elevation =
        distXZ < EPS
          ? 90
          : Math.atan2(camera.position.y - target.y, distXZ) * (180 / Math.PI);

      const fov = (camera as PerspectiveCamera).fov ?? 60;

      const next: MinimapCameraState = {
        x: camera.position.x,
        y: camera.position.y,
        z: camera.position.z,
        targetX: target.x,
        targetZ: target.z,
        azimuth,
        elevation,
        fov,
      };

      const prev = lastState.current;
      if (
        !prev ||
        Math.abs(prev.x - next.x) > EPS ||
        Math.abs(prev.y - next.y) > EPS ||
        Math.abs(prev.z - next.z) > EPS ||
        Math.abs(prev.targetX - next.targetX) > EPS ||
        Math.abs(prev.targetZ - next.targetZ) > EPS ||
        Math.abs(prev.azimuth - next.azimuth) > EPS ||
        Math.abs(prev.elevation - next.elevation) > EPS ||
        Math.abs(prev.fov - next.fov) > EPS
      ) {
        lastState.current = next;
        onStateChange(next);
      }
    });

    // ── Helper ───────────────────────────────────────────────────────────────
    const getCtrl = useCallback(() => {
      const { controls } = get();
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      return controls as any;
    }, [get]);

    // ── Exposed handle ───────────────────────────────────────────────────────
    useImperativeHandle(
      ref,
      () => ({
        setCameraXZ(x: number, z: number) {
          const { camera } = get();
          const ctrl = getCtrl();
          const target: Vector3 = ctrl?.target ?? new Vector3();

          // Keep camera↔target offset, just translate both in XZ
          const offsetX = camera.position.x - target.x;
          const offsetZ = camera.position.z - target.z;

          target.x = x - offsetX;
          target.z = z - offsetZ;
          camera.position.x = x;
          camera.position.z = z;

          ctrl?.update?.();
          invalidate();
        },

        setAzimuth(radians: number) {
          const { camera } = get();
          const ctrl = getCtrl();
          const target: Vector3 = ctrl?.target ?? new Vector3();

          const dx = camera.position.x - target.x;
          const dz = camera.position.z - target.z;
          const distXZ = Math.sqrt(dx * dx + dz * dz);

          // Keep camera fixed; rotate target around camera to the new azimuth.
          // Convention: azimuth 0 → target is at +Z from camera (camera faces –Z).
          target.x = camera.position.x - distXZ * Math.sin(radians);
          target.z = camera.position.z + distXZ * Math.cos(radians);

          ctrl?.update?.();
          invalidate();
        },

        setHeight(meters: number) {
          const { camera } = get();
          const ctrl = getCtrl();
          const target: Vector3 = ctrl?.target ?? new Vector3();

          const dx = camera.position.x - target.x;
          const dz = camera.position.z - target.z;
          const distXZ = Math.sqrt(dx * dx + dz * dz);

          // Preserve elevation angle by tracking how much target.y must shift.
          const elevRad =
            distXZ < EPS ? 0 : Math.atan2(camera.position.y - target.y, distXZ);

          camera.position.y = Math.max(0, Math.min(3, meters));

          // Move target.y so the look-angle stays the same.
          if (distXZ >= EPS) {
            target.y = camera.position.y - distXZ * Math.tan(elevRad);
          }

          ctrl?.update?.();
          invalidate();
        },

        setElevation(degrees: number) {
          const { camera } = get();
          const ctrl = getCtrl();
          const target: Vector3 = ctrl?.target ?? new Vector3();

          const dx = camera.position.x - target.x;
          const dz = camera.position.z - target.z;
          const distXZ = Math.sqrt(dx * dx + dz * dz);

          if (distXZ < EPS) return; // camera directly above target — skip

          const clampedDeg = Math.max(-89, Math.min(89, degrees));
          const rad = clampedDeg * (Math.PI / 180);

          // Keep camera XYZ fixed; tilt by adjusting target.y only.
          // Negative degrees → target.y > camera.y → camera looks upward.
          target.y = camera.position.y - distXZ * Math.tan(rad);

          ctrl?.update?.();
          invalidate();
        },

        setFov(degrees: number) {
          const { camera } = get();
          const clampedFov = Math.max(20, Math.min(100, degrees));
          (camera as PerspectiveCamera).fov = clampedFov;
          (camera as PerspectiveCamera).updateProjectionMatrix();
          invalidate();
        },
      }),
      [get, getCtrl, invalidate],
    );

    return null;
  },
);

CameraControl.displayName = "CameraControl";
export default CameraControl;
