"use client";

import { useEffect, useRef } from "react";
import { useThree } from "@react-three/fiber";
import { useViewMode } from "@/states/slices/view/hooks";
import { OrthographicCamera, PerspectiveCamera } from "three";

/**
 * Imperatively swaps between a true OrthographicCamera (2D — no depth, no
 * perspective distortion) and the original PerspectiveCamera (3D) whenever
 * the view mode changes.
 *
 * Why imperative instead of declarative (<OrthographicCamera makeDefault>)?
 * The Canvas `camera` prop only runs once at mount, so conditional JSX cameras
 * inside the scene need `makeDefault` plumbing that can race with OrbitControls
 * re-initialisation. Swapping via `set({ camera })` is simpler and reliable.
 */
export default function CameraReset() {
  const set = useThree((state) => state.set);
  const get = useThree((state) => state.get);
  const invalidate = useThree((state) => state.invalidate);
  const size = useThree((state) => state.size);
  const viewMode = useViewMode();

  // Stable refs — created once, reused across mode switches
  const perspRef = useRef<PerspectiveCamera | null>(null);
  const orthoRef = useRef<OrthographicCamera | null>(null);

  // ── Main effect: swap camera on every viewMode change ───────────────────
  useEffect(() => {
    // First run: capture R3F's initial PerspectiveCamera so we can restore it
    if (!perspRef.current) {
      const cam = get().camera;
      if (cam instanceof PerspectiveCamera) {
        perspRef.current = cam;
        cam.position.set(15, 15, 15);
        cam.lookAt(0, 0, 0);
        cam.updateProjectionMatrix();
      }
    }

    if (viewMode === "2D") {
      // ── Build OrthographicCamera once ──────────────────────────────────
      if (!orthoRef.current) {
        const ortho = new OrthographicCamera(-1, 1, 1, -1, 0.1, 1000);
        // With the camera above the XZ floor plane looking straight down,
        // Three.js' default up=(0,1,0) is parallel to the view direction
        // (gimbal lock). Setting up=(0,0,-1) makes -Z the "north" direction
        // in the 2D floor plan (top of screen = negative Z in world space).
        ortho.up.set(0, 0, -1);
        orthoRef.current = ortho;
      }

      const ortho = orthoRef.current;
      const { width, height } = get().size;
      const aspect = width / height;
      // viewH = how many world-units (metres) are visible vertically at zoom=1.
      // 30 m shows the default 20×20 m room with comfortable margins.
      const viewH = 30;
      ortho.left = (-aspect * viewH) / 2;
      ortho.right = (aspect * viewH) / 2;
      ortho.top = viewH / 2;
      ortho.bottom = -viewH / 2;
      ortho.zoom = 2.5; // Start zoomed in to show the room nicely
      ortho.position.set(0, 50, 0);
      ortho.lookAt(0, 0, 0);
      ortho.updateProjectionMatrix();

      set({ camera: ortho });

      // Snap OrbitControls pan target to scene centre
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const controls = get().controls as any;
      controls?.target?.set(0, 0, 0);
      controls?.update?.();
    } else {
      // ── Restore PerspectiveCamera ───────────────────────────────────────
      if (perspRef.current) {
        const { width, height } = get().size;
        perspRef.current.aspect = width / height;
        perspRef.current.updateProjectionMatrix();
        set({ camera: perspRef.current });
      }
    }

    invalidate();
    // set/get/invalidate are stable store references; orthoRef/perspRef are
    // refs — none need to be in the dep array.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [viewMode]);

  // ── Resize effect: keep ortho frustum correct when the canvas resizes ───
  useEffect(() => {
    if (viewMode !== "2D" || !orthoRef.current) return;
    const aspect = size.width / size.height;
    const viewH = 30;
    const ortho = orthoRef.current;
    ortho.left = (-aspect * viewH) / 2;
    ortho.right = (aspect * viewH) / 2;
    ortho.top = viewH / 2;
    ortho.bottom = -viewH / 2;
    ortho.updateProjectionMatrix();
    invalidate();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [size]);

  return null;
}
