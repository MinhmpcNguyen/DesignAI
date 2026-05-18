"use client";

import { useThree } from "@react-three/fiber";
import { forwardRef, useImperativeHandle } from "react";

export interface ScreenshotCaptureHandle {
  capture: () => string | null;
}

/**
 * Invisible R3F child that exposes a `capture()` function via ref.
 * Must live inside <Canvas> to access useThree().
 * The Canvas must have `gl={{ preserveDrawingBuffer: true }}` for toDataURL()
 * to return the last rendered frame rather than a blank image.
 */
const ScreenshotCapture = forwardRef<ScreenshotCaptureHandle>((_, ref) => {
  const { gl } = useThree();

  useImperativeHandle(ref, () => ({
    capture: () => {
      const src = gl.domElement;
      const MAX_WIDTH = 1280;
      const scale = Math.min(1, MAX_WIDTH / src.width);
      const dstW = Math.round(src.width * scale);
      const dstH = Math.round(src.height * scale);

      const offscreen = document.createElement("canvas");
      offscreen.width = dstW;
      offscreen.height = dstH;
      offscreen.getContext("2d")!.drawImage(src, 0, 0, dstW, dstH);

      const dataUrl = offscreen.toDataURL("image/jpeg", 0.85);
      // const approxBytes = Math.round((dataUrl.length * 3) / 4);
      // console.log(`[ScreenshotCapture] ${src.width}×${src.height} → ${dstW}×${dstH} px, ~${approxBytes} bytes (JPEG 0.85)`);
      return dataUrl;
    },
  }));

  return null;
});

ScreenshotCapture.displayName = "ScreenshotCapture";
export default ScreenshotCapture;
