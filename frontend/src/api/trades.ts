import client from "./client";
import { ParentTrade } from "../types";

export interface TradeQuery {
  asset_code?: string | null;
  asset_type?: string | null;
  direction?: string | null;
  start?: string | null;
  end?: string | null;
  timezone?: string;
  currency?: string;
}

export const fetchTrades = async (params: TradeQuery): Promise<ParentTrade[]> => {
  const response = await client.get<ParentTrade[]>("/trades", { params });
  return response.data;
};

export const deleteAllTrades = async (): Promise<void> => {
  await client.delete("/trades");
};

export const exportFills = async (params: TradeQuery): Promise<string> => {
  const response = await client.get("/trades/fills/export", {
    params,
    responseType: "text"
  });
  return response.data as string;
};
