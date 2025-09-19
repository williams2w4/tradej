import { useEffect, useMemo, useState } from "react";
import { Calendar, Card, Typography } from "antd";
import dayjs, { Dayjs } from "dayjs";
import type { CalendarMode } from "antd/es/calendar";

import { fetchCalendar } from "../api/calendar";
import FilterBar from "../components/FilterBar";
import { useAppDispatch, useAppSelector } from "../hooks";
import { setDateRange, setPreset } from "../store/filterSlice";
import { CalendarDay } from "../types";
import { formatPercentage } from "../utils/date";
import { useNavigate } from "react-router-dom";

const CalendarPage = () => {
  const dispatch = useAppDispatch();
  const filters = useAppSelector((state) => state.filters);
  const timezone = useAppSelector((state) => state.settings.timezone);
  const currency = useAppSelector((state) => state.settings.currency);
  const [value, setValue] = useState<Dayjs>(dayjs());
  const [mode, setMode] = useState<CalendarMode>("month");
  const [data, setData] = useState<Record<string, CalendarDay>>({});
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const query = useMemo(
    () => ({
      asset_code: filters.assetCode,
      asset_type: filters.assetType,
      direction: filters.direction
    }),
    [filters.assetCode, filters.assetType, filters.direction]
  );

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      try {
        const response = await fetchCalendar({
          year: value.year(),
          month: value.month() + 1,
          timezone,
          currency,
          mode,
          ...query
        });
        const bucket: Record<string, CalendarDay> = {};
        response.forEach((item) => {
          const key = mode === "year" ? dayjs(item.date).format("YYYY-MM") : item.date;
          bucket[key] = item;
        });
        setData(bucket);
      } catch (error) {
        console.error("Failed to load calendar", error);
      } finally {
        setLoading(false);
      }
    };
    void load();
  }, [currency, mode, query, timezone, value]);

  const dateCellRender = (current: Dayjs) => {
    if (mode !== "month") {
      return <div className="calendar-cell-empty" />;
    }
    const key = current.format("YYYY-MM-DD");
    const entry = data[key];
    const isPositive = (entry?.total_profit_loss ?? 0) >= 0;

    const tradeCountText = `${entry?.trade_count ?? 0}笔`;
    const winRateText = entry ? formatPercentage(entry.win_rate) : "0.00%";
    const profitLoss = entry?.total_profit_loss ?? 0;
    const profitText = new Intl.NumberFormat(undefined, {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    }).format(profitLoss);

    return (
      <div
        style={{
          minHeight: 110,
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          alignItems: "center",
          gap: 6,
          borderRadius: 8,
          padding: 8,
          textAlign: "center",
          background: entry ? (isPositive ? "#f6ffed" : "#fff1f0") : undefined
        }}
      >
        <Typography.Text strong style={{ fontSize: 21 }}>
          {current.date()}
        </Typography.Text>
        <Typography.Text>{tradeCountText}</Typography.Text>
        <Typography.Text>{winRateText}</Typography.Text>
        <Typography.Text style={{ color: isPositive ? "#3f8600" : "#cf1322" }}>
          {profitText}
        </Typography.Text>
      </div>
    );
  };

  const monthCellRender = (current: Dayjs) => {
    if (mode !== "year") {
      return <div className="calendar-cell-empty" />;
    }
    const key = current.format("YYYY-MM");
    const entry = data[key];
    const isPositive = (entry?.total_profit_loss ?? 0) >= 0;

    const tradeCountText = `${entry?.trade_count ?? 0}笔`;
    const winRateText = entry ? formatPercentage(entry.win_rate) : "0.00%";
    const profitLoss = entry?.total_profit_loss ?? 0;
    const profitText = new Intl.NumberFormat(undefined, {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    }).format(profitLoss);

    return (
      <div
        style={{
          minHeight: 120,
          borderRadius: 10,
          padding: 12,
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          alignItems: "center",
          gap: 8,
          textAlign: "center",
          background: entry ? (isPositive ? "#f6ffed" : "#fff1f0") : undefined
        }}
      >
        <Typography.Text strong style={{ fontSize: 21 }}>
          {current.format("MM月")}
        </Typography.Text>
        <Typography.Text>{tradeCountText}</Typography.Text>
        <Typography.Text>{winRateText}</Typography.Text>
        <Typography.Text style={{ color: isPositive ? "#3f8600" : "#cf1322" }}>
          {profitText}
        </Typography.Text>
      </div>
    );
  };

  const handleSelect = (
    date: Dayjs,
    info: { source: "year" | "month" | "date" | "customize" }
  ) => {
    setValue(date);

    if (mode === "year" && info.source === "month") {
      setMode("month");
      return;
    }

    if (info.source !== "date") {
      return;
    }

    const start = date.startOf("day").toISOString();
    const end = date.endOf("day").toISOString();
    dispatch(setDateRange({ startDate: start, endDate: end }));
    dispatch(setPreset(null));
    navigate("/trades");
  };

  return (
    <div>
      <FilterBar />
      <Card loading={loading}>
        <Calendar
          value={value}
          mode={mode}
          onSelect={handleSelect}
          onPanelChange={(nextValue, nextMode) => {
            setValue(nextValue);
            if (nextMode) {
              setMode(nextMode);
            }
          }}
          dateFullCellRender={dateCellRender}
          monthFullCellRender={monthCellRender}
        />
      </Card>
    </div>
  );
};

export default CalendarPage;
