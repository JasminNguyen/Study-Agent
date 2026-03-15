import { ChangeEvent, useMemo, useState } from "react";
import { ChatKit, useChatKit } from "@openai/chatkit-react";
import { createClientSecretFetcher, workflowId } from "../lib/chatkitSession";

export function ChatKitPanel() {
  const [uploadedDocumentName, setUploadedDocumentName] = useState("");
  const [documentText, setDocumentText] = useState("");
  const [isUploadingDocument, setIsUploadingDocument] = useState(false);
  const [isSubmittingDocument, setIsSubmittingDocument] = useState(false);
  const [documentError, setDocumentError] = useState<string | null>(null);

  const getClientSecret = useMemo(
    () => createClientSecretFetcher(workflowId),
    []
  );

  const chatkit = useChatKit({
    api: { getClientSecret },
  });

  const hasDocumentText = documentText.trim().length > 0;

  async function handleUploadDocument(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;

    setIsUploadingDocument(true);
    setDocumentError(null);

    try {
      const formData = new FormData();
      formData.append("file", file);

      const response = await fetch("/api/upload-document", {
        method: "POST",
        body: formData,
      });

      const payload = (await response.json().catch(() => ({}))) as {
        filename?: string;
        text?: string;
        error?: string;
      };

      if (!response.ok || !payload.text) {
        throw new Error(
          payload.error ?? "Unable to process that document right now."
        );
      }

      setUploadedDocumentName(payload.filename ?? file.name);
      setDocumentText(payload.text);
    } catch (error) {
      setUploadedDocumentName("");
      setDocumentText("");
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

  async function handleStartWithDocument() {
    const trimmedDocument = documentText.trim();
    if (!trimmedDocument) {
      setDocumentError("Upload a document before starting a chat.");
      return;
    }

    setIsSubmittingDocument(true);
    setDocumentError(null);

    try {
      await chatkit.setThreadId(null);
      await chatkit.sendUserMessage({
        newThread: true,
        text: [
          `Use the following document as the primary source for this chat${uploadedDocumentName ? `: ${uploadedDocumentName}` : ""}.`,
          "Summarize it first, then answer follow-up questions using only this document unless I ask otherwise.",
          "",
          trimmedDocument,
        ].join("\n"),
      });
    } catch (error) {
      setDocumentError(
        error instanceof Error
          ? error.message
          : "Unable to start the chat with this document."
      );
    } finally {
      setIsSubmittingDocument(false);
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
            Upload a `.txt`, `.md`, `.pdf`, or `.docx` file, then start a new
            chat from the extracted text.
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

        <label className="mt-4 block text-sm font-medium text-slate-700 dark:text-slate-200">
          Extracted text preview
        </label>
        <textarea
          className="mt-2 min-h-44 w-full rounded-xl border border-slate-300 bg-white px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-slate-500 focus:ring-2 focus:ring-slate-200 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100 dark:focus:border-slate-400 dark:focus:ring-slate-800"
          value={documentText}
          onChange={(event) => setDocumentText(event.target.value)}
          placeholder="Once uploaded, the extracted document text will appear here."
        />

        <div className="mt-3 flex items-center justify-between gap-3">
          <p className="text-xs text-slate-500 dark:text-slate-400">
            Supported uploads: `.txt`, `.md`, `.pdf`, `.docx` up to 10 MB.
          </p>
          <button
            type="button"
            onClick={() => void handleStartWithDocument()}
            disabled={!hasDocumentText || isSubmittingDocument || isUploadingDocument}
            className="rounded-full bg-slate-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-700 disabled:cursor-not-allowed disabled:bg-slate-400 dark:bg-slate-100 dark:text-slate-900 dark:hover:bg-slate-300 dark:disabled:bg-slate-600 dark:disabled:text-slate-200"
          >
            {isSubmittingDocument ? "Starting..." : "Start Chat With Document"}
          </button>
        </div>

        {documentError ? (
          <p className="mt-3 text-sm text-red-600 dark:text-red-400">
            {documentError}
          </p>
        ) : null}
      </section>

      <div className="flex h-[90vh] w-full rounded-2xl bg-white shadow-sm transition-colors dark:bg-slate-900">
        <ChatKit control={chatkit.control} className="h-full w-full" />
      </div>
    </div>
  );
}
