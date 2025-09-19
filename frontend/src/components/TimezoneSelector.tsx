import { useEffect, useMemo, useState } from "react";
import { Select, message } from "antd";

import { useAppDispatch, useAppSelector } from "../hooks";
import { hydrateSettings, setTimezone } from "../store/settingsSlice";
import { fetchSettings, updateSettings } from "../api/settings";

const FALLBACK_TIMEZONES = [
  "UTC",
  "America/New_York",
  "America/Chicago",
  "America/Los_Angeles",
  "Europe/London",
  "Europe/Paris",
  "Asia/Shanghai",
  "Asia/Tokyo",
  "Australia/Sydney"
];

const resolveTimezones = (): string[] => {
  if (typeof Intl.supportedValuesOf === "function") {
    try {
      return Intl.supportedValuesOf("timeZone");
    } catch (error) {
      console.warn("Unable to load timezones from Intl", error);
    }
  }
  return FALLBACK_TIMEZONES;
};

const TimezoneSelector = () => {
  const dispatch = useAppDispatch();
  const timezone = useAppSelector((state) => state.settings.timezone);
  const [loading, setLoading] = useState(false);
  const options = useMemo(() => resolveTimezones(), []);

  useEffect(() => {
    const load = async () => {
      try {
        const settings = await fetchSettings();
        dispatch(hydrateSettings(settings));
      } catch (error) {
        console.error("Failed to load settings", error);
      }
    };
    void load();
  }, [dispatch]);

  const handleChange = async (value: string) => {
    dispatch(setTimezone(value));
    setLoading(true);
    try {
      await updateSettings({ timezone: value });
      message.success("时区已更新");
    } catch (error) {
      console.error(error);
      message.error("更新时区失败");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Select
      showSearch
      size="middle"
      style={{ width: 220 }}
      value={timezone}
      loading={loading}
      onChange={handleChange}
      filterOption={(input, option) => {
        const optionValue = String(option?.value ?? "");
        return optionValue.toLowerCase().includes(input.toLowerCase());
      }}
    >
      {options.map((tz) => (
        <Select.Option key={tz} value={tz}>
          {tz}
        </Select.Option>
      ))}
    </Select>
  );
};

export default TimezoneSelector;
