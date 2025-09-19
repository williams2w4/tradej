import client from "./client";
import { CalendarDay } from "../types";

export interface CalendarQuery {
  year: number;
  month: number;
  asset_code?: string | null;
  asset_type?: string | null;
  direction?: string | null;
  timezone?: string;
  currency?: string;
  mode?: "month" | "year";
}

export const fetchCalendar = async (params: CalendarQuery): Promise<CalendarDay[]> => {
  const response = await client.get<CalendarDay[]>("/calendar", { params });
  return response.data;
};
