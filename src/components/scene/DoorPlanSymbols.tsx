"use client";

import { useMemo } from "react";
import { useViewMode } from "@/states/slices/view/hooks";
import { useObjectsValue } from "@/states/slices/objects/hooks";
import { useWalls } from "@/states/slices/walls/hooks";
import { isWallDoorSceneObject } from "@/lib/doorModels";
import DoorSwingPlanOverlay from "@/components/scene/DoorSwingPlanOverlay";
import WindowPlanOverlay from "@/components/scene/WindowPlanOverlay";

/**
 * Architectural swing + open leaf in 2D orthographic view only.
 */
export default function DoorPlanSymbols() {
  const viewMode = useViewMode();
  const walls = useWalls();
  const { objects } = useObjectsValue();
  const is2D = viewMode === "2D";

  const wallById = useMemo(() => {
    const m = new Map<string, (typeof walls)[0]>();
    for (const w of walls) m.set(w.id, w);
    return m;
  }, [walls]);

  if (!is2D) return null;

  return (
    <>
      {objects.map((obj) => {
        if (!isWallDoorSceneObject(obj)) return null;
        const wall = obj.snappedToWall
          ? wallById.get(obj.snappedToWall)
          : undefined;
        if (!wall) return null;

        if (obj.objectRole === "window") {
          return (
            <WindowPlanOverlay
              key={obj.id}
              wall={wall}
              position={obj.position}
              rotation={obj.rotation}
              size={obj.size}
              selectableObjectId={obj.id}
            />
          );
        }

        return (
          <DoorSwingPlanOverlay
            key={obj.id}
            wall={wall}
            position={obj.position}
            rotation={obj.rotation}
            size={obj.size}
            selectableObjectId={obj.id}
          />
        );
      })}
    </>
  );
}
