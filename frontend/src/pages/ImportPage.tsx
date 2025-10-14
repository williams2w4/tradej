import { useCallback, useEffect, useState } from "react";
import axios from "axios";
import { Card, Modal, Table, Upload, message } from "antd";
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
        if (axios.isAxiosError(error)) {
          const detail = error.response?.data?.detail;
          if (detail && typeof detail === "object" && detail.code === "duplicates_only") {
            const duplicates = detail.duplicates ?? 0;
            Modal.confirm({
              title: "检测到重复交易",
              content: `发现 ${duplicates} 条重复交易记录。是否覆盖导入并替换现有记录？`,
              okText: "覆盖导入",
              cancelText: "取消",
              onOk: async () => {
                try {
                  await uploadIbkrCsv(file as File, { overrideDuplicates: true });
                  message.success("覆盖导入成功");
                  await loadData();
                  onSuccess?.("ok", file as any);
                } catch (overrideError) {
                  if (axios.isAxiosError(overrideError)) {
                    const overrideDetail = overrideError.response?.data?.detail;
                    const overrideMessage =
                      (overrideDetail && typeof overrideDetail === "object" && "message" in overrideDetail
                        ? overrideDetail.message
                        : null) ?? "覆盖导入失败";
                    message.error(overrideMessage);
                  } else {
                    message.error("覆盖导入失败");
                  }
                  onError?.(overrideError as Error);
                }
              },
              onCancel: () => {
                message.info("已取消覆盖导入");
              }
            });
          } else {
            const detailMessage =
              (typeof detail === "object" && detail?.message) || (typeof detail === "string" ? detail : null);
            message.error(detailMessage ?? "上传失败");
          }
        } else {
          message.error("上传失败");
        }
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
            { title: "跳过记录数", dataIndex: "skipped_records" },
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
