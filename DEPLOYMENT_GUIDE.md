# BrandGuard deployment guide

Status (2026-11-22): partial deployment verification. The public Vercel frontend https://brandguard-seven.vercel.app/ loads and renders the BrandGuard dashboard. Earlier project history records a Render backend deployment as user-reported, but the exact public API URL is not recorded in this repository and could not be independently recovered. A request to https://brandguard-seven.vercel.app/api/health returned HTTP 500; this is not a verified Render API health check. Do not mark backend health, end-to-end public workflows, or external QR verification as verified until the exact Render API URL is tested.

## Current release blockers

1. The exact production API URL is not documented in the repository. Confirm the Render service's public HTTPS URL and verify `/api/health`. The frontend's `VITE_API_BASE_URL` is compiled into the Vite build, so it must point to that API before a production rebuild.
2. FastAPI requires Tesseract and language model files on the host; this repository does not provision those operating-system packages.
3. Trust Passport and One-Upload reports use SQLite. The host must provide durable storage and the backend must set `BRANDGUARD_DATA_DIR` to that mount. Do not put real submissions on an ephemeral filesystem.
4. Public QR links are only correct after both `BRANDGUARD_PUBLIC_URL` (backend API URL) and `BRANDGUARD_FRONTEND_URL` (frontend HTTPS URL) are configured and reachable.
5. Set `BRANDGUARD_ALLOWED_ORIGINS` to the exact frontend origin(s). Do not use wildcard origins with credentials.
6. Configure a long random `BRANDGUARD_REVIEWER_TOKEN` as a backend secret before using the reviewer workflow. Do not expose it to the browser or commit it.

## Suggested hosting shape

- Frontend: static Vite site. Vercel documents Vite support and serves the `dist` output; the build-time `VITE_API_BASE_URL` must point to the API.
- Backend: a Python ASGI host that provides Tesseract, OpenCV's required system libraries, HTTPS, environment secrets and durable database storage.
- Keep the current SQLite design only if the chosen backend host supplies a persistent mounted disk and its backup/restore behavior is acceptable. Otherwise, a database migration is a separate project decision and is not included here.

The free Render web-service tier sleeps after inactivity and uses an ephemeral filesystem; its free Postgres option is time-limited. That combination is suitable only for a disposable demo, not durable Trust Passport/report records. Persistent disks are paid. No paid service is being requested or provisioned here. Verify current plan details before choosing a host.

Official provider references checked 2026-11-18: [Vercel Vite deployment](https://vercel.com/docs/frameworks/frontend/vite), [Render free service limits](https://render.com/docs/free), [Render FastAPI deployment](https://render.com/docs/deploy-fastapi), and [Render persistent disks](https://render.com/docs/disks).

## Configuration sequence after you choose a host

1. Provision the backend with Python dependencies, system Tesseract plus required language models, OpenCV runtime libraries, HTTPS, and a durable data directory.
2. Set backend environment variables from `backend/.env.example`:
   - `BRANDGUARD_DATA_DIR` to the durable mount.
   - `BRANDGUARD_PUBLIC_URL` to the public API origin, without a trailing slash.
   - `BRANDGUARD_FRONTEND_URL` to the public frontend origin, without a trailing slash.
   - `BRANDGUARD_ALLOWED_ORIGINS` to the exact frontend origin.
   - `BRANDGUARD_REVIEWER_TOKEN` as a secret in the hosting dashboard.
3. Confirm `GET /api/health` (liveness/diagnostics) and `GET /api/ready` (readiness; requires Tesseract and English OCR) before building the frontend.
4. Build the static frontend with `VITE_API_BASE_URL` set to the public API origin. Never put reviewer tokens or private API keys in a `VITE_*` variable.
5. The frontend is already publicly reachable on Vercel. Rebuild/redeploy it only after confirming the Render API URL, backend health and CORS. Do not replace a working deployment with a localhost-configured build.

## Post-deployment acceptance checks

Run these from a device/network outside the hosting environment; localhost and LAN tests are not substitutes:

- Open the public frontend over HTTPS on desktop and mobile.
- Confirm `/api/health` returns diagnostics and `/api/ready` returns HTTP 200 with English OCR available; check optional language models separately.
- Upload a generated test poster. Confirm the UI polls the job to completion, shows OCR and module states, and does not label unavailable evidence/price/food sources as verified.
- Upload a short generated video. Confirm timestamped sampled-frame findings are visible; audio remains `NOT TESTED` unless transcription is explicitly configured.
- Create a Trust Passport and confirm the public submission is `NEEDS REVIEW`, risk `0`, reviewer `UNASSIGNED`.
- Verify the passport by scanning its QR using a second device on mobile data. Confirm the QR URL is public HTTPS and returns the same record.
- Confirm unauthenticated reviewer listing/update requests are denied; authorized reviewer actions work only with the backend secret.
- Check the unified report QR opens `/#/verify/<report-id>` and the report endpoint returns only the intended public fields.
- Re-check CORS, redirect/private-address rejection in website truth checking, logs, storage persistence after restart, and backup/restore behavior.

Until the exact Render API URL passes the external health and workflow checks, report backend deployment health and end-to-end public operation as `NOT VERIFIED`; report external QR verification as `NOT TESTED`.


## Frontend API routing

The Vite frontend uses `VITE_API_BASE_URL` when supplied. If omitted, production builds use same-origin relative API paths (served through the `/api/*` rewrite in `vercel.json`); local development defaults to `http://127.0.0.1:8000`. If the backend is hosted separately (for example, a dedicated Render service), set `VITE_API_BASE_URL` to that service's public HTTPS origin in the Vercel Production environment and redeploy the frontend. Never set this to localhost in a public deployment.

## Dependency consistency

The repository-root `requirements.txt` is the Vercel/root deployment dependency set; `backend/requirements.txt` is the backend container dependency set. Keep their application package versions aligned. Both use the headless OpenCV wheel to avoid GUI dependencies in hosted Linux environments. The backend Dockerfile installs Tesseract and its language data separately from Python packages.
