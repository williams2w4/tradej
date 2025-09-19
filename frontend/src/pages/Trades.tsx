import { useCallback, useEffect, useMemo, useState } from "react";
import { Button, Card, Popconfirm, Space, Table, message } from "antd";

import FilterBar from "../components/FilterBar";
import { deleteAllTrades, exportFills, fetchTrades } from "../api/trades";
import { useAppSelector } from "../hooks";
import { ParentTrade, TradeFill } from "../types";
import { formatCurrency, formatDateTime } from "../utils/date";

const Trades = () => {
  const filters = useAppSelector((state) => state.filters);
  const timezone = useAppSelector((state) => state.settings.timezone);
  const [trades, setTrades] = useState<ParentTrade[]>([]);
  const [loading, setLoading] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const query = useMemo(
    () => ({
      assetCode: filters.assetCode,
      assetType: filters.assetType,
      direction: filters.direction,
      start: filters.startDate,
      end: filters.endDate,
      timezone
    }),
    [filters.assetCode, filters.assetType, filters.direction, filters.startDate, filters.endDate, timezone]
  );

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      try {
        const data = await fetchTrades(query);
        setTrades(data);
      } catch (error) {
        console.error("Failed to load trades", error);
      } finally {
        setLoading(false);
      }
    };
    void load();
  }, [query]);

  const handleExport = useCallback(async () => {
    setExporting(true);
    try {
      const content = await exportFills(query);
      const blob = new Blob([content], { type: "text/plain;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = "trade_fills.pine";
      anchor.click();
      URL.revokeObjectURL(url);
      message.success("导出成功");
    } catch (error) {
      console.error(error);
      message.error("导出失败");
    } finally {
      setExporting(false);
    }
  }, [query]);

  const handleDelete = useCallback(async () => {
    setDeleting(true);
    try {
      await deleteAllTrades();
      setTrades([]);
      message.success("所有交易已删除");
    } catch (error) {
      console.error(error);
      message.error("删除失败");
    } finally {
      setDeleting(false);
    }
  }, []);

  const renderFillTable = (fills: TradeFill[]) => (
    <Table
      dataSource={fills}
      rowKey={(fill) => fill.id}
      pagination={false}
      size="small"
      columns={[
        { title: "方向", dataIndex: "side" },
        { title: "数量", dataIndex: "quantity" },
        { title: "价格", dataIndex: "price", render: (value: number) => value.toFixed(2) },
        { title: "佣金", dataIndex: "commission", render: (value: number) => value.toFixed(2) },
        {
          title: "成交时间",
          dataIndex: "trade_time",
          render: (value: string) => formatDateTime(value, timezone)
        },
        { title: "来源", dataIndex: "source", render: (value: string | null) => value ?? "--" },
        { title: "订单号", dataIndex: "order_id", render: (value: string | null) => value ?? "--" }
      ]}
    />
  );

  return (
    <div>
      <Space style={{ width: "100%", marginBottom: 16, justifyContent: "space-between" }}>
        <Space>
          <Button type="primary" onClick={handleExport} loading={exporting}>
            导出子交易
          </Button>
          <Popconfirm title="确认删除所有交易？" onConfirm={handleDelete} okButtonProps={{ loading: deleting }}>
            <Button danger>删除所有交易</Button>
          </Popconfirm>
        </Space>
      </Space>
      <FilterBar />
      <Card>
        <Table
          loading={loading}
          dataSource={trades}
          rowKey={(trade) => trade.id}
          expandable={{ expandedRowRender: (record) => renderFillTable(record.fills) }}
          columns={[
            { title: "记录ID", dataIndex: "id" },
            { title: "资产代码", dataIndex: "asset_code" },
            { title: "方向", dataIndex: "direction" },
            { title: "数量", dataIndex: "quantity" },
            {
              title: "开仓价格",
              dataIndex: "open_price",
              render: (value: number | null) => (value !== null ? value.toFixed(2) : "--")
            },
            {
              title: "平仓价格",
              dataIndex: "close_price",
              render: (value: number | null) => (value !== null ? value.toFixed(2) : "--")
            },
            {
              title: "开仓时间",
              dataIndex: "open_time",
              render: (value: string) => formatDateTime(value, timezone)
            },
            {
              title: "平仓时间",
              dataIndex: "close_time",
              render: (value: string | null) => (value ? formatDateTime(value, timezone) : "--")
            },
            {
              title: "佣金",
              dataIndex: "total_commission",
              render: (_: number, record: ParentTrade) => formatCurrency(record.total_commission, record.currency)
            },
            {
              title: "盈亏",
              dataIndex: "profit_loss",
              render: (_: number, record: ParentTrade) => formatCurrency(record.profit_loss, record.currency)
            }
          ]}
        />
      </Card>
    </div>
  );
};

export default Trades;
