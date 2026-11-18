# BrandGuard

BrandGuard is a React + Vite frontend and Python + FastAPI service for reviewing advertising claims, poster text, video frames, evidence and trust records. It is a human-review aid, not a legal-compliance certificate or automated approval system.

## Current capabilities

- Existing Tesseract OCR passes, multilingual selection, OCR region grouping and confidence presentation.
- Claim analysis, critical-value review, disclaimer/QR/manipulation checks, risk alerts, website truth checks, Fake Review Analysis, Brand DNA and copy-improvement guidance.
- Evidence matching for extracted claims, with missing/expired/questionable states. Text files are read as text and images are OCRed; PDF contents are not reliably extracted in this build. Matching does not establish authenticity or legal compliance.
- Sampled video-frame OCR and timestamped claim/disclaimer findings. Audio transcription is not configured, and brief text between sampled frames may be missed.
- One-Upload Review starts the existing applicable image/video checks and collects their results in a local report. Unsupported external checks remain clearly marked unable to verify or skipped.
- Trust Passport image hashes, QR generation and public read-only record verification. Public submissions are always `NEEDS REVIEW`; only a server-authorized reviewer can set an official outcome.
- AI Poster Generator is a deterministic local composition engine with editable copy/style/size/theme fields and a human approval gate before download. It is not third-party generative AI.
- Settings stores browser-local display/language preferences only; it does not grant reviewer permissions or store credentials.

See [FINAL_VERIFICATION_REPORT.md](./FINAL_VERIFICATION_REPORT.md) for the actual test matrix and [DEPLOYMENT_GUIDE.md](./DEPLOYMENT_GUIDE.md) for the deployment prerequisites and free-tier limitations.

## Requirements

- Node.js compatible with the Vite version in `package.json`.
- Python 3.10+ and the packages in `backend/requirements.txt`.
- Tesseract OCR installed separately, with the language packs you plan to use.
- On Windows, the current backend detects `C:\Program Files\Tesseract-OCR\tesseract.exe`; otherwise Tesseract must be on `PATH`.

## Run locally (Windows PowerShell)

From the project root, install frontend dependencies and start Vite:

```powershell
npm ci
$env:VITE_API_BASE_URL = 'http://127.0.0.1:8000'
npm run dev
```

In another PowerShell window:

```powershell
py -m venv backend/.venv
backend/.venv/Scripts/Activate.ps1
python -m pip install -r backend/requirements.txt
$env:BRANDGUARD_ALLOWED_ORIGINS = 'http://localhost:5173,http://127.0.0.1:5173'
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

Run the backend commands from the `backend` directory. Open the Vite URL printed by the frontend. The health endpoint is `http://127.0.0.1:8000/api/health`; interactive API docs are at `/docs`.

For a LAN demo, set Vite's `--host 0.0.0.0`, run the backend with `--host 0.0.0.0`, use the computer's LAN IP in `VITE_API_BASE_URL`, and include the frontend origin in `BRANDGUARD_ALLOWED_ORIGINS`. This does not make the application publicly reachable or provide HTTPS.

## Configuration

- Root `.env` / build environment: `VITE_API_BASE_URL` is the backend origin. Vite embeds this value at build time; use the actual public HTTPS API URL only after deployment.
- Backend environment: copy `backend/.env.example` as a starting point. Set CORS to exact trusted frontend origins. Keep `BRANDGUARD_REVIEWER_TOKEN` server-side only.
- `BRANDGUARD_PUBLIC_URL` controls the backend URL embedded in Trust Passport QR codes.
- `BRANDGUARD_FRONTEND_URL` controls whether a unified report receives a public HTTPS verification QR. Its public route is `/#/verify/<report-id>`.
- `BRANDGUARD_DATA_DIR` selects where SQLite databases are stored. Use a durable mounted volume if records must survive service restarts.
- Never commit `.env` files or expose backend secrets through `VITE_*` variables.

Example files contain local defaults and placeholders only. Public deployment and public QR verification have not been tested.

## API highlights

Existing analyzer endpoints include `/api/ocr`, `/api/analyze-claims`, `/api/verify-claims-evidence`, `/api/analyze-video`, `/api/detect-disclaimer`, `/api/detect-qr`, `/api/manipulation-check`, `/api/truth-check`, `/api/fake-reviews`, `/api/brand-dna`, `/api/risk-alert`, `/api/improve-ad`, `/api/generate-poster`, and `/api/trust-passport/`.

The One-Upload Review flow uses:

- `POST /api/unified-analysis` — accepts one image or video and queues the existing applicable checks.
- `GET /api/unified-analysis/{job_id}` — returns job progress/results.
- `GET /api/analysis-reports/{report_id}` — returns a limited, read-only public report after the job finishes.

The report ID identifies a stored record; cryptographic report-integrity verification is not implemented. Public report access does not establish that claims are true.

## Checks

```powershell
npm.cmd run lint
npm.cmd run build
backend/venv/Scripts/python.exe -m compileall -q backend
```

There is no automated test suite configured in `package.json` or `backend/`. The final verification report distinguishes direct browser/API checks from checks not performed.

## Honest limitations

- OCR may misread small, blurry, stylized or multilingual text; review extracted text and confidence.
- Video analysis samples frames and can miss brief text between samples. Audio transcription is not configured.
- Evidence matching does not prove document authenticity, scope, issuer, legal compliance or claim truth. PDF extraction is not supported reliably.
- Price/discount and food/regulatory claims require authoritative comparison sources that are not configured in the demo.
- Website truth checking is a text comparison, not proof that a claim is false. Private, loopback and reserved destinations are rejected.
- Fake-review, manipulation, risk and completeness results are heuristic indicators for human review.
- The poster output is locally composed and deterministic; no third-party generative AI is configured.
- SQLite and uploaded report persistence depend on the selected host's durable storage. A free sleeping/ephemeral host is not suitable for durable Trust Passport/report records.
- No public deployment, external QR scan, accessibility certification or production security certification has been completed.

## Deploy (Docker backend + Vercel frontend)

1. **Backend (Render, Docker):** create a Web Service from this repo using `render.yaml` (or set Root Directory `backend`, runtime Docker). Set `BRANDGUARD_PUBLIC_URL`, `BRANDGUARD_FRONTEND_URL`, `BRANDGUARD_ALLOWED_ORIGINS`; `BRANDGUARD_REVIEWER_TOKEN` is generated. Confirm `<backend-url>/api/health` returns `healthy` with the language packs listed.
2. **Frontend (Vercel):** import the repo, set `VITE_API_BASE_URL` to the backend URL, deploy. Then set the two backend URL variables to the final addresses and redeploy the backend.
3. Free Render instances sleep and have an ephemeral disk: records reset on redeploy. Open `/api/health` once before a demo to wake the server.
4. The Dockerfile and render.yaml were written without a test build; check the first deploy log.
