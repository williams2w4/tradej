import { configureStore } from "@reduxjs/toolkit";

import filterReducer from "./filterSlice";
import settingsReducer from "./settingsSlice";

export const store = configureStore({
  reducer: {
    filters: filterReducer,
    settings: settingsReducer
  }
});

export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;
