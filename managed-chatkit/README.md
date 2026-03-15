# Managed ChatKit starter

Vite + React UI that talks to a FastAPI session backend for creating ChatKit
workflow sessions.

## Deploy to Vercel

This starter can be deployed as a single Vercel project rooted at this
`managed-chatkit` directory.

What Vercel uses:

- `frontend/dist` for the static Vite build
- `api/create-session.py` and `api/health.py` for the FastAPI backend routes
- `vercel.json` for the build/output settings

Recommended Vercel project settings:

- Root Directory: `openai-chatkit-starter-app/managed-chatkit`
- Framework Preset: `Other`
- Build Command: `npm run frontend:build`
- Output Directory: `frontend/dist`

Required Vercel environment variables:

- `OPENAI_API_KEY`
- `VITE_CHATKIT_WORKFLOW_ID`

Optional Vercel environment variables:

- `CHATKIT_WORKFLOW_ID` if you prefer the backend to own the workflow id
- `CHATKIT_API_BASE` or `VITE_CHATKIT_API_BASE`
- `VITE_API_URL` only if you deploy the backend somewhere other than the same
  Vercel project

After adding env vars, redeploy and verify:

- `https://<your-domain>/`
- `https://<your-domain>/api/create-session`
- `https://<your-domain>/api/health`

## Quick start

```bash
npm install           # installs root deps (concurrently)
npm run dev           # runs FastAPI on :8000 and Vite on :3000
```

What happens:

- `npm run dev` runs the backend via `backend/scripts/run.sh` (FastAPI +
  uvicorn) and the frontend via `npm --prefix frontend run dev`.
- The backend exposes `/api/create-session`, exchanging your workflow id and
  `OPENAI_API_KEY` for a ChatKit client secret. The Vite dev server proxies
  `/api/*` to `127.0.0.1:8000`.

## Required environment

- `OPENAI_API_KEY`
- `VITE_CHATKIT_WORKFLOW_ID`
- (optional) `CHATKIT_API_BASE` or `VITE_CHATKIT_API_BASE` (defaults to `https://api.openai.com`)
- (optional) `VITE_API_URL` (override the dev proxy target for `/api`)

Set the env vars in your shell (or process manager) before running. Use a
workflow id from Agent Builder (starts with `wf_...`) and an API key from the
same project and organization.

## Customize

- UI: `frontend/src/components/ChatKitPanel.tsx`
- Session logic: `backend/app/main.py`
