export type AssetType = "stock" | "option" | "future";
export type TradeDirection = "long" | "short";
export type FillSide = "BUY" | "SELL";
export type CurrencyCode = "USD" | "HKD" | "EUR" | "JPY" | "CNY";

export interface TradeFill {
  id: number;
  side: FillSide;
  direction: TradeDirection;
  quantity: number;
  price: number;
  commission: number;
  currency: string;
  original_currency: string;
  trade_time: string;
  source?: string | null;
  order_id?: string | null;
}

export interface ParentTrade {
  id: number;
  asset_id: number;
  asset_code: string;
  asset_type: AssetType;
  direction: TradeDirection;
  quantity: number;
  open_time: string;
  close_time: string | null;
  open_price: number | null;
  close_price: number | null;
  total_commission: number;
  profit_loss: number | null; // null for open positions
  currency: string;
  original_currency: string;
  fills: TradeFill[];
}

export interface OverviewStats {
  total_trades: number;
  win_rate: number;
  total_profit_loss: number;
  average_profit_loss: number;
  profit_loss_ratio: number | null;
  profit_factor: number | null;
}

export interface AssetBreakdown {
  asset_code: string;
  asset_type: string;
  trade_count: number;
  win_rate: number;
  total_profit_loss: number;
}

export interface CalendarDay {
  date: string;
  trade_count: number;
  total_profit_loss: number;
  win_rate: number;
}

export interface ImportBatch {
  id: number;
  broker: string;
  filename: string;
  status: string;
  error_message?: string | null;
  total_records: number;
  created_at: string;
  completed_at: string | null;
  timezone: string | null;
}

export interface Settings {
  timezone: string;
  currency: CurrencyCode;
}

export type DateRangePreset =
  | "today"
  | "yesterday"
  | "thisWeek"
  | "thisMonth"
  | "thisQuarter"
  | "thisYear"
  | "last7"
  | "last30"
  | "last365"
  | null;

export interface FilterState {
  assetCode: string | null;
  assetType: AssetType | null;
  direction: TradeDirection | null;
  startDate: string | null;
  endDate: string | null;
  preset: DateRangePreset;
}
