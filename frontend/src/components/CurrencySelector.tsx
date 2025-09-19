import { useState } from "react";
import { Select, message } from "antd";

import { useAppDispatch, useAppSelector } from "../hooks";
import { setCurrency } from "../store/settingsSlice";
import { updateSettings } from "../api/settings";
import { CurrencyCode } from "../types";

const CURRENCY_OPTIONS: { label: string; value: CurrencyCode }[] = [
  { label: "美元 (USD)", value: "USD" },
  { label: "港币 (HKD)", value: "HKD" },
  { label: "欧元 (EUR)", value: "EUR" },
  { label: "日元 (JPY)", value: "JPY" },
  { label: "人民币 (CNY)", value: "CNY" }
];

const CurrencySelector = () => {
  const dispatch = useAppDispatch();
  const currency = useAppSelector((state) => state.settings.currency);
  const [loading, setLoading] = useState(false);

  const handleChange = async (value: CurrencyCode) => {
    dispatch(setCurrency(value));
    setLoading(true);
    try {
      await updateSettings({ currency: value });
      message.success("货币已更新");
    } catch (error) {
      console.error(error);
      message.error("更新货币失败");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Select
      style={{ width: 160 }}
      value={currency}
      loading={loading}
      onChange={handleChange}
      options={CURRENCY_OPTIONS}
    />
  );
};

export default CurrencySelector;
