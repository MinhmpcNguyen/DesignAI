"use client";

import AuthGuard from "@/components/AuthGuard";
import type {
  CameraControlHandle,
  MinimapCameraState,
} from "@/components/camera/CameraController";
import type { CameraZoomHandle } from "@/components/camera/CameraZoom";
import KeyboardControls from "@/components/KeyboardControls";
import Footer from "@/components/toolbar/Footer";
import Header from "@/components/toolbar/Header";
import type { ScreenshotCaptureHandle } from "@/components/tools/ScreenshotCapture";
import AIGeneratePanel, {
  type AIGeneratePanelHandle,
} from "@/components/views/DesignPage/AIGeneratePanel";
import FloorStylePanel from "@/components/views/DesignPage/FloorStylePanel";
import MenuOptions from "@/components/views/DesignPage/MenuOptions";
import ProjectSidebarPanel from "@/components/views/DesignPage/ProjectSidebarPanel";
import RoomTemplateSelector from "@/components/views/DesignPage/RoomTemplateSelector";
import SelectedObjectOverlay from "@/components/views/DesignPage/SelectedObjectOverlay";
import SelectedWallOverlay from "@/components/views/DesignPage/SelectedWallOverlay";
import { useFloorMaterials } from "@/hooks/useCatalog";
import { useLoadDesign, useSaveDesign } from "@/hooks/useDesign";
import {
  centroidKey,
  computeTotalFloorArea,
  findRoomPolygons,
} from "@/lib/roomPolygons";
import { enableThumbnailRenderer } from "@/lib/thumbnailRenderer";
import { useObjectsValue } from "@/states/slices/objects/hooks";
import {
  useSelectionValue,
  useSetSelectedId,
} from "@/states/slices/selection/hooks";
import {
  useSetViewMode,
  useIsAIGenMode,
  useSetIsAIGenMode,
} from "@/states/slices/view/hooks";
import {
  useSelectedWallId,
  useSelectWall,
} from "@/states/slices/wallEditor/hooks";
import {
  useGlobalMaterialId,
  useRoomDescriptions,
  useRoomMaterials,
  useRoomNames,
  useSelectedRoomKey,
} from "@/states/slices/floor/hooks";
import { useWalls } from "@/states/slices/walls/hooks";
import { Loader2 } from "lucide-react";
import dynamic from "next/dynamic";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useLayoutEffect, useRef, useState } from "react";

const DesignSceneCanvas = dynamic(
  () => import("@/components/views/DesignPage/DesignSceneCanvas"),
  {
    ssr: false,
  },
);

const FurnitureCatalogOverlay = dynamic(
  () =>
    import("@/components/views/DesignPage/furniture-catalog/FurnitureCatalogOverlay"),
  {
    ssr: false,
  },
);

const GroupOverlay = dynamic(
  () => import("@/components/views/DesignPage/GroupOverlay"),
  {
    ssr: false,
  },
);

function DesignPageInner() {
  const searchParams = useSearchParams();
  const designId = searchParams.get("id") ?? undefined;
  const designTitle = searchParams.get("title") ?? undefined;
  const screenshotRef = useRef<ScreenshotCaptureHandle | null>(null);

  // Suspend the offscreen thumbnail renderer for the entire lifetime of this
  // page so it cannot compete with R3F's WebGL context (browser limit ~8-16).
  // enableThumbnailRenderer is called on unmount so the home/project pages
  // can render thumbnails again after the user navigates away.
  useLayoutEffect(() => {
    return enableThumbnailRenderer;
  }, []);
  const panelRef = useRef<AIGeneratePanelHandle | null>(null);
  const cameraZoomRef = useRef<CameraZoomHandle | null>(null);
  const cameraControlRef = useRef<CameraControlHandle | null>(null);

  const { objects } = useObjectsValue();
  const { mutateAsync: saveDesign, isPending: isSavingDesign } =
    useSaveDesign();

  const [cameraState, setCameraState] = useState<MinimapCameraState>({
    x: 15,
    y: 15,
    z: 15,
    targetX: 0,
    targetZ: 0,
    azimuth: Math.PI / 4, // matches initial camera position [15,15,15]
    elevation: 45,
    fov: 60,
  });
  const [activeMenu, setActiveMenu] = useState<string | null>("floor-plan");
  const isAIGenMode = useIsAIGenMode();
  const setIsAIGenMode = useSetIsAIGenMode();
  const [isUIHidden, setIsUIHidden] = useState(false);

  const { selectedIds } = useSelectionValue();
  const { isLoading: loadingDesign } = useLoadDesign(designId);
  const selectedWallId = useSelectedWallId();
  const setSelectedId = useSetSelectedId();
  const selectWall = useSelectWall();
  const setViewMode = useSetViewMode();
  const walls = useWalls();
  const selectedRoomKey = useSelectedRoomKey();
  const roomMaterials = useRoomMaterials();
  const roomNames = useRoomNames();
  const roomDescriptions = useRoomDescriptions();
  const globalMaterialId = useGlobalMaterialId();
  const { floorMaterials } = useFloorMaterials();
  const catalogOpen = activeMenu === "products";
  const templatePanelOpen = activeMenu === "floor-plan";
  const projectPanelOpen = activeMenu === "project";
  // Derive whether the tool panel should be open from either the
  // active menu or a currently-selected room key. This avoids
  // synchronously calling `setState` inside an effect and prevents
  // cascading renders.
  // When another panel is explicitly active, the tool panel stays closed
  // even if a room is selected — it only reopens once the other panel closes.
  const toolPanelOpen =
    activeMenu === "tool" ||
    (Boolean(selectedRoomKey) &&
      !catalogOpen &&
      !templatePanelOpen &&
      !projectPanelOpen);

  // Close AI panel when an object or wall is selected
  useEffect(() => {
    if (selectedIds.size > 0 || selectedWallId) {
      panelRef.current?.close();
    }
  }, [selectedIds, selectedWallId]);

  // Mutual exclusion: selecting a wall clears any selected object
  useEffect(() => {
    if (selectedWallId) {
      setSelectedId(null);
    }
  }, [selectedWallId]); // eslint-disable-line react-hooks/exhaustive-deps

  // Mutual exclusion: selecting an object clears any selected wall
  useEffect(() => {
    if (selectedIds.size > 0) {
      selectWall(null);
    }
  }, [selectedIds]); // eslint-disable-line react-hooks/exhaustive-deps

  // Auto-open Floor Style Panel when a room floor is selected
  // Previously this effect synchronously called `setActiveMenu("tool")`
  // when `selectedRoomKey` changed. That caused React's warning about
  // synchronous setState in effects and could trigger cascading renders.
  // We now derive `toolPanelOpen` from `selectedRoomKey` instead, so no
  // effect is necessary.

  // TEMP: Press Shift+E to export current design as a RoomTemplate to the console
  // useEffect(() => {
  //   const handler = (e: KeyboardEvent) => {
  //     if (!e.shiftKey || e.key !== "E") return;
  //     const polygons: [number, number][][] = findRoomPolygons(walls);
  //     const rooms = polygons.map((polygon, i) => {
  //       const key = centroidKey(polygon);
  //       const materialId = roomMaterials[key] ?? globalMaterialId;
  //       return {
  //         key,
  //         name: roomNames[key] ?? `Phòng ${i + 1}`,
  //         polygons: polygon,
  //         materialId,
  //         description: roomDescriptions[key] ?? "",
  //         materialLabel:
  //           floorMaterials.find((m) => m.id === materialId)?.label ?? "",
  //       };
  //     });
  //     const template = {
  //       id: `custom-${Date.now()}`,
  //       name: "My Design",
  //       description: "",
  //       area: computeTotalFloorArea(walls),
  //       polygon: polygons,
  //       rooms,
  //       walls,
  //       objects: objects.map((obj) => {
  //         const { id, ...rest } = obj;
  //         void id;
  //         return rest;
  //       }),
  //     };
  //     console.log("=== ROOM TEMPLATE ===");
  //     console.log(JSON.stringify(template, null, 2));
  //   };
  //   window.addEventListener("keydown", handler);
  //   return () => window.removeEventListener("keydown", handler);
  // }, [
  //   walls,
  //   objects,
  //   roomMaterials,
  //   roomNames,
  //   roomDescriptions,
  //   globalMaterialId,
  //   floorMaterials,
  // ]);

  const handleSave = designId
    ? async () => {
        const polygons = findRoomPolygons(walls);
        const rooms = polygons.map((polygon, i) => {
          const key = centroidKey(polygon);
          const materialId = roomMaterials[key] ?? globalMaterialId;
          return {
            key,
            name: roomNames[key] ?? `Phòng ${i + 1}`,
            polygons: polygon,
            materialId,
            description: roomDescriptions[key] ?? "",
            materialLabel:
              floorMaterials.find((m) => m.id === materialId)?.label ?? "",
          };
        });
        await saveDesign({
          designId,
          payload: {
            walls: walls as unknown as Record<string, unknown>[],
            objects: objects as unknown as Record<string, unknown>[],
            polygon: polygons,
            area: computeTotalFloorArea(walls) ?? undefined,
            rooms,
          },
        });
      }
    : undefined;

  // Keep refs fresh so the auto-save interval always reads the latest scene
  // without needing walls/objects in the interval's dependency array.
  const wallsRef = useRef(walls);
  const objectsRef = useRef(objects);
  const roomMaterialsRef = useRef(roomMaterials);
  const roomNamesRef = useRef(roomNames);
  const roomDescriptionsRef = useRef(roomDescriptions);
  const globalMaterialIdRef = useRef(globalMaterialId);
  const floorMaterialsRef = useRef(floorMaterials);
  useEffect(() => {
    wallsRef.current = walls;
  }, [walls]);
  useEffect(() => {
    objectsRef.current = objects;
  }, [objects]);
  useEffect(() => {
    roomMaterialsRef.current = roomMaterials;
  }, [roomMaterials]);
  useEffect(() => {
    roomNamesRef.current = roomNames;
  }, [roomNames]);
  useEffect(() => {
    roomDescriptionsRef.current = roomDescriptions;
  }, [roomDescriptions]);
  useEffect(() => {
    globalMaterialIdRef.current = globalMaterialId;
  }, [globalMaterialId]);
  useEffect(() => {
    floorMaterialsRef.current = floorMaterials;
  }, [floorMaterials]);

  // Reset camera to eye-level when AI mode opens.
  // Must run as a useEffect so CameraReset's effect (a deep child) has already
  // switched R3F's active camera to PerspectiveCamera before we issue resets.
  // React runs children effects before parent effects, so this fires after
  // CameraReset has swapped back to the PerspectiveCamera.
  useEffect(() => {
    if (!isAIGenMode) return;
    const w = wallsRef.current;
    const xs = w.flatMap((wall) => [wall.startPoint[0], wall.endPoint[0]]);
    const zs = w.flatMap((wall) => [wall.startPoint[1], wall.endPoint[1]]);
    const cx = xs.length ? (Math.min(...xs) + Math.max(...xs)) / 2 : 0;
    const cz = zs.length ? (Math.min(...zs) + Math.max(...zs)) / 2 : 0;
    cameraControlRef.current?.setCameraXZ(cx, cz);
    cameraControlRef.current?.setHeight(1.6);
    cameraControlRef.current?.setAzimuth(0);
    cameraControlRef.current?.setElevation(0);
  }, [isAIGenMode]);

  // Auto-save every 5 minutes when a designId is present.
  // Interval is stable — only recreated when designId changes.
  useEffect(() => {
    if (!designId) return;
    const interval = setInterval(
      async () => {
        const w = wallsRef.current;
        const polygons = findRoomPolygons(w);
        const rooms = polygons.map((polygon, i) => {
          const key = centroidKey(polygon);
          const materialId =
            roomMaterialsRef.current[key] ?? globalMaterialIdRef.current;
          return {
            key,
            name: roomNamesRef.current[key] ?? `Phòng ${i + 1}`,
            polygons: polygon,
            materialId,
            description: roomDescriptionsRef.current[key] ?? "",
            materialLabel:
              floorMaterialsRef.current.find((m) => m.id === materialId)
                ?.label ?? "",
          };
        });
        await saveDesign({
          designId,
          payload: {
            walls: w as unknown as Record<string, unknown>[],
            objects: objectsRef.current as unknown as Record<string, unknown>[],
            polygon: polygons,
            area: computeTotalFloorArea(w) ?? undefined,
            rooms,
          },
        });
      },
      5 * 60 * 1000,
    );
    return () => clearInterval(interval);
  }, [designId, saveDesign]);

  return (
    <AuthGuard>
      <div className="w-full h-screen overflow-hidden">
        <KeyboardControls />
        {loadingDesign && (
          <div className="pointer-events-none absolute top-3 right-3 z-60 rounded-full bg-black/60 px-3 py-1.5 text-xs text-white backdrop-blur-sm">
            <span className="flex items-center gap-1.5">
              <Loader2 className="size-3.5 animate-spin" />
              Loading design...
            </span>
          </div>
        )}

        {!isAIGenMode && (
          <>
            {/* Room Template Selector drawer */}
            <RoomTemplateSelector
              open={templatePanelOpen}
              onOpenChange={(o) => {
                if (!o) setActiveMenu(null);
              }}
              onApplySuccess={() => setActiveMenu("products")}
            />

            {/* Header */}
            <Header
              onAICapture={() => {
                setSelectedId(null);
                selectWall(null);
                setActiveMenu(null);
                setViewMode("3D");
                panelRef.current?.triggerCapture();
              }}
              cameraZoomRef={cameraZoomRef}
              isUIHidden={isUIHidden}
              onToggleUI={() => setIsUIHidden((v) => !v)}
              onSave={handleSave}
              isSaving={isSavingDesign}
              designTitle={designTitle}
            />

            {/* Footer */}
            <Footer isUIHidden={isUIHidden} />

            {!isUIHidden && (
              <>
                {/* Menu Options - left side */}
                <MenuOptions
                  activeMenu={activeMenu}
                  onMenuChange={setActiveMenu}
                />
                {/* Left Furniture Catalog Overlay (toolbox + groups) */}
                <FurnitureCatalogOverlay
                  open={catalogOpen}
                  onOpenChange={(o) => {
                    if (!o) setActiveMenu(null);
                  }}
                />
                {/* Floor Style Panel ("Công cụ" menu item) */}
                <FloorStylePanel
                  open={toolPanelOpen}
                  onOpenChange={(o) => {
                    if (!o) setActiveMenu(null);
                  }}
                />
                <ProjectSidebarPanel
                  open={projectPanelOpen}
                  onOpenChange={(o) => {
                    if (!o) setActiveMenu(null);
                  }}
                />

                {/* Right drawer — selected object details */}
                <SelectedObjectOverlay />

                {/* Right-side overlays */}
                <div className="absolute top-16 right-4 z-50 flex flex-col gap-2">
                  <SelectedWallOverlay />
                  <GroupOverlay />
                </div>
              </>
            )}
          </>
        )}

        {/* AI Enhancement panel (fullscreen when open — camera minimap embedded inside) */}
        <AIGeneratePanel
          ref={panelRef}
          screenshotRef={screenshotRef}
          cameraControlRef={cameraControlRef}
          cameraState={cameraState}
          onOpenChange={(open) => {
            setIsAIGenMode(open);
            if (!open) {
              // Restore default FOV when leaving AI mode.
              cameraControlRef.current?.setFov(50);
            }
          }}
        />

        {/* 3D Canvas - drop target for objects from overlay */}
        <DesignSceneCanvas
          screenshotRef={screenshotRef}
          cameraZoomRef={cameraZoomRef}
          cameraControlRef={cameraControlRef}
          setCameraState={setCameraState}
          objects={objects}
          isAIGenMode={isAIGenMode}
        />
      </div>
    </AuthGuard>
  );
}

export default function DesignPage() {
  return (
    <Suspense>
      <DesignPageInner />
    </Suspense>
  );
}
