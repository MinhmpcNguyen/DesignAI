"use client";

import { useEffect, useRef } from "react";
import { useFrame, useThree } from "@react-three/fiber";
import { Vector3 } from "three";
import type { OrbitControls as OrbitControlsImpl } from "three-stdlib";
import { useIsAIGenMode } from "@/states/slices/view/hooks";

/**
 * Camera movement controls using WASD/Arrow keys
 *
 * Moves the OrbitControls target to pan the camera around the scene
 * Works alongside OrbitControls for rotation
 */
export default function CameraMovement() {
  const { invalidate } = useThree(); // only needed to kick off the first frame on keydown
  const keysPressed = useRef<Set<string>>(new Set());
  const isAIGenMode = useIsAIGenMode();

  // Movement speed (meters per second)
  const moveSpeed = 10;

  // Track key presses
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Only add movement keys, ignore if user is typing in an input
      if (
        e.target instanceof HTMLInputElement ||
        e.target instanceof HTMLTextAreaElement
      ) {
        return;
      }

      const key = e.key.toLowerCase();
      if (
        [
          "w",
          "a",
          "s",
          "d",
          "q",
          "e",
          "arrowup",
          "arrowdown",
          "arrowleft",
          "arrowright",
          "pageup",
          "pagedown",
        ].includes(key)
      ) {
        keysPressed.current.add(key);
        e.preventDefault(); // Prevent page scrolling with arrow keys
        invalidate(); // Trigger render in demand mode
      }
    };

    const handleKeyUp = (e: KeyboardEvent) => {
      const key = e.key.toLowerCase();
      keysPressed.current.delete(key);
    };

    // Reset keys on window blur (user switches tabs)
    const handleBlur = () => {
      keysPressed.current.clear();
    };

    window.addEventListener("keydown", handleKeyDown);
    window.addEventListener("keyup", handleKeyUp);
    window.addEventListener("blur", handleBlur);

    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      window.removeEventListener("keyup", handleKeyUp);
      window.removeEventListener("blur", handleBlur);
    };
  }, [invalidate]);

  // Update camera position each frame
  useFrame((state, delta) => {
    const { camera, controls, invalidate: frameInvalidate } = state;
    if (!controls || keysPressed.current.size === 0) return;

    // Calculate movement direction
    const moveDirection = new Vector3();
    const forward = new Vector3();
    const right = new Vector3();

    if (isAIGenMode) {
      // In AI mode: world-fixed axes so arrow keys always move in the same
      // direction regardless of which way the camera is facing.
      // Up = -Z (world north), Right = +X (world east)
      forward.set(0, 0, -1);
      right.set(1, 0, 0);
    } else {
      // Get camera's forward direction (projected onto XZ plane)
      camera.getWorldDirection(forward);
      forward.y = 0; // Keep movement on XZ plane only

      if (forward.lengthSq() < 0.0001) {
        // Camera is looking straight up or down (top-down 2D mode).
        // getWorldDirection → (0,±1,0) which zeros out after stripping Y.
        // Fall back to the camera's local-Y axis in world space (its "screen up"
        // direction), projected onto XZ — this keeps W/Up = world-forward (-Z)
        // and A/Left = world-left (-X) regardless of orthographic projection.
        forward.setFromMatrixColumn(camera.matrixWorld, 1);
        forward.y = 0;
      }

      forward.normalize();

      // Get camera's right direction
      right.crossVectors(forward, new Vector3(0, 1, 0)).normalize();
    }

    // Calculate movement based on pressed keys
    const keys = keysPressed.current;

    if (keys.has("arrowup")) {
      moveDirection.add(forward);
    }
    if (keys.has("arrowdown")) {
      moveDirection.sub(forward);
    }
    if (keys.has("arrowleft")) {
      moveDirection.sub(right);
    }
    if (keys.has("arrowright")) {
      moveDirection.add(right);
    }
    if (keys.has("e") || keys.has("pageup")) {
      moveDirection.y += 1; // Move camera up
    }
    if (keys.has("q") || keys.has("pagedown")) {
      moveDirection.y -= 1; // Move camera down
    }

    // Normalize and apply speed
    if (moveDirection.length() > 0) {
      moveDirection.normalize();
      moveDirection.multiplyScalar(moveSpeed * delta);

      // Move both camera and orbit target together
      camera.position.add(moveDirection);

      // Update OrbitControls target if available
      if (controls && "target" in controls) {
        const orbitControls = controls as OrbitControlsImpl;
        orbitControls.target.add(moveDirection);
        // Note: drei's OrbitControls calls update() on its own useFrame — no need to call it here
      }

      // Keep rendering while keys are pressed (for frameloop="demand" mode)
      frameInvalidate();
    }
  });

  return null; // This component doesn't render anything
}
