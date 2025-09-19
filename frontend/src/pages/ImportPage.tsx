import { useCallback, useEffect, useState } from "react";
import { Card, Table, Upload, message } from "antd";
import type { UploadProps } from "antd";

import { listImports, uploadIbkrCsv } from "../api/imports";
import { ImportBatch } from "../types";
import { formatDateTime } from "../utils/date";
import { useAppSelector } from "../hooks";

const ImportPage = () => {
  const timezone = useAppSelector((state) => state.settings.timezone);
  const [records, setRecords] = useState<ImportBatch[]>([]);
  const [loading, setLoading] = useState(false);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const data = await listImports();
      setRecords(data);
    } catch (error) {
      console.error("Failed to load imports", error);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  const uploadProps: UploadProps = {
    name: "file",
    accept: ".csv",
    showUploadList: false,
    customRequest: async ({ file, onError, onSuccess }) => {
      try {
        await uploadIbkrCsv(file as File);
        message.success("上传成功");
        await loadData();
        onSuccess?.("ok", file as any);
      } catch (error) {
        console.error(error);
        message.error("上传失败");
        onError?.(error as Error);
      }
    }
  };

  return (
    <div>
      <Card title="导入IBKR CSV">
        <Upload {...uploadProps}>
          <div style={{ padding: 24, border: "1px dashed #d9d9d9", borderRadius: 8, textAlign: "center" }}>
            点击或拖拽文件到此处上传
          </div>
        </Upload>
      </Card>
      <Card title="导入历史" style={{ marginTop: 24 }} loading={loading}>
        <Table
          dataSource={records}
          rowKey={(record) => record.id}
          pagination={false}
          columns={[
            { title: "编号", dataIndex: "id" },
            { title: "文件名", dataIndex: "filename" },
            { title: "券商", dataIndex: "broker" },
            { title: "状态", dataIndex: "status" },
            { title: "总记录数", dataIndex: "total_records" },
            {
              title: "创建时间",
              dataIndex: "created_at",
              render: (value: string) => formatDateTime(value, timezone)
            },
            {
              title: "完成时间",
              dataIndex: "completed_at",
              render: (value: string | null) => (value ? formatDateTime(value, timezone) : "--")
            },
            {
              title: "错误信息",
              dataIndex: "error_message",
              render: (value: string | null) => value ?? "--"
            }
          ]}
        />
      </Card>
    </div>
  );
};

export default ImportPage;
