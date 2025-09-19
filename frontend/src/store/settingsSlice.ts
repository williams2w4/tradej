import { createSlice, PayloadAction } from "@reduxjs/toolkit";
import { Settings } from "../types";

interface SettingsState {
  timezone: string;
}

const initialState: SettingsState = {
  timezone: "UTC"
};

const settingsSlice = createSlice({
  name: "settings",
  initialState,
  reducers: {
    setTimezone(state, action: PayloadAction<string>) {
      state.timezone = action.payload;
    },
    hydrateSettings(state, action: PayloadAction<Settings>) {
      state.timezone = action.payload.timezone;
    }
  }
});

export const { setTimezone, hydrateSettings } = settingsSlice.actions;
export default settingsSlice.reducer;
