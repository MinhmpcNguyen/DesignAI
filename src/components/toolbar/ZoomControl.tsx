import type { RefObject } from "react";
import { FullScreenIcon, ZoomInIcon, ZoomOutIcon } from "../icons";
import VerticalDivide from "../VerticalDivide";
import type { CameraZoomHandle } from "../camera/CameraZoom";

interface ZoomControlProps {
  cameraZoomRef: RefObject<CameraZoomHandle | null>;
  isUIHidden?: boolean;
  onToggleUI?: () => void;
}

export default function ZoomControl({
  cameraZoomRef,
  isUIHidden,
  onToggleUI,
}: ZoomControlProps) {
  return (
    <div
      className="flex bg-white items-center p-3 rounded-xl shadow-(--shadow-style)"
      style={{ border: "var(--border-style)" }}
    >
      {!isUIHidden && (
        <>
          <button
            type="button"
            aria-label="Zoom In"
            title="Phóng to"
            onClick={() => cameraZoomRef.current?.zoomIn()}
            className="flex items-center justify-center cursor-pointer active:scale-95 active:opacity-80 transition-transform focus:outline-none"
          >
            <ZoomInIcon />
          </button>
          <VerticalDivide />
          <button
            type="button"
            aria-label="Zoom Out"
            title="Thu nhỏ"
            onClick={() => cameraZoomRef.current?.zoomOut()}
            className="flex items-center justify-center cursor-pointer active:scale-95 active:opacity-80 transition-transform focus:outline-none"
          >
            <ZoomOutIcon />
          </button>
          <VerticalDivide />
        </>
      )}
      <button
        type="button"
        aria-label="Full Screen"
        title={isUIHidden ? "Hiện giao diện" : "Ẩn giao diện"}
        onClick={onToggleUI}
        className="flex items-center justify-center cursor-pointer active:scale-95 active:opacity-80 transition-transform focus:outline-none"
      >
        <FullScreenIcon />
      </button>
    </div>
  );
}
