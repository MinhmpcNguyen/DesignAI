"use client";

import { memo } from "react";
import { Box } from "lucide-react";

interface ShapePreviewProps {
  shape: "model";
  color: string;
  size?: number;
  modelUrl?: string;
  /** Pre-rendered data URL from the offscreen renderer. Shows instead of swatch when ready. */
  thumbnailUrl?: string;
}

/** Shows a real 3D thumbnail (data URL) when available, falls back to color swatch + icon. */
const ShapePreview = memo(function ShapePreview({
  color,
  size = 60,
  thumbnailUrl,
}: ShapePreviewProps) {
  const iconSize = Math.round(size * 0.45);
  const containerStyle: React.CSSProperties = {
    width: "100%",
    height: "100%",
    borderRadius: "8px",
    flexShrink: 0,
    overflow: "hidden",
  };

  if (thumbnailUrl) {
    return (
      <div style={containerStyle}>
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={thumbnailUrl}
          alt=""
          style={{
            width: "100%",
            height: "100%",
            objectFit: "cover",
            /* Zoom thumbnail so it feels bigger inside the same container */
            transform: "scale(1.2)",
            transformOrigin: "center",
            display: "block",
          }}
        />
      </div>
    );
  }

  return (
    <div
      style={{
        ...containerStyle,
        background: color,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        opacity: 0.85,
      }}
    >
      <Box size={iconSize} color="#ffffff" strokeWidth={1.5} />
    </div>
  );
});

export default ShapePreview;
