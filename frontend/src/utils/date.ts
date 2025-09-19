import dayjs from "dayjs";
import utc from "dayjs/plugin/utc";
import timezonePlugin from "dayjs/plugin/timezone";

import { DateRangePreset } from "../types";

dayjs.extend(utc);
dayjs.extend(timezonePlugin);

export const computeRange = (preset: DateRangePreset, timezone: string): {
  start: string | null;
  end: string | null;
} => {
  if (!preset) {
    return { start: null, end: null };
  }
  const now = dayjs().tz(timezone);
  switch (preset) {
    case "today": {
      const start = now.startOf("day");
      const end = now.endOf("day");
      return { start: start.toISOString(), end: end.toISOString() };
    }
    case "yesterday": {
      const start = now.subtract(1, "day").startOf("day");
      const end = start.endOf("day");
      return { start: start.toISOString(), end: end.toISOString() };
    }
    case "thisWeek": {
      const start = now.startOf("week");
      const end = now.endOf("week");
      return { start: start.toISOString(), end: end.toISOString() };
    }
    case "thisMonth": {
      const start = now.startOf("month");
      const end = now.endOf("month");
      return { start: start.toISOString(), end: end.toISOString() };
    }
    case "thisQuarter": {
      const start = now.startOf("quarter");
      const end = now.endOf("quarter");
      return { start: start.toISOString(), end: end.toISOString() };
    }
    case "thisYear": {
      const start = now.startOf("year");
      const end = now.endOf("year");
      return { start: start.toISOString(), end: end.toISOString() };
    }
    case "last7": {
      const start = now.subtract(6, "day").startOf("day");
      return { start: start.toISOString(), end: now.endOf("day").toISOString() };
    }
    case "last30": {
      const start = now.subtract(29, "day").startOf("day");
      return { start: start.toISOString(), end: now.endOf("day").toISOString() };
    }
    case "last365": {
      const start = now.subtract(364, "day").startOf("day");
      return { start: start.toISOString(), end: now.endOf("day").toISOString() };
    }
    default:
      return { start: null, end: null };
  }
};

export const formatCurrency = (value: number, currency = "USD"): string => {
  return new Intl.NumberFormat(undefined, {
    style: "currency",
    currency,
    minimumFractionDigits: 2
  }).format(value);
};

export const formatPercentage = (value: number): string => {
  return `${(value * 100).toFixed(2)}%`;
};

export const formatDateTime = (value: string, timezone: string): string => {
  return dayjs(value).tz(timezone).format("YYYY-MM-DD HH:mm");
};
