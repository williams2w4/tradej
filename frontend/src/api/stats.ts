import client from "./client";
import { AssetBreakdown, OverviewStats } from "../types";
import { TradeQuery } from "./trades";

export const fetchOverviewStats = async (params: TradeQuery): Promise<OverviewStats> => {
  const response = await client.get<OverviewStats>("/stats/overview", { params });
  return response.data;
};

export const fetchAssetBreakdown = async (params: TradeQuery): Promise<AssetBreakdown[]> => {
  const response = await client.get<AssetBreakdown[]>("/stats/by-asset", { params });
  return response.data;
};
