import { ChangeEvent, useMemo, useState } from "react";
import { ChatKit, useChatKit } from "@openai/chatkit-react";
import { createClientSecretFetcher, workflowId } from "../lib/chatkitSession";

export function ChatKitPanel() {
  const [uploadedDocumentName, setUploadedDocumentName] = useState("");
  const [vectorStoreId, setVectorStoreId] = useState("");
  const [isUploadingDocument, setIsUploadingDocument] = useState(false);
  const [documentError, setDocumentError] = useState<string | null>(null);

  async function handleUploadDocument(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;

    setIsUploadingDocument(true);
    setDocumentError(null);
    setVectorStoreId("");

    try {
      const formData = new FormData();
      formData.append("file", file);

      const response = await fetch("/api/upload-document", {
        method: "POST",
        body: formData,
      });

      const payload = (await response.json().catch(() => ({}))) as {
        filename?: string;
        vector_store_id?: string;
        error?: string;
      };

      if (!response.ok || !payload.vector_store_id) {
        throw new Error(
          payload.error ?? "Unable to process that document right now."
        );
      }

      setUploadedDocumentName(payload.filename ?? file.name);
      setVectorStoreId(payload.vector_store_id);
    } catch (error) {
      setUploadedDocumentName("");
      setVectorStoreId("");
      setDocumentError(
        error instanceof Error
          ? error.message
          : "Unable to process that document right now."
      );
    } finally {
      event.target.value = "";
      setIsUploadingDocument(false);
    }
  }

  return (
    <div className="space-y-4">
      <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm transition-colors dark:border-slate-800 dark:bg-slate-900">
        <div className="space-y-2">
          <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">
            Upload A Document
          </h2>
          <p className="text-sm text-slate-600 dark:text-slate-300">
            Upload a `.txt`, `.md`, `.pdf`, or `.docx` file to create a vector
            store for retrieval.
          </p>
        </div>

        <div className="mt-4 flex flex-wrap items-center gap-3">
          <label className="inline-flex cursor-pointer items-center rounded-full bg-slate-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-700 dark:bg-slate-100 dark:text-slate-900 dark:hover:bg-slate-300">
            <input
              type="file"
              accept=".txt,.md,.pdf,.docx"
              className="hidden"
              onChange={(event) => void handleUploadDocument(event)}
            />
            {isUploadingDocument ? "Uploading..." : "Choose Document"}
          </label>
          {uploadedDocumentName ? (
            <p className="text-sm text-slate-600 dark:text-slate-300">
              Loaded: {uploadedDocumentName}
            </p>
          ) : (
            <p className="text-sm text-slate-500 dark:text-slate-400">
              No document uploaded yet.
            </p>
          )}
        </div>

        <div className="mt-3 flex items-center justify-between gap-3">
          <p className="text-xs text-slate-500 dark:text-slate-400">
            Supported uploads: `.txt`, `.md`, `.pdf`, `.docx` up to 25 MB.
          </p>
          {vectorStoreId ? (
            <p className="text-xs font-medium text-emerald-700 dark:text-emerald-400">
              Vector store ready: {vectorStoreId}
            </p>
          ) : null}
        </div>

        {documentError ? (
          <p className="mt-3 text-sm text-red-600 dark:text-red-400">
            {documentError}
          </p>
        ) : null}

        {!documentError && vectorStoreId ? (
          <p className="mt-3 text-sm text-slate-600 dark:text-slate-300">
            The document is indexed. The next step is wiring this
            `vector_store_id` into your workflow's `file_search` path.
          </p>
        ) : null}
      </section>

      <ChatKitSession vectorStoreId={vectorStoreId} />
    </div>
  );
}

function ChatKitSession({ vectorStoreId }: { vectorStoreId: string }) {
  const getClientSecret = useMemo(
    () =>
      createClientSecretFetcher(
        workflowId,
        undefined,
        vectorStoreId ? { vector_store_id: vectorStoreId } : undefined
      ),
    [vectorStoreId]
  );

  const chatkit = useChatKit({
    api: { getClientSecret },
  });

  return (
    <div
      key={vectorStoreId || "default-session"}
      className="flex h-[90vh] w-full rounded-2xl bg-white shadow-sm transition-colors dark:bg-slate-900"
    >
      <ChatKit control={chatkit.control} className="h-full w-full" />
    </div>
  );
}
