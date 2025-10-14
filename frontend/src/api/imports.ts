import client from "./client";
import { ImportBatch } from "../types";

export const listImports = async (): Promise<ImportBatch[]> => {
  const response = await client.get<ImportBatch[]>("/imports");
  return response.data;
};

export const uploadIbkrCsv = async (
  file: File,
  options: { overrideDuplicates?: boolean } = {}
): Promise<ImportBatch> => {
  const formData = new FormData();
  formData.append("broker", "ibkr");
  formData.append("file", file);
  if (options.overrideDuplicates) {
    formData.append("override_duplicates", "true");
  }
  const response = await client.post<ImportBatch>("/imports", formData, {
    headers: { "Content-Type": "multipart/form-data" }
  });
  return response.data;
};
