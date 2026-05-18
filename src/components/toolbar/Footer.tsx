import { LandPlot } from "lucide-react";
import UserGuide from "../views/DesignPage/UserGuide";
import DrawWallButton from "./DrawWallButton";
import EditModeToggle from "./EditModeToggle";
import MeasureTool from "./MeasureTool";
import { useWalls } from "@/states/slices/walls/hooks";
import { computeTotalFloorArea } from "@/lib/roomPolygons";
import { useMemo } from "react";

interface FooterProps {
  isUIHidden?: boolean;
}

export default function Footer({ isUIHidden }: FooterProps) {
  const walls = useWalls();

  const totalFloorArea = useMemo(() => computeTotalFloorArea(walls), [walls]);

  if (isUIHidden) return null;

  return (
    <footer className="fixed bottom-0 left-0 right-0 z-50 h-14 bg-transparent flex items-center justify-between px-2 gap-2">
      <UserGuide />
      <div className="flex items-center gap-2 justify-center">
        <EditModeToggle />
        <DrawWallButton />
        <MeasureTool />
      </div>

      {/* Floating floor-area badge (over canvas) */}
      <div className="z-50">
        <div
          className="bg-white px-3 py-2 rounded-lg shadow-(--shadow-style) flex items-center gap-2"
          style={{ border: "var(--border-style)" }}
        >
          <LandPlot size={16} color="var(--primary-color)" />
          <div className="text-sm font-medium select-none">
            {totalFloorArea !== null
              ? `${totalFloorArea.toFixed(1)} m²`
              : "0 m²"}
          </div>
        </div>
      </div>
    </footer>
  );
}
