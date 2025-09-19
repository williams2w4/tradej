import { createSlice, PayloadAction } from "@reduxjs/toolkit";
import { CurrencyCode, Settings } from "../types";

interface SettingsState {
  timezone: string;
  currency: CurrencyCode;
}

const initialState: SettingsState = {
  timezone: "UTC",
  currency: "USD"
};

const settingsSlice = createSlice({
  name: "settings",
  initialState,
  reducers: {
    setTimezone(state, action: PayloadAction<string>) {
      state.timezone = action.payload;
    },
    setCurrency(state, action: PayloadAction<CurrencyCode>) {
      state.currency = action.payload;
    },
    hydrateSettings(state, action: PayloadAction<Settings>) {
      state.timezone = action.payload.timezone;
      state.currency = action.payload.currency;
    }
  }
});

export const { setTimezone, setCurrency, hydrateSettings } = settingsSlice.actions;
export default settingsSlice.reducer;
