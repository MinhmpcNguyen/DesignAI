"use client";

import { useFrame } from "@react-three/fiber";
import { useRef, useEffect } from "react";

/**
 * Performance monitoring component that tracks FPS and render times
 * Displays stats in the top-right corner
 */
export default function PerformanceMonitor() {
  const frameCount = useRef(0);
  const lastTime = useRef(0);

  // Initialize lastTime on mount
  useEffect(() => {
    lastTime.current = performance.now();
  }, []);

  useFrame((state, delta) => {
    frameCount.current++;
    const now = performance.now();

    // Update FPS every second
    if (now - lastTime.current >= 1000) {
      const currentFps = Math.round(
        (frameCount.current * 1000) / (now - lastTime.current),
      );

      // Log to console for debugging
      console.log(
        `🎮 Performance: ${currentFps} FPS | Frame time: ${Math.round(delta * 1000)}ms`,
      );

      frameCount.current = 0;
      lastTime.current = now;
    }
  });

  return null; // This component doesn't render 3D objects
}

/**
 * UI overlay to display performance stats
 */
export function PerformanceStats({
  fps,
  renderTime,
}: {
  fps: number;
  renderTime: number;
}) {
  const fpsColor = fps >= 55 ? "#00ff00" : fps >= 30 ? "#ffaa00" : "#ff0000";

  return (
    <div
      style={{
        position: "fixed",
        top: "10px",
        right: "10px",
        backgroundColor: "rgba(0, 0, 0, 0.7)",
        color: "white",
        padding: "10px 15px",
        borderRadius: "5px",
        fontFamily: "monospace",
        fontSize: "12px",
        zIndex: 1000,
        userSelect: "none",
      }}
    >
      <div style={{ color: fpsColor, fontWeight: "bold" }}>FPS: {fps}</div>
      <div style={{ color: "#aaa", fontSize: "10px" }}>
        Frame: {renderTime.toFixed(2)}ms
      </div>
    </div>
  );
}
