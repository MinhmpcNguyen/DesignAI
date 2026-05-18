export type MeasureLine = {
  id: string;
  /** XZ coordinates of the first point (Y=0 floor plane) */
  start: [number, number];
  /** XZ coordinates of the second point (Y=0 floor plane) */
  end: [number, number];
};

export type MeasureSliceType = {
  /** Whether the measure tool is currently active */
  isActive: boolean;
  /** The first point the user clicked — waiting for the second point */
  pendingStart: [number, number] | null;
  /** All completed measurement lines in the scene */
  lines: MeasureLine[];
};
