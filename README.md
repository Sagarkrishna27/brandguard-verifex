# BrandGuard

**BrandGuard** is an advertising-review workspace built by **Team Verifex** for CodeZen. It helps reviewers inspect poster and video advertisements, extract claims, compare supplied evidence, identify potential risk signals, and prepare clearer creative. It is a decision-support tool: it does not certify that an advertisement or claim is true, legally compliant, safe, or approved.

- **Live application:** https://brandguard-seven.vercel.app/
- **Backend API:** https://brandguard-backend-fxhr.onrender.com/
- **Interactive API docs:** https://brandguard-backend-fxhr.onrender.com/docs
- **Source repository:** https://github.com/Sagarkrishna27/brandguard-verifex
- **Deployment and test notes:** [DEPLOYMENT_GUIDE.md](./DEPLOYMENT_GUIDE.md) · [FINAL_VERIFICATION_REPORT.md](./FINAL_VERIFICATION_REPORT.md)

## What BrandGuard includes

### Unified poster and video review

The One-Upload Review workflow accepts one poster image or video, queues the applicable checks, tracks each module state, and produces a consolidated report. A module can finish as `COMPLETED`, `UNABLE_TO_VERIFY`, `SKIPPED`, or `FAILED`; unavailable evidence is not silently converted into a successful verification.

The image workflow includes multilingual OCR, OCR regions, critical values, claim analysis, evidence and Proof & Claim review, disclaimers, QR detection, manipulation/forensics triage, evaluation, risk, price/discount and food checks, preliminary legal screening, copy improvement, completeness review, and report generation. The video workflow applies corresponding checks to sampled frames and a video timeline.

### Feature inventory

The following describes the implemented product behavior. Source-dependent or heuristic checks are not proof of a claim.

1. **Unified poster and video analysis** — one upload starts applicable checks and consolidates their states/results.
2. **Multilingual OCR** — Tesseract OCR supports English and 13 Indian-language models: Hindi, Kannada, Tamil, Telugu, Malayalam, Bengali, Gujarati, Marathi, Punjabi, Odia, Assamese, Urdu and Sanskrit. The live backend currently reports all 14 language models installed.
3. **OCR region analysis** — groups extracted text into poster regions such as headline, offer/promo code, conditions and footer.
4. **Critical Value Review** — highlights important values such as prices, discounts, percentages, dates and offer details for review.
5. **Advertisement Claim Analysis** — identifies claim wording and categories using the existing claim-analysis rules.
6. **Claim Evidence Analysis** — compares extracted claims with documents supplied by the reviewer and reports missing, insufficient or review-required evidence.
7. **Proof & Claim** — connects claims to the evidence required to substantiate them; text overlap is only a triage signal and never automatically marks evidence as supported.
8. **Disclaimer Detection** — flags disclaimer-like wording for a human readability and prominence check.
9. **QR Code Detection** — detects and decodes QR codes in supported images and sampled video frames.
10. **Image Manipulation Detection** — applies image-forensics heuristics; results are indicators, not proof of editing.
11. **Multimodal Media Forensics** — provides image/video forensic triage and optional face-region analysis. It is not a trained deepfake classifier; synthetic voice/face classification and audio transcription are not configured.
12. **Advertisement Evaluation** — consolidates applicable review findings for human assessment.
13. **Risk Alerts** — summarizes signals into heuristic risk indicators, not a calibrated certification.
14. **AI Legal Compliance Intelligence** — preliminary keyword/rule-based screening with references to selected ASCI and CCPA guidance; it is not a complete legal assessment or legal advice.
15. **Autonomous Advertisement Investigation** — includes optional Tavily public-source search and Gemini preliminary source assessment. Both providers are currently reported as not configured by the live readiness endpoint, so live research is unavailable in the current deployment until valid server-side keys are configured.
16. **Advertisement Improvement Assistant** — provides rule-based, editable copy suggestions; it does not silently change the original advertisement.
17. **Advertisement Completeness Review** — flags potentially missing information for human review.
18. **Price and Discount Verification** — identifies price/offer details and can report when authoritative comparison data is unavailable; no authoritative price-history/comparison source is configured in the current demo.
19. **Website Truth Checker** — compares advertisement text with text retrieved from a supplied website. This is not proof that a claim is false or true. Private, loopback and reserved destinations are rejected.
20. **Food Advertisement Verification** — identifies food-related claims and the evidence they may need. Official FSSAI sources, lab reports and accreditation records are not automatically supplied by the current demo.
21. **Shareable verification reports and QR codes** — generates report/Trust Passport records and QR links. Public records are read-only and require human review; external QR scanning and durable persistence across host restarts have not been verified.

**Additional workspace tools:** Fake Review Analysis uses linguistic heuristics; Brand DNA creates a statistical profile from supplied scan history; the AI Poster Generator creates a deterministic, locally composed poster with editable copy/style/size/theme and a human approval step. The poster generator is not connected to a third-party generative-image service.

## Architecture and data flow

- **Frontend:** React with Vite, deployed at Vercel.
- **Backend:** Python with FastAPI, deployed at Render.
- **Communication:** HTTPS REST API requests. The frontend reads `VITE_API_BASE_URL`; its production fallback is the Render API origin above, while local development defaults to `http://127.0.0.1:8000`.
- **OCR:** Tesseract through `pytesseract`, with language selection, preprocessing, multiple OCR passes, word confidence/coordinates and grouped regions.
- **Image/video processing:** Pillow and OpenCV; video review samples frames and attaches timestamps to findings.
- **Evidence extraction:** text decoding, OCR for image evidence, and bounded selectable-text PDF extraction using `pypdf`.
- **Storage:** SQLite for analysis jobs/reports and Trust Passport records. Durable records require a persistent mounted data directory configured with `BRANDGUARD_DATA_DIR`.
- **Optional integrations:** Tavily and Gemini are server-side optional integrations. The current live readiness response reports both as not configured. Never expose provider keys in frontend variables or commit them.
- **QR/report flow:** the backend creates report records and QR URLs; public report routes expose limited read-only data. Report IDs are not cryptographic proof of report integrity.

### Main unified-analysis endpoints

- `POST /api/unified-analysis` — upload an image or video and create a job.
- `GET /api/unified-analysis/{job_id}` — retrieve job progress and module results.
- `GET /api/analysis-reports/{report_id}` — retrieve the limited public report.
- `GET /api/health` — liveness and runtime diagnostics.
- `GET /api/ready` — readiness check for required OCR runtime.
- `/docs` — interactive FastAPI documentation.

Other analyzer endpoints include `/api/ocr`, `/api/analyze-claims`, `/api/verify-claims-evidence`, `/api/analyze-video`, `/api/detect-disclaimer`, `/api/detect-qr`, `/api/manipulation-check`, `/api/media-forensics`, `/api/truth-check`, `/api/fake-reviews`, `/api/brand-dna`, `/api/risk-alert`, `/api/improve-ad`, and `/api/generate-poster`. See `/docs` for the deployed API schema.

## Run locally (Windows PowerShell)

Requirements: Node.js compatible with the Vite version in `package.json`, Python 3.10+, Tesseract installed separately, and the language packs you intend to use.

From the repository root:

```powershell
npm ci
$env:VITE_API_BASE_URL = 'http://127.0.0.1:8000'
npm run dev
```

In another PowerShell window, from the repository root:

```powershell
py -m venv backend/.venv
backend/.venv/Scripts/Activate.ps1
python -m pip install -r backend/requirements.txt
$env:BRANDGUARD_ALLOWED_ORIGINS = 'http://localhost:5173,http://127.0.0.1:5173'
Set-Location backend
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

Open the Vite URL printed by the frontend. Local API docs are at `http://127.0.0.1:8000/docs`.

On Windows, the backend also checks `C:\Program Files\Tesseract-OCR\tesseract.exe`; otherwise Tesseract must be available on `PATH`.

## Configuration and security

- Set `VITE_API_BASE_URL` to the backend origin at frontend build time when using a different API host.
- Configure `BRANDGUARD_ALLOWED_ORIGINS` with exact trusted frontend origins.
- Configure `BRANDGUARD_PUBLIC_URL` and `BRANDGUARD_FRONTEND_URL` for public QR links.
- Set `BRANDGUARD_DATA_DIR` to a durable mounted directory if report/Trust Passport records must survive restarts.
- Set `BRANDGUARD_REVIEWER_TOKEN` only as a backend secret. It must never be sent to the browser or stored in a `VITE_*` variable.
- Configure `TAVILY_API_KEY` and `GEMINI_API_KEY` only in backend secrets if enabling public-source investigation and optional AI workflows.
- Never commit real `.env` files, tokens or provider keys.

## Testing and current live verification

The latest recorded repository verification run (2026-11-22) reported:
- Frontend lint and production build passed.
- Backend compilation passed.
- Backend pytest suite: **29 passed**, with one Starlette/httpx deprecation warning.
- Local unified image and video workflows completed with explicit partial/unavailable/skipped module states.
- Local Trust Passport authorization checks rejected unauthenticated reviewer operations.

A live endpoint check on **2026-11-24** confirmed:
- Frontend: `https://brandguard-seven.vercel.app/` rendered the BrandGuard dashboard.
- Backend `/api/health`: `healthy`, API version `3.0.0`, Tesseract `5.5.0`; all 14 configured OCR language models were installed.
- Backend `/api/ready`: `ready`; no missing optional language models were reported.
- Optional integration status: `tavily_configured=false` and `gemini_configured=false`.

These live checks verify page rendering and API liveness/readiness, not every end-to-end user workflow. The feature-level test matrix and known limitations are recorded in [FINAL_VERIFICATION_REPORT.md](./FINAL_VERIFICATION_REPORT.md).

## Honest limitations

- OCR may misread small, blurry, stylized or multilingual text; review extracted text and confidence. Installed language packs do not establish recognition accuracy for every language or image.
- Video analysis samples frames and can miss brief text between samples. Audio transcription is not configured.
- Face-region detection is optional and may return `NOT_CONFIGURED` when the installed OpenCV build lacks the required classifier API/data. No trained deepfake model classifies synthetic faces or voices.
- Evidence matching does not prove document authenticity, scope, issuer, legal compliance or claim truth. Selectable-text PDFs can be parsed with bounded `pypdf` extraction (up to 100 pages and 1 MB of extracted text); scanned PDFs without a text layer still require OCR. Extraction and layout accuracy are not guaranteed.
- Price/discount and food/regulatory claims require authoritative comparison sources that are not configured in the demo.
- Website truth checking is a text comparison, not proof that a claim is false or true. Private, loopback and reserved destinations are rejected.
- Legal compliance screening uses keyword/rule-based preliminary indicators and selected references; it is not a complete legal assessment or legal advice. Human review is required.
- Autonomous Advertisement Investigation has Tavily/Gemini integration code, but the live backend currently reports both providers as not configured. Live provider research has therefore not been verified in this deployment. Search snippets and AI assessments are not proof.
- Fake-review, manipulation, risk and completeness results are heuristic indicators for human review.
- The poster output is locally composed and deterministic; no third-party generative AI is configured.
- SQLite and uploaded report persistence depend on the selected host's durable storage. Persistence across host restarts and backups have not been verified.
- External QR scanning, production CORS behavior, accessibility certification, penetration testing and production security certification have not been verified.
- A healthy/readiness API response does not prove that every frontend-to-backend workflow works end to end.

## Roadmap

1. Improve multilingual OCR accuracy and layout recognition with representative labelled poster sets, including Kannada, Hindi and mixed scripts.
2. Strengthen claim extraction and evidence matching, including document scope, dates, issuer and source quality while preserving human review.
3. Improve image/video forensic triage and evaluate against labelled manipulated/unaltered samples.
4. Configure and validate optional public-source investigation providers before presenting it as live.
5. Maintain current advertising-compliance references and expand domain-specific source coverage.
6. Validate durable storage, backups, public QR scanning, CORS and end-to-end production workflows.
7. Expand testing across industries, languages, poster layouts and video formats.

---

BrandGuard is a verification assistant for advertisers, agencies and compliance teams. It helps organize review; final decisions remain with qualified humans.
