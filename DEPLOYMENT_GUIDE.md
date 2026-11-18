# BrandGuard deployment guide

Status: preparation only. No hosting account was connected, no service was created, and no public deployment or external QR scan was performed.

## Current release blockers

1. There is no production API URL or domain yet. The frontend's `VITE_API_BASE_URL` is compiled into the Vite build, so it must be set before the production build.
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
3. Confirm the backend health endpoint and supported OCR languages before building the frontend.
4. Build the static frontend with `VITE_API_BASE_URL` set to the public API origin. Never put reviewer tokens or private API keys in a `VITE_*` variable.
5. Publish the frontend only after the API is reachable and CORS is configured. Publishing/deployment is outside this verification and requires your approval.

## Post-deployment acceptance checks

Run these from a device/network outside the hosting environment; localhost and LAN tests are not substitutes:

- Open the public frontend over HTTPS on desktop and mobile.
- Confirm `/api/health` responds through the configured API origin and all required OCR language models are present.
- Upload a generated test poster. Confirm the UI polls the job to completion, shows OCR and module states, and does not label unavailable evidence/price/food sources as verified.
- Upload a short generated video. Confirm timestamped sampled-frame findings are visible; audio remains `NOT TESTED` unless transcription is explicitly configured.
- Create a Trust Passport and confirm the public submission is `NEEDS REVIEW`, risk `0`, reviewer `UNASSIGNED`.
- Verify the passport by scanning its QR using a second device on mobile data. Confirm the QR URL is public HTTPS and returns the same record.
- Confirm unauthenticated reviewer listing/update requests are denied; authorized reviewer actions work only with the backend secret.
- Check the unified report QR opens `/#/verify/<report-id>` and the report endpoint returns only the intended public fields.
- Re-check CORS, redirect/private-address rejection in website truth checking, logs, storage persistence after restart, and backup/restore behavior.

Until those external checks pass, report public deployment and live QR verification as `NOT TESTED`.
