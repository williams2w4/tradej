import { useEffect } from "react";
import { Card, Col, DatePicker, Input, Row, Select, Space, Button } from "antd";
import dayjs from "dayjs";

import { useAppDispatch, useAppSelector } from "../hooks";
import {
  resetFilters,
  setAssetCode,
  setAssetType,
  setDateRange,
  setDirection,
  setPreset
} from "../store/filterSlice";
import { AssetType, DateRangePreset, TradeDirection } from "../types";
import { computeRange } from "../utils/date";

const presetOptions: { label: string; value: DateRangePreset }[] = [
  { label: "今天", value: "today" },
  { label: "昨天", value: "yesterday" },
  { label: "本周", value: "thisWeek" },
  { label: "本月", value: "thisMonth" },
  { label: "本季度", value: "thisQuarter" },
  { label: "本年", value: "thisYear" },
  { label: "最近7天", value: "last7" },
  { label: "最近30天", value: "last30" },
  { label: "最近一年", value: "last365" }
];

const assetTypeOptions: { label: string; value: AssetType }[] = [
  { label: "股票", value: "stock" },
  { label: "期权", value: "option" },
  { label: "期货", value: "future" }
];

const directionOptions: { label: string; value: TradeDirection }[] = [
  { label: "多头", value: "long" },
  { label: "空头", value: "short" }
];

const FilterBar = () => {
  const dispatch = useAppDispatch();
  const filters = useAppSelector((state) => state.filters);
  const timezone = useAppSelector((state) => state.settings.timezone);

  useEffect(() => {
    if (filters.preset) {
      const range = computeRange(filters.preset, timezone);
      if (filters.startDate !== range.start || filters.endDate !== range.end) {
        dispatch(setDateRange({ startDate: range.start, endDate: range.end }));
      }
    }
  }, [dispatch, filters.endDate, filters.preset, filters.startDate, timezone]);

  const handleRangeChange = (values: [dayjs.Dayjs | null, dayjs.Dayjs | null] | null) => {
    if (!values || !values[0] || !values[1]) {
      dispatch(setDateRange({ startDate: null, endDate: null }));
      dispatch(setPreset(null));
      return;
    }
    dispatch(
      setDateRange({
        startDate: values[0].tz(timezone).startOf("day").toISOString(),
        endDate: values[1].tz(timezone).endOf("day").toISOString()
      })
    );
    dispatch(setPreset(null));
  };

  const handlePresetChange = (value: DateRangePreset) => {
    dispatch(setPreset(value));
  };

  const handleReset = () => {
    dispatch(resetFilters());
  };

  const rangeValue =
    filters.startDate && filters.endDate
      ? [dayjs(filters.startDate), dayjs(filters.endDate)]
      : null;

  return (
    <Card size="small" style={{ marginBottom: 16 }}>
      <Row gutter={16} align="middle">
        <Col xs={24} md={6} lg={4}>
          <Input
            value={filters.assetCode ?? ""}
            onChange={(e) => dispatch(setAssetCode(e.target.value.toUpperCase() || null))}
            placeholder="资产代码"
            allowClear
          />
        </Col>
        <Col xs={24} md={6} lg={4}>
          <Select
            value={filters.assetType ?? undefined}
            placeholder="资产类型"
            allowClear
            style={{ width: "100%" }}
            onChange={(value) => dispatch(setAssetType((value as AssetType) || null))}
            options={assetTypeOptions}
          />
        </Col>
        <Col xs={24} md={6} lg={4}>
          <Select
            value={filters.direction ?? undefined}
            placeholder="方向"
            allowClear
            style={{ width: "100%" }}
            onChange={(value) => dispatch(setDirection((value as TradeDirection) || null))}
            options={directionOptions}
          />
        </Col>
        <Col xs={24} md={12} lg={6}>
          <DatePicker.RangePicker
            value={rangeValue as any}
            onChange={handleRangeChange as any}
            style={{ width: "100%" }}
            allowClear
          />
        </Col>
        <Col xs={24} md={8} lg={4}>
          <Select
            value={filters.preset ?? undefined}
            placeholder="快捷选择"
            allowClear
            style={{ width: "100%" }}
            onChange={handlePresetChange}
            options={presetOptions}
          />
        </Col>
        <Col xs={24} md={4} lg={2}>
          <Space>
            <Button onClick={handleReset}>重置</Button>
          </Space>
        </Col>
      </Row>
    </Card>
  );
};

export default FilterBar;
