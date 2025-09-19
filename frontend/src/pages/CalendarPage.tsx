import { useEffect, useMemo, useState } from "react";
import { Calendar, Card, Popover, Typography } from "antd";
import dayjs, { Dayjs } from "dayjs";

import { fetchCalendar } from "../api/calendar";
import FilterBar from "../components/FilterBar";
import { useAppDispatch, useAppSelector } from "../hooks";
import { setDateRange, setPreset } from "../store/filterSlice";
import { CalendarDay } from "../types";
import { formatCurrency } from "../utils/date";
import { useNavigate } from "react-router-dom";

const CalendarPage = () => {
  const dispatch = useAppDispatch();
  const filters = useAppSelector((state) => state.filters);
  const timezone = useAppSelector((state) => state.settings.timezone);
  const [value, setValue] = useState<Dayjs>(dayjs());
  const [data, setData] = useState<Record<string, CalendarDay>>({});
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const query = useMemo(
    () => ({
      assetCode: filters.assetCode,
      assetType: filters.assetType,
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
          ...query
        });
        const bucket: Record<string, CalendarDay> = {};
        response.forEach((item) => {
          bucket[item.date] = item;
        });
        setData(bucket);
      } catch (error) {
        console.error("Failed to load calendar", error);
      } finally {
        setLoading(false);
      }
    };
    void load();
  }, [query, timezone, value]);

  const dateCellRender = (current: Dayjs) => {
    const key = current.format("YYYY-MM-DD");
    const entry = data[key];
    if (!entry) {
      return <div className="calendar-cell-empty" />;
    }
    const content = (
      <div>
        <Typography.Text>交易笔数：{entry.trade_count}</Typography.Text>
        <br />
        <Typography.Text>总盈亏：{formatCurrency(entry.total_profit_loss)}</Typography.Text>
      </div>
    );
    const isPositive = entry.total_profit_loss >= 0;
    return (
      <Popover content={content} title={key} placement="top">
        <div
          style={{
            background: isPositive ? "#f6ffed" : "#fff1f0",
            borderRadius: 6,
            padding: 8,
            textAlign: "center"
          }}
        >
          <Typography.Text strong>{entry.trade_count}</Typography.Text>
          <br />
          <Typography.Text type={isPositive ? "success" : "danger"}>
            {entry.total_profit_loss.toFixed(2)}
          </Typography.Text>
        </div>
      </Popover>
    );
  };

  const handleSelect = (date: Dayjs) => {
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
          onSelect={handleSelect}
          onPanelChange={(next) => {
            setValue(next);
          }}
          dateFullCellRender={dateCellRender}
        />
      </Card>
    </div>
  );
};

export default CalendarPage;
