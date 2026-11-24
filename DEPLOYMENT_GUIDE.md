# BrandGuard deployment guide

**Live deployment check — 2026-11-24**

- Frontend: https://brandguard-seven.vercel.app/ — fetched successfully and the BrandGuard dashboard rendered.
- Backend: https://brandguard-backend-fxhr.onrender.com/ — the exact Render API origin is configured as the production fallback in `src/lib/api.js`.
- `GET /api/health` — returned `healthy`, API version `3.0.0`, Tesseract `5.5.0`, with all 14 configured OCR language models installed.
- `GET /api/ready` — returned `ready`; no missing optional language models were reported.
- Optional providers: the live readiness response reported `tavily_configured=false` and `gemini_configured=false`.

These checks establish that the frontend renders and the backend health/readiness endpoints respond. They do **not** establish that every browser workflow, public report, QR scan, external integration or storage behavior has been tested end to end.

## Deployment topology

- **Frontend:** React + Vite static application on Vercel.
- **Backend:** Python + FastAPI service on Render.
- **API routing:** the frontend uses `VITE_API_BASE_URL` when set. In production, the current source falls back to `https://brandguard-backend-fxhr.onrender.com`; local development falls back to `http://127.0.0.1:8000`.
- **Vercel Services configuration:** `vercel.json` declares frontend and backend services and rewrites `/api/*` to the backend service. The deployed frontend's configured API origin is still the Render URL fallback unless overridden at build time.

## Required backend configuration

Use `backend/.env.example` as a reference. Configure secrets and deployment-specific values in the hosting dashboard, not in committed files.

- `BRANDGUARD_ALLOWED_ORIGINS` — exact trusted frontend origins. Do not use wildcard origins with credentials.
- `BRANDGUARD_PUBLIC_URL` — public backend API origin used in Trust Passport QR links.
- `BRANDGUARD_FRONTEND_URL` — public frontend origin used in unified-report QR links.
- `BRANDGUARD_DATA_DIR` — durable mounted directory for SQLite records and report data.
- `BRANDGUARD_REVIEWER_TOKEN` — long random backend-only secret for reviewer operations. Never expose it to the browser or use a `VITE_*` variable.
- `TAVILY_API_KEY` and `GEMINI_API_KEY` — optional backend-only provider keys. The live readiness endpoint currently reports both integrations as not configured. Do not describe autonomous live research as operational until keys are configured and real provider calls are verified.
- Tesseract and the required language model files must be installed on the backend host. The live service currently reports Tesseract 5.5.0 and 14 installed OCR language models.

## Local development

From the repository root, start the frontend:

```powershell
npm ci
$env:VITE_API_BASE_URL = 'http://127.0.0.1:8000'
npm run dev
```

In a second PowerShell window:

```powershell
py -m venv backend/.venv
backend/.venv/Scripts/Activate.ps1
python -m pip install -r backend/requirements.txt
$env:BRANDGUARD_ALLOWED_ORIGINS = 'http://localhost:5173,http://127.0.0.1:5173'
Set-Location backend
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

Open the Vite URL printed by the frontend. Local API docs are at `http://127.0.0.1:8000/docs`.

## Post-deployment acceptance checks

Run these from a device/network outside the hosting environment. A successful health endpoint is necessary but not sufficient.

1. Open the public frontend over HTTPS on desktop and mobile.
2. Confirm `GET /api/health` returns runtime diagnostics and `GET /api/ready` returns readiness with English OCR available. Check optional language models separately.
3. Upload a generated test poster. Confirm the UI polls the job to completion, shows OCR and module states, and does not label unavailable evidence, price or food sources as verified.
4. Upload a short generated video. Confirm timestamped sampled-frame findings are visible. Audio must remain untranscribed unless an approved speech-to-text service is configured.
5. Supply evidence files and confirm text overlap results remain `UNDER_REVIEW` or `INSUFFICIENT`, never automatically `SUPPORTED`.
6. Create a Trust Passport and confirm a public submission cannot assign reviewer status, risk score or reviewer identity.
7. Scan a public QR using a second device on mobile data. Confirm the QR URL is public HTTPS and returns the intended read-only record.
8. Confirm unauthenticated reviewer listing/update requests are denied; authorized reviewer actions require the backend secret.
9. Confirm a unified report QR opens `/#/verify/<report-id>` and the public endpoint returns only intended fields.
10. Check CORS, private/loopback/reserved URL rejection in website truth checking, logs, persistence after restart, and backup/restore behavior.

## Storage and free-tier caution

Trust Passport and One-Upload reports use SQLite. Their durability depends on the host's filesystem. A sleeping service or ephemeral filesystem can lose records on restart/redeploy and is not suitable for durable records. Use a persistent mounted disk and verify backup/restore before treating records as durable. The current deployment's persistence across host restarts has not been tested.

Free hosting may sleep after inactivity and may use ephemeral storage or impose resource limits. Treat the current service as a demonstration deployment unless persistence, uptime and recovery have been verified. Check the hosting provider's current plan terms before making production commitments.

## Current verification boundary

**Verified on 2026-11-24:** public frontend page rendering; Render backend `/api/health`; Render backend `/api/ready`; Tesseract version and installed language-model inventory; optional Tavily/Gemini configuration status.

**Not verified in this check:** complete public upload-to-report workflows; public QR scanning from an external device; database persistence after host restart; backup/restore; production CORS from all client origins; live Tavily/Gemini provider calls; accessibility certification; penetration testing; production security certification.

Do not turn an endpoint health result into a claim that all application features have passed production testing.
