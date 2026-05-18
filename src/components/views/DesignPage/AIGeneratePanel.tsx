"use client";

import {
  forwardRef,
  type RefObject,
  useCallback,
  useEffect,
  useImperativeHandle,
  useRef,
  useState,
} from "react";
import {
  AlertCircle,
  Download,
  Loader2,
  RotateCcw,
  Shuffle,
  Sparkles,
  Wand2,
  X,
} from "lucide-react";
import type { ScreenshotCaptureHandle } from "../../tools/ScreenshotCapture";
import { useCreateSession } from "@/hooks/useSessions";
import { useUploadImage } from "@/hooks/useImages";
import { useJobStatus, useSubmitGeneration } from "@/hooks/useGenerate";
import {
  DefaultPrompts,
  PresetLightings,
  PresetSceneries,
  PresetStyles,
} from "@/constant";
import type { CameraAnglePreset, TPresets } from "@/types/global";
import type {
  CameraControlHandle,
  MinimapCameraState,
} from "@/components/camera/CameraController";
import MinimapPanel from "@/components/toolbar/MinimapPanel";
import { computeRoomCameraAngles } from "@/lib/cameraAngles";
import { useSelectedRoomKey } from "@/states/slices/floor/hooks";
import { useWalls } from "@/states/slices/walls/hooks";

export interface AIGeneratePanelHandle {
  triggerCapture: () => void;
  close: () => void;
}

interface Props {
  screenshotRef: RefObject<ScreenshotCaptureHandle | null>;
  cameraControlRef: RefObject<CameraControlHandle | null>;
  cameraState: MinimapCameraState;
  onOpenChange?: (open: boolean) => void;
}

interface GenerationJob {
  label: string;
  jobId: string;
  resultUrl: string | null;
}

interface PresetRowProps {
  label: string;
  items: TPresets[];
  selected: string | null;
  onSelect: (key: string | null) => void;
  disabled?: boolean;
}

function PresetRow({
  label,
  items,
  selected,
  onSelect,
  disabled,
}: PresetRowProps) {
  return (
    <div className="space-y-2">
      <span className="text-[10px] font-semibold text-(--sub-color) uppercase tracking-widest">
        {label}
      </span>
      <div className="flex flex-wrap gap-2">
        {items.map((item) => {
          const isActive = selected === item.key;
          return (
            <button
              key={item.key}
              onClick={() => onSelect(isActive ? null : item.key)}
              disabled={disabled}
              title={item.label}
              className={`flex flex-col cursor-pointer items-center gap-1 rounded-lg border-2 p-1 transition-colors disabled:opacity-40 ${
                isActive
                  ? "border-(--primary-color)"
                  : "border-transparent hover:border-(--primary-color)/40"
              }`}
            >
              <div className="w-16 h-12 rounded bg-(--sub-color) overflow-hidden flex items-center justify-center">
                {item.imgUrl ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={item.imgUrl}
                    alt={item.label}
                    className="w-full h-full object-cover"
                  />
                ) : (
                  <span className="text-[8px] text-white text-center leading-tight px-1">
                    {item.label}
                  </span>
                )}
              </div>
              <span className="text-[9px] w-16 truncate leading-tight text-center">
                {item.label}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

const AIGeneratePanel = forwardRef<AIGeneratePanelHandle, Props>(
  function AIGeneratePanel(
    { screenshotRef, cameraControlRef, cameraState, onOpenChange },
    ref,
  ) {
    const [isOpen, setIsOpen] = useState(false);
    const [prompt, setPrompt] = useState("");
    const [jobId, setJobId] = useState<string | undefined>();
    const [submitError, setSubmitError] = useState<string | null>(null);
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [selectedLighting, setSelectedLighting] = useState<string | null>(
      null,
    );
    const [selectedStyle, setSelectedStyle] = useState<string | null>(null);
    const [selectedScenery, setSelectedScenery] = useState<string | null>(null);
    const [resultUrl, setResultUrl] = useState<string | null>(null);
    // Multi-angle jobs
    const [jobs, setJobs] = useState<GenerationJob[]>([]);
    // Camera angle presets
    const [cameraAngles, setCameraAngles] = useState<CameraAnglePreset[]>([]);
    const [activeAngleIdx, setActiveAngleIdx] = useState(0);

    const { mutateAsync: createSession } = useCreateSession();
    const { mutateAsync: uploadImage } = useUploadImage();
    const { mutateAsync: submitGeneration } = useSubmitGeneration();
    const { data: jobStatus } = useJobStatus(jobId);

    // ── Context for camera angle computation ────────────────────────────
    const walls = useWalls();
    const selectedRoomKey = useSelectedRoomKey();

    // ── Fixed-slot polling for multi-angle jobs (max 6) ─────────────────
    const { data: s0 } = useJobStatus(jobs[0]?.jobId);
    const { data: s1 } = useJobStatus(jobs[1]?.jobId);
    const { data: s2 } = useJobStatus(jobs[2]?.jobId);
    const { data: s3 } = useJobStatus(jobs[3]?.jobId);
    const { data: s4 } = useJobStatus(jobs[4]?.jobId);
    const { data: s5 } = useJobStatus(jobs[5]?.jobId);

    const isMultiMode = jobs.length > 0;
    const multiStatuses = [s0, s1, s2, s3, s4, s5];

    // Single-mode derived state (unchanged behaviour)
    const isDone =
      !isMultiMode && (!!resultUrl || jobStatus?.status === "completed");
    const isFailed = !isMultiMode && !!jobId && jobStatus?.status === "failed";
    const isGenerating =
      isSubmitting ||
      (isMultiMode
        ? jobs.some(
            (job, i) => !job.resultUrl && multiStatuses[i]?.status !== "failed",
          )
        : !!jobId && !isDone && !isFailed);
    const error = isFailed ? "Tạo thất bại. Vui lòng thử lại." : submitError;
    const finalResultUrl =
      resultUrl ??
      (jobStatus?.status === "completed"
        ? (jobStatus.result_url ?? null)
        : null);

    // Multi-mode: all jobs settled (completed or failed)
    const multiAllSettled =
      isMultiMode &&
      !isSubmitting &&
      jobs.every(
        (job, i) =>
          job.resultUrl !== null || multiStatuses[i]?.status === "failed",
      );

    // How many angles are selected (for overlay copy)
    const selectedAnglesCount = cameraAngles.filter((a) => a.selected).length;

    useImperativeHandle(ref, () => ({
      triggerCapture: () => {
        setPrompt(
          DefaultPrompts[Math.floor(Math.random() * DefaultPrompts.length)],
        );
        setSubmitError(null);
        setJobId(undefined);
        setResultUrl(null);
        setJobs([]);
        setIsSubmitting(false);
        onOpenChange?.(true);
        setIsOpen(true);
      },
      close: handleClose,
    }));

    const handleClose = () => {
      onOpenChange?.(false);
      setIsOpen(false);
      setPrompt("");
      setSubmitError(null);
      setJobId(undefined);
      setResultUrl(null);
      setJobs([]);
      setCameraAngles([]);
      setActiveAngleIdx(0);
      setIsSubmitting(false);
      setSelectedLighting(null);
      setSelectedStyle(null);
      setSelectedScenery(null);
    };

    // ── Compute camera angles when panel opens or room/walls change ─────
    useEffect(() => {
      if (!isOpen) return;
      setCameraAngles(computeRoomCameraAngles(walls, selectedRoomKey));
      setActiveAngleIdx(0);
    }, [isOpen, walls, selectedRoomKey]);

    // ── Sync multi-angle job result URLs as polling completes ────────────
    useEffect(() => {
      const statuses = [s0, s1, s2, s3, s4, s5];
      setJobs((prev) => {
        if (prev.length === 0) return prev;
        let changed = false;
        const updated = prev.map((job, i) => {
          const status = statuses[i];
          if (
            status?.status === "completed" &&
            status.result_url &&
            !job.resultUrl
          ) {
            changed = true;
            return { ...job, resultUrl: status.result_url };
          }
          return job;
        });
        return changed ? updated : prev;
      });
    }, [s0, s1, s2, s3, s4, s5]);

    // Capture screenshot(s) and run the generation pipeline
    const handleRender = async () => {
      const selectedAngles = cameraAngles.filter((a) => a.selected);

      setSubmitError(null);
      setJobId(undefined);
      setResultUrl(null);
      setJobs([]);
      setIsSubmitting(true);

      if (selectedAngles.length === 0) {
        // ── Single capture (existing behaviour) ────────────────────────
        try {
          const url = screenshotRef.current?.capture() ?? null;
          if (!url) return;
          const blob = await fetch(url).then((r) => r.blob());
          const file = new File([blob], "screenshot.jpg", {
            type: "image/jpeg",
          });
          const sessionRes = await createSession({});
          const sessionId = sessionRes.data.session_id;
          await uploadImage({ sessionId, body: { file } });
          const gen = await submitGeneration({
            sessionId,
            body: {
              prompt: prompt.trim() || DefaultPrompts[0],
              lighting: selectedLighting ?? undefined,
              style: selectedStyle ?? undefined,
              scenery: selectedScenery ?? undefined,
            },
          });
          setJobId(gen.job_id);
        } catch (err) {
          setSubmitError(err instanceof Error ? err.message : "Đã xảy ra lỗi");
        } finally {
          setIsSubmitting(false);
        }
        return;
      }

      // ── Multi-angle capture ──────────────────────────────────────────
      const newJobs: GenerationJob[] = [];
      try {
        for (const angle of selectedAngles) {
          // Apply camera preset to the live 3D scene
          cameraControlRef.current?.setCameraXZ(angle.x, angle.z);
          cameraControlRef.current?.setHeight(angle.y);
          cameraControlRef.current?.setAzimuth(angle.azimuth);
          cameraControlRef.current?.setElevation(angle.elevation);
          cameraControlRef.current?.setFov(angle.fov);

          // Wait for Three.js to re-render the frame before capturing
          await new Promise<void>((resolve) => setTimeout(resolve, 150));

          const url = screenshotRef.current?.capture() ?? null;
          if (!url) continue;

          const blob = await fetch(url).then((r) => r.blob());
          const file = new File([blob], `screenshot-${angle.id}.jpg`, {
            type: "image/jpeg",
          });
          const sessionRes = await createSession({});
          const sessionId = sessionRes.data.session_id;
          await uploadImage({ sessionId, body: { file } });
          const gen = await submitGeneration({
            sessionId,
            body: {
              prompt: prompt.trim() || DefaultPrompts[0],
              lighting: selectedLighting ?? undefined,
              style: selectedStyle ?? undefined,
              scenery: selectedScenery ?? undefined,
            },
          });
          newJobs.push({
            label: angle.label,
            jobId: gen.job_id,
            resultUrl: null,
          });
        }
      } catch (err) {
        setSubmitError(err instanceof Error ? err.message : "Đã xảy ra lỗi");
      } finally {
        setIsSubmitting(false);
        if (newJobs.length > 0) setJobs(newJobs);
      }
    };

    // Keep resultUrl in sync with polling once completed
    if (
      jobStatus?.status === "completed" &&
      jobStatus.result_url &&
      !resultUrl
    ) {
      setResultUrl(jobStatus.result_url);
    }

    const handleDownload = () => {
      if (!finalResultUrl) return;
      window.open(finalResultUrl, "_blank", "noopener,noreferrer");
    };

    // ── Drag: look-around on center panel ───────────────────────────────────
    const centerDragRef = useRef<{
      startX: number;
      startY: number;
      startAzimuth: number;
      startElevation: number;
    } | null>(null);

    const handleCenterPointerDown = useCallback(
      (e: React.PointerEvent<HTMLDivElement>) => {
        // Don't capture drag when result image is displayed
        if (finalResultUrl) return;
        e.currentTarget.setPointerCapture(e.pointerId);
        centerDragRef.current = {
          startX: e.clientX,
          startY: e.clientY,
          startAzimuth: cameraState.azimuth,
          startElevation: cameraState.elevation,
        };
      },
      [finalResultUrl, cameraState.azimuth, cameraState.elevation],
    );

    const handleCenterPointerMove = useCallback(
      (e: React.PointerEvent<HTMLDivElement>) => {
        if (!centerDragRef.current) return;
        const { startX, startY, startAzimuth, startElevation } =
          centerDragRef.current;
        const deltaX = e.clientX - startX;
        const deltaY = e.clientY - startY;
        cameraControlRef.current?.setAzimuth(startAzimuth + deltaX * 0.005);
        cameraControlRef.current?.setElevation(
          Math.max(-89, Math.min(89, startElevation - deltaY * 0.3)),
        );
      },
      [cameraControlRef],
    );

    const handleCenterPointerUp = useCallback(() => {
      centerDragRef.current = null;
    }, []);

    if (!isOpen) return null;

    return (
      <div className="fixed inset-0 z-50 flex" style={{ userSelect: "none" }}>
        {/* ── Left column: prompt + presets ───────────────────────────── */}
        <div className="w-72 shrink-0 bg-white flex flex-col overflow-y-auto border-r border-gray-200">
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100 shrink-0">
            <div className="flex items-center gap-2">
              <Sparkles size={14} className="text-(--secondary-color)" />
              <span className="text-sm font-semibold text-(--secondary-color)">
                Diễn họa với AI
              </span>
            </div>
            <button
              onClick={handleClose}
              className="p-1 rounded-md text-(--sub-color) hover:bg-gray-100 transition-colors cursor-pointer"
              aria-label="Đóng"
            >
              <X size={14} />
            </button>
          </div>

          {/* Prompt */}
          <div className="px-4 pt-4 pb-3 space-y-2 border-b border-gray-100 shrink-0">
            <div className="flex items-center justify-between">
              <label className="text-[10px] font-semibold text-(--sub-color) uppercase tracking-widest">
                Câu lệnh (Prompt)
              </label>
              <button
                onClick={() =>
                  setPrompt(
                    DefaultPrompts[
                      Math.floor(Math.random() * DefaultPrompts.length)
                    ],
                  )
                }
                disabled={isGenerating}
                className="flex items-center gap-1 text-[10px] text-(--sub-color) hover:text-(--primary-color) transition-colors disabled:opacity-40 cursor-pointer"
              >
                <Shuffle size={10} />
                Ngẫu nhiên
              </button>
            </div>
            <textarea
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              onKeyDown={(e) => e.stopPropagation()}
              disabled={isGenerating || isDone}
              placeholder="Mô tả phong cách, ánh sáng..."
              className="w-full h-30 px-3 py-2 text-xs text-(--secondary-color) placeholder-(--sub-color) border border-(--sub-color)/30 rounded-lg outline-none focus:border-(--sub-color) resize-none disabled:opacity-50 transition-colors"
            />

            {/* Error */}
            {error && (
              <div className="flex items-start gap-2 px-3 py-2 bg-red-50 border border-red-200 rounded-lg">
                <AlertCircle
                  size={12}
                  className="text-red-500 shrink-0 mt-0.5"
                />
                <p className="text-xs text-red-600 leading-snug">{error}</p>
              </div>
            )}
          </div>

          {/* Presets */}
          <div className="flex-1 overflow-y-auto px-4 py-4 space-y-5">
            <PresetRow
              label="Ánh sáng"
              items={PresetLightings}
              selected={selectedLighting}
              onSelect={setSelectedLighting}
              disabled={isGenerating || isDone}
            />
            <PresetRow
              label="Phong cách"
              items={PresetStyles}
              selected={selectedStyle}
              onSelect={setSelectedStyle}
              disabled={isGenerating || isDone}
            />
            <PresetRow
              label="Cảnh nền"
              items={PresetSceneries}
              selected={selectedScenery}
              onSelect={setSelectedScenery}
              disabled={isGenerating || isDone}
            />
          </div>
        </div>

        {/* ── Center: transparent — 3D scene visible through ──────────── */}
        {/* Drag left/right = azimuth; drag up/down = elevation; position unchanged */}
        <div
          className={`flex-1 relative flex flex-col items-center justify-end pb-2 pointer-events-auto${!finalResultUrl ? " cursor-grab active:cursor-grabbing" : ""}`}
          onPointerDown={handleCenterPointerDown}
          onPointerMove={handleCenterPointerMove}
          onPointerUp={handleCenterPointerUp}
        >
          {/* Single-mode result overlay */}
          {!isMultiMode && finalResultUrl && (
            <div className="absolute inset-0 flex items-center justify-center bg-black/60 pointer-events-auto">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={finalResultUrl}
                alt="AI enhanced result"
                className="max-w-full max-h-full object-contain"
                referrerPolicy="no-referrer"
              />
            </div>
          )}

          {/* Generating overlay */}
          {isGenerating && (
            <div className="absolute inset-0 flex flex-col items-center justify-center bg-black/20 pointer-events-none gap-3">
              <Loader2 size={32} className="text-white animate-spin" />
              <span className="text-white text-sm font-medium">
                {isSubmitting && selectedAnglesCount > 0
                  ? `Đang chụp ${selectedAnglesCount} góc…`
                  : isSubmitting
                    ? "Đang tải lên…"
                    : "Đang tạo ảnh…"}
              </span>
              {!isMultiMode && jobId && (
                <div className="w-48 h-1 bg-white/30 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-white rounded-full transition-all duration-700"
                    style={{
                      width:
                        jobStatus?.status === "processing"
                          ? "66%"
                          : jobStatus?.status === "completed"
                            ? "100%"
                            : "33%",
                    }}
                  />
                </div>
              )}
            </div>
          )}

          {/* Multi-angle result cards */}
          {isMultiMode && !isSubmitting && (
            <div className="absolute bottom-16 left-0 right-0 px-4 pointer-events-auto">
              <div className="flex gap-3 overflow-x-auto pb-2 [scrollbar-width:thin]">
                {jobs.map((job, i) => {
                  const status = multiStatuses[i];
                  const isJobDone = !!job.resultUrl;
                  const isJobFailed =
                    !job.resultUrl && status?.status === "failed";
                  return (
                    <div
                      key={job.jobId}
                      className="shrink-0 w-40 bg-white/90 rounded-xl overflow-hidden shadow-lg flex flex-col"
                    >
                      <div className="h-28 bg-gray-100 flex items-center justify-center relative">
                        {isJobDone ? (
                          // eslint-disable-next-line @next/next/no-img-element
                          <img
                            src={job.resultUrl!}
                            alt={job.label}
                            className="w-full h-full object-cover"
                            referrerPolicy="no-referrer"
                          />
                        ) : isJobFailed ? (
                          <AlertCircle size={20} className="text-red-400" />
                        ) : (
                          <Loader2
                            size={20}
                            className="text-(--primary-color) animate-spin"
                          />
                        )}
                      </div>
                      <div className="flex items-center justify-between px-2 py-1.5 gap-1">
                        <span className="text-[9px] font-semibold text-(--secondary-color) truncate">
                          {job.label}
                        </span>
                        {isJobDone && (
                          <button
                            onClick={() =>
                              window.open(
                                job.resultUrl!,
                                "_blank",
                                "noopener,noreferrer",
                              )
                            }
                            className="shrink-0 p-1 rounded hover:bg-gray-100 transition-colors cursor-pointer"
                            aria-label="Tải xuống"
                          >
                            <Download
                              size={11}
                              className="text-(--primary-color)"
                            />
                          </button>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Action buttons — re-enable pointer events */}
          <div
            className="pointer-events-auto flex gap-3 relative z-10"
            onPointerDown={(e) => e.stopPropagation()}
          >
            {/* Single-mode: Tạo ảnh */}
            {!isMultiMode && !isDone && !isGenerating && (
              <button
                onClick={() => handleRender()}
                disabled={!prompt.trim()}
                className="flex items-center gap-2 px-6 py-2.5 bg-(--primary-color) text-white rounded-xl text-sm font-medium shadow-lg hover:bg-(--secondary-color) transition-colors disabled:opacity-40 disabled:cursor-not-allowed active:scale-95 cursor-pointer"
              >
                <Wand2 size={14} />
                Tạo ảnh
              </button>
            )}

            {/* Single-mode: Done */}
            {!isMultiMode && isDone && (
              <>
                <button
                  onClick={handleDownload}
                  className="flex items-center gap-2 px-5 py-2.5 bg-(--primary-color) text-white rounded-xl text-sm font-medium shadow-lg hover:bg-(--secondary-color) transition-colors active:scale-95"
                >
                  <Download size={14} />
                  Tải xuống
                </button>
                <button
                  onClick={handleClose}
                  className="flex items-center gap-2 px-5 py-2.5 bg-white/90 text-(--secondary-color) rounded-xl text-sm font-medium shadow-lg hover:bg-white transition-colors active:scale-95"
                >
                  <RotateCcw size={14} />
                  Chụp lại
                </button>
              </>
            )}

            {/* Multi-mode: Tạo ảnh (not yet captured) — shown before first run */}
            {isMultiMode && !isGenerating && !multiAllSettled && (
              <button
                onClick={() => handleRender()}
                disabled={!prompt.trim()}
                className="flex items-center gap-2 px-6 py-2.5 bg-(--primary-color) text-white rounded-xl text-sm font-medium shadow-lg hover:bg-(--secondary-color) transition-colors disabled:opacity-40 disabled:cursor-not-allowed active:scale-95 cursor-pointer"
              >
                <Wand2 size={14} />
                Tạo lại
              </button>
            )}

            {/* Multi-mode: All done */}
            {isMultiMode && multiAllSettled && (
              <button
                onClick={handleClose}
                className="flex items-center gap-2 px-5 py-2.5 bg-white/90 text-(--secondary-color) rounded-xl text-sm font-medium shadow-lg hover:bg-white transition-colors active:scale-95"
              >
                <RotateCcw size={14} />
                Chụp lại
              </button>
            )}
          </div>
        </div>

        {/* ── Right column: camera controls ───────────────────────────── */}
        <div className="w-72 shrink-0 bg-transparent flex flex-col py-3 mr-2">
          <div className="flex-1 overflow-y-auto [scrollbar-width:none] [-ms-overflow-style:none] [&::-webkit-scrollbar]:hidden">
            <MinimapPanel
              className="w-full"
              cameraControlRef={cameraControlRef}
              cameraState={cameraState}
              cameraAngles={cameraAngles}
              activeAngleIdx={activeAngleIdx}
              onNavigate={(delta) => {
                // Snapshot live camera into the current angle before leaving
                // so manual adjustments survive round-trips between presets.
                setCameraAngles((prev) =>
                  prev.map((a, i) =>
                    i === activeAngleIdx
                      ? {
                          ...a,
                          x: cameraState.x,
                          z: cameraState.z,
                          y: cameraState.y,
                          azimuth: cameraState.azimuth,
                          elevation: cameraState.elevation,
                          fov: cameraState.fov,
                        }
                      : a,
                  ),
                );
                const next =
                  (activeAngleIdx + delta + cameraAngles.length) %
                  cameraAngles.length;
                setActiveAngleIdx(next);
                const angle = cameraAngles[next];
                if (!angle) return;
                cameraControlRef.current?.setCameraXZ(angle.x, angle.z);
                cameraControlRef.current?.setHeight(angle.y);
                cameraControlRef.current?.setAzimuth(angle.azimuth);
                cameraControlRef.current?.setElevation(angle.elevation);
                cameraControlRef.current?.setFov(angle.fov);
              }}
              onToggleSelect={(idx) => {
                setCameraAngles((prev) =>
                  prev.map((a, i) =>
                    i === idx ? { ...a, selected: !a.selected } : a,
                  ),
                );
              }}
            />
          </div>
        </div>
      </div>
    );
  },
);

AIGeneratePanel.displayName = "AIGeneratePanel";
export default AIGeneratePanel;
