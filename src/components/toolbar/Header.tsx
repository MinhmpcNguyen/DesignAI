"use client";

import { useState } from "react";
import ViewToggle from "./ViewToggle";
import { AiGenerateIcon, AppIcon } from "../icons";
import UndoRedoControls from "./UndoRedoControls";
import ZoomControl from "./ZoomControl";
import MoreInfo from "../views/DesignPage/MoreInfo";
import type { RefObject } from "react";
import type { CameraZoomHandle } from "../camera/CameraZoom";
import PriceDialog from "./PriceDialog";
import { useRouter } from "next/navigation";

interface HeaderProps {
  onAICapture: () => void;
  cameraZoomRef: RefObject<CameraZoomHandle | null>;
  isUIHidden?: boolean;
  onToggleUI?: () => void;
  onSave?: () => void;
  isSaving?: boolean;
  designTitle?: string;
}

export default function Header({
  onAICapture,
  cameraZoomRef,
  isUIHidden,
  onToggleUI,
  onSave,
  isSaving,
  designTitle,
}: HeaderProps) {
  const router = useRouter();
  const [isPriceDialogOpen, setIsPriceDialogOpen] = useState(false);

  const handleOpenPriceDialog = () => {
    setIsPriceDialogOpen(true);
  };

  const handleReturnToApp = () => {
    router.push("/project");
  };

  return (
    <header className="fixed top-0 left-0 right-0 z-50 h-14 bg-transparent flex items-center px-2">
      {/* App icon - Left side */}
      {!isUIHidden && (
        <div className="flex items-center">
          <div
            className="rounded-2xl w-12 h-12 bg-white flex items-center justify-center shadow-(--shadow-style) cursor-pointer"
            style={{ border: "var(--border-style)" }}
            onClick={handleReturnToApp}
          >
            <AppIcon width={24} height={24} />
          </div>
        </div>
      )}

      {/* Center controls - always centered on screen */}
      <div className="absolute left-1/2 top-0 bottom-0 transform -translate-x-1/2 flex items-center justify-center gap-3 h-full">
        {!isUIHidden && (
          <>
            <UndoRedoControls />
            <div
              className="bg-white flex items-center gap-2 px-2 py-1.5 rounded-xl shadow-(--shadow-style)"
              style={{ border: "var(--border-style)" }}
            >
              <ViewToggle />
              <button
                onClick={onAICapture}
                className="flex items-center gap-1 px-3 py-2 bg-(--primary-color) text-white rounded-xl text-sm font-light active:scale-95 transition-all select-none"
              >
                <AiGenerateIcon />
                <span>AI tạo ảnh</span>
              </button>
              <button
                onClick={handleOpenPriceDialog}
                className="flex items-center gap-1 px-3 py-2 bg-(--primary-color) text-white rounded-xl text-sm font-light active:scale-95 transition-all select-none"
              >
                <span>Báo giá</span>
              </button>
            </div>
          </>
        )}
        <ZoomControl
          cameraZoomRef={cameraZoomRef}
          isUIHidden={isUIHidden}
          onToggleUI={onToggleUI}
        />
      </div>

      {/* Apartment name, share icon, and user icon - right */}
      {!isUIHidden && (
        <div className="ml-auto">
          <MoreInfo
            onSave={onSave}
            isSaving={isSaving}
            designTitle={designTitle}
          />
        </div>
      )}

      <PriceDialog
        open={isPriceDialogOpen}
        onClose={() => setIsPriceDialogOpen(false)}
      />
    </header>
  );
}
