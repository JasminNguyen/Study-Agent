import { ChangeEvent, FormEvent, useState } from "react";

type Message = {
  role: "user" | "assistant";
  content: string;
};

export function ChatKitPanel() {
  const [uploadedDocumentName, setUploadedDocumentName] = useState("");
  const [vectorStoreId, setVectorStoreId] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [draft, setDraft] = useState("");
  const [isUploadingDocument, setIsUploadingDocument] = useState(false);
  const [isSendingMessage, setIsSendingMessage] = useState(false);
  const [documentError, setDocumentError] = useState<string | null>(null);
  const [chatError, setChatError] = useState<string | null>(null);

  async function handleUploadDocument(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;

    setIsUploadingDocument(true);
    setDocumentError(null);
    setChatError(null);
    setVectorStoreId("");
    setMessages([]);

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
      setMessages([
        {
          role: "assistant",
          content:
            "Your document is indexed and ready. Ask a question about it whenever you’re ready.",
        },
      ]);
    } catch (error) {
      setUploadedDocumentName("");
      setVectorStoreId("");
      setMessages([]);
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

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const trimmedDraft = draft.trim();
    if (!trimmedDraft || !vectorStoreId || isSendingMessage) return;

    const nextMessages = [
      ...messages,
      { role: "user" as const, content: trimmedDraft },
    ];

    setDraft("");
    setChatError(null);
    setMessages(nextMessages);
    setIsSendingMessage(true);

    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: trimmedDraft,
          vector_store_id: vectorStoreId,
          history: messages,
        }),
      });

      const payload = (await response.json().catch(() => ({}))) as {
        answer?: string;
        error?: string;
      };

      if (!response.ok || !payload.answer) {
        throw new Error(payload.error ?? "Unable to answer that question right now.");
      }

      setMessages([
        ...nextMessages,
        { role: "assistant", content: payload.answer },
      ]);
    } catch (error) {
      setMessages(messages);
      setDraft(trimmedDraft);
      setChatError(
        error instanceof Error
          ? error.message
          : "Unable to answer that question right now."
      );
    } finally {
      setIsSendingMessage(false);
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
            Upload a `.txt`, `.md`, `.pdf`, or `.docx` file. Questions will use
            retrieval over the uploaded document instead of sending the full file
            into chat.
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
      </section>

      <section className="flex h-[90vh] flex-col rounded-2xl bg-white shadow-sm transition-colors dark:bg-slate-900">
        <div className="border-b border-slate-200 px-5 py-4 dark:border-slate-800">
          <h3 className="text-base font-semibold text-slate-900 dark:text-slate-100">
            Document Chat
          </h3>
          <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">
            Ask specific questions, request summaries, or turn the document into study notes.
          </p>
        </div>

        <div className="flex-1 space-y-4 overflow-y-auto px-5 py-4">
          {messages.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-slate-300 bg-slate-50 p-5 text-sm text-slate-600 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-300">
              Upload a document to start the conversation.
            </div>
          ) : (
            messages.map((message, index) => (
              <article
                key={`${message.role}-${index}`}
                className={
                  message.role === "user"
                    ? "ml-auto max-w-[80%] rounded-2xl bg-slate-900 px-4 py-3 text-sm text-white dark:bg-slate-100 dark:text-slate-900"
                    : "max-w-[85%] rounded-2xl bg-slate-100 px-4 py-3 text-sm text-slate-900 dark:bg-slate-800 dark:text-slate-100"
                }
              >
                <p className="whitespace-pre-wrap">{message.content}</p>
              </article>
            ))
          )}
        </div>

        <form
          onSubmit={(event) => void handleSubmit(event)}
          className="border-t border-slate-200 px-5 py-4 dark:border-slate-800"
        >
          <label className="sr-only" htmlFor="document-chat-input">
            Ask a question about the uploaded document
          </label>
          <textarea
            id="document-chat-input"
            className="min-h-24 w-full rounded-2xl border border-slate-300 bg-white px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-slate-500 focus:ring-2 focus:ring-slate-200 disabled:cursor-not-allowed disabled:bg-slate-100 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100 dark:focus:border-slate-400 dark:focus:ring-slate-800 dark:disabled:bg-slate-900"
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            disabled={!vectorStoreId || isSendingMessage}
            placeholder={
              vectorStoreId
                ? "Ask something about the uploaded document..."
                : "Upload a document before asking a question."
            }
          />

          <div className="mt-3 flex items-center justify-between gap-3">
            <p className="text-xs text-slate-500 dark:text-slate-400">
              Retrieval is powered by the uploaded vector store, so large documents stay searchable.
            </p>
            <button
              type="submit"
              disabled={!vectorStoreId || !draft.trim() || isSendingMessage}
              className="rounded-full bg-slate-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-700 disabled:cursor-not-allowed disabled:bg-slate-400 dark:bg-slate-100 dark:text-slate-900 dark:hover:bg-slate-300 dark:disabled:bg-slate-600 dark:disabled:text-slate-200"
            >
              {isSendingMessage ? "Thinking..." : "Send"}
            </button>
          </div>

          {chatError ? (
            <p className="mt-3 text-sm text-red-600 dark:text-red-400">
              {chatError}
            </p>
          ) : null}
        </form>
      </section>
    </div>
  );
}
