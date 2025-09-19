import { useEffect, useMemo, useState } from "react";
import { Card, Col, Row, Statistic, Table } from "antd";

import FilterBar from "../components/FilterBar";
import { fetchAssetBreakdown, fetchOverviewStats } from "../api/stats";
import { useAppSelector } from "../hooks";
import { AssetBreakdown, OverviewStats } from "../types";
import { formatCurrency, formatPercentage } from "../utils/date";

const Dashboard = () => {
  const filters = useAppSelector((state) => state.filters);
  const timezone = useAppSelector((state) => state.settings.timezone);
  const currency = useAppSelector((state) => state.settings.currency);
  const [overview, setOverview] = useState<OverviewStats | null>(null);
  const [breakdown, setBreakdown] = useState<AssetBreakdown[]>([]);
  const [loading, setLoading] = useState(false);

  const query = useMemo(
    () => ({
      assetCode: filters.assetCode,
      assetType: filters.assetType,
      direction: filters.direction,
      start: filters.startDate,
      end: filters.endDate,
      timezone,
      currency
    }),
    [filters.assetCode, filters.assetType, filters.direction, filters.startDate, filters.endDate, timezone, currency]
  );

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      try {
        const [overviewResp, breakdownResp] = await Promise.all([
          fetchOverviewStats(query),
          fetchAssetBreakdown(query)
        ]);
        setOverview(overviewResp);
        setBreakdown(breakdownResp);
      } catch (error) {
        console.error("Failed to load dashboard data", error);
      } finally {
        setLoading(false);
      }
    };
    void load();
  }, [query]);

  const totalProfit = overview?.total_profit_loss ?? 0;
  const isPositive = totalProfit >= 0;
  const valueStyle = { color: isPositive ? "#3f8600" : "#cf1322" };

  const stats = [
    {
      key: "total",
      title: "总盈亏",
      value: formatCurrency(totalProfit, currency)
    },
    {
      key: "win_rate",
      title: "胜率",
      value: formatPercentage(overview?.win_rate ?? 0)
    },
    {
      key: "ratio",
      title: "盈亏比",
      value:
        overview?.profit_loss_ratio !== null && overview?.profit_loss_ratio !== undefined
          ? overview.profit_loss_ratio.toFixed(2)
          : "--"
    },
    {
      key: "average",
      title: "平均盈亏",
      value: formatCurrency(overview?.average_profit_loss ?? 0, currency)
    },
    {
      key: "count",
      title: "交易总数",
      value: overview?.total_trades ?? 0
    },
    {
      key: "factor",
      title: "盈利因子",
      value:
        overview?.profit_factor !== null && overview?.profit_factor !== undefined
          ? overview.profit_factor.toFixed(2)
          : "--"
    }
  ];

  return (
    <div>
      <FilterBar />
      <Row gutter={[16, 16]}>
        {stats.map((item) => (
          <Col xs={24} md={8} key={item.key}>
            <Card loading={loading}>
              <Statistic title={item.title} value={item.value} valueStyle={valueStyle} />
            </Card>
          </Col>
        ))}
      </Row>
      <Card title="按资产分类统计" style={{ marginTop: 24 }} loading={loading}>
        <Table
          dataSource={breakdown}
          rowKey={(record) => record.asset_code}
          pagination={false}
          columns={[
            {
              title: "资产代码",
              dataIndex: "asset_code"
            },
            {
              title: "资产类型",
              dataIndex: "asset_type"
            },
            {
              title: "交易次数",
              dataIndex: "trade_count"
            },
            {
              title: "胜率",
              dataIndex: "win_rate",
              render: (value: number) => formatPercentage(value)
            },
            {
              title: "总盈亏",
              dataIndex: "total_profit_loss",
              render: (value: number) => (
                <span style={{ color: value >= 0 ? "#3f8600" : "#cf1322" }}>
                  {formatCurrency(value, currency)}
                </span>
              )
            }
          ]}
        />
      </Card>
    </div>
  );
};

export default Dashboard;
