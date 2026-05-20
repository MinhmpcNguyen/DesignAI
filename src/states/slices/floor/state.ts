import { createSlice, type PayloadAction } from "@reduxjs/toolkit";
import type { RootState } from "@/states/store";
import type { FloorSliceType } from "./types";
import { DEFAULT_FLOOR_MATERIAL_ID } from "@/constant";
import type {
  AutoFillDebugSplitWall,
  AutoFillDebugZone,
  TRoomInfo,
} from "@/types/api";

const initialState: FloorSliceType = {
  globalMaterialId: DEFAULT_FLOOR_MATERIAL_ID,
  roomMaterials: {},
  roomNames: {},
  roomDescriptions: {},
  debugSplitWalls: {},
  debugSplitZones: {},
  selectedRoomKey: null,
};

const floorSlice = createSlice({
  name: "floor",
  initialState,
  reducers: {
    setGlobalMaterial(state, action: PayloadAction<string>) {
      state.globalMaterialId = action.payload;
    },
    setRoomMaterial(
      state,
      action: PayloadAction<{ key: string; materialId: string }>,
    ) {
      state.roomMaterials[action.payload.key] = action.payload.materialId;
    },
    clearRoomMaterial(state, action: PayloadAction<string>) {
      delete state.roomMaterials[action.payload];
    },
    setRoomName(state, action: PayloadAction<{ key: string; name: string }>) {
      state.roomNames[action.payload.key] = action.payload.name;
    },
    setRoomDescription(
      state,
      action: PayloadAction<{ key: string; description: string }>,
    ) {
      state.roomDescriptions[action.payload.key] = action.payload.description;
    },
    setRoomDebugSplit(
      state,
      action: PayloadAction<{
        key: string;
        wall: AutoFillDebugSplitWall;
        zones: AutoFillDebugZone[];
      }>,
    ) {
      state.debugSplitWalls[action.payload.key] = action.payload.wall;
      state.debugSplitZones[action.payload.key] = action.payload.zones;
    },
    clearRoomDebugSplit(state, action: PayloadAction<string>) {
      delete state.debugSplitWalls[action.payload];
      delete state.debugSplitZones[action.payload];
    },
    setSelectedRoomKey(state, action: PayloadAction<string | null>) {
      state.selectedRoomKey = action.payload;
    },
    /** Hydrate room names and materials from a saved snapshot. Replaces existing values. */
    loadRoomsFromSnapshot(state, action: PayloadAction<TRoomInfo[]>) {
      const names: Record<string, string> = {};
      const materials: Record<string, string> = {};
      const descriptions: Record<string, string> = {};
      const autoNamePattern = /^Ph\u00f2ng \d+$/;
      for (const room of action.payload) {
        // Only persist names that were explicitly set by the user
        if (room.name && !autoNamePattern.test(room.name)) {
          names[room.key] = room.name;
        }
        if (room.materialId) {
          materials[room.key] = room.materialId;
        }
        if (room.description) {
          descriptions[room.key] = room.description;
        }
      }
      state.roomNames = names;
      state.roomMaterials = materials;
      state.roomDescriptions = descriptions;
      state.debugSplitWalls = {};
      state.debugSplitZones = {};
      state.selectedRoomKey = null;
    },
  },
});

export const floorActions = floorSlice.actions;

export const floorSelectors = {
  selectGlobalMaterialId: (state: RootState) => state.floor.globalMaterialId,
  selectRoomMaterials: (state: RootState) => state.floor.roomMaterials,
  selectRoomNames: (state: RootState) => state.floor.roomNames,
  selectRoomDescriptions: (state: RootState) => state.floor.roomDescriptions,
  selectDebugSplitWalls: (state: RootState) => state.floor.debugSplitWalls,
  selectDebugSplitZones: (state: RootState) => state.floor.debugSplitZones,
  selectSelectedRoomKey: (state: RootState) => state.floor.selectedRoomKey,
};

export default floorSlice.reducer;
