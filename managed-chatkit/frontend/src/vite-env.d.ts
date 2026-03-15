/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_URL?: string;
  readonly VITE_CHATKIT_API_BASE?: string;
  readonly VITE_CHATKIT_WORKFLOW_ID?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
