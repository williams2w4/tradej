import client from "./client";
import { CalendarDay } from "../types";

export interface CalendarQuery {
  year: number;
  month: number;
  assetCode?: string | null;
  assetType?: string | null;
  direction?: string | null;
  timezone?: string;
}

export const fetchCalendar = async (params: CalendarQuery): Promise<CalendarDay[]> => {
  const response = await client.get<CalendarDay[]>("/calendar", { params });
  return response.data;
};
