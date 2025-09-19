import { createSlice, PayloadAction } from "@reduxjs/toolkit";
import { AssetType, DateRangePreset, FilterState, TradeDirection } from "../types";

type DateRangePayload = {
  startDate: string | null;
  endDate: string | null;
};

const initialState: FilterState = {
  assetCode: null,
  assetType: null,
  direction: null,
  startDate: null,
  endDate: null,
  preset: "last30"
};

const filterSlice = createSlice({
  name: "filters",
  initialState,
  reducers: {
    setAssetCode(state, action: PayloadAction<string | null>) {
      state.assetCode = action.payload;
    },
    setAssetType(state, action: PayloadAction<AssetType | null>) {
      state.assetType = action.payload;
    },
    setDirection(state, action: PayloadAction<TradeDirection | null>) {
      state.direction = action.payload;
    },
    setDateRange(state, action: PayloadAction<DateRangePayload>) {
      state.startDate = action.payload.startDate;
      state.endDate = action.payload.endDate;
    },
    setPreset(state, action: PayloadAction<DateRangePreset>) {
      state.preset = action.payload;
    },
    resetFilters() {
      return initialState;
    }
  }
});

export const { setAssetCode, setAssetType, setDirection, setDateRange, setPreset, resetFilters } =
  filterSlice.actions;
export default filterSlice.reducer;
