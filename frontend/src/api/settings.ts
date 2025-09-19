import client from "./client";
import { Settings } from "../types";

export const fetchSettings = async (): Promise<Settings> => {
  const response = await client.get<Settings>("/settings");
  return response.data;
};

export const updateSettings = async (settings: Partial<Settings>): Promise<Settings> => {
  const response = await client.patch<Settings>("/settings", settings);
  return response.data;
};
