import { ComponentType, SVGProps } from "react";

export type TPresets = {
  key: string;
  label: string;
  imgUrl: string;
};

export type FloorMaterial = {
  id: string;
  label: string;
  /** CSS hex fallback color — used when textureUrl is absent or still loading */
  color: string;
  /** Path relative to /public — optional; feature works without it */
  textureUrl?: string;
  /** World-space size of one texture tile in meters (0.5 = tile repeats every 0.5 m) */
  tileSize: number;
};

export type TMenuOption = {
  id: string;
  name: string;
  icon: ComponentType<{ isSelected: boolean } & SVGProps<SVGSVGElement>>;
};

export interface CameraAnglePreset {
  id: string;
  label: string;
  x: number;
  z: number;
  y: number;
  azimuth: number;
  elevation: number;
  fov: number;
  selected: boolean;
}
