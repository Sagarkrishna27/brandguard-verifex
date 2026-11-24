"""Single-upload orchestration and public, read-only analysis reports.

This module coordinates existing BrandGuard checks. It deliberately reports
missing evidence and unavailable external verification as such; it does not
turn heuristic checks into approval decisions.
"""

import asyncio
import base64
import concurrent.futures
import io
import json
import os
import re
import secrets
import sqlite3
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import qrcode
from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from PIL import Image, ImageOps
from starlette.datastructures import Headers

import main as bg


router = APIRouter(tags=["Unified Advertisement Analysis"])
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv("BRANDGUARD_DATA_DIR", str(BASE_DIR))).expanduser().resolve()
DATA_DIR.mkdir(parents=True, exist_ok=True)
DATABASE_PATH = DATA_DIR / "brandguard_analysis.db"
MAX_VIDEO_BYTES = 200 * 1024 * 1024
MAX_IMAGE_BYTES = 15 * 1024 * 1024


def _connect():
    connection = sqlite3.connect(DATABASE_PATH, timeout=30)
    connection.row_factory = sqlite3.Row
    return connection


def _initialize_database():
    with _connect() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS analysis_jobs (
                id TEXT PRIMARY KEY,
                report_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                filename TEXT NOT NULL,
                media_type TEXT NOT NULL,
                languages TEXT NOT NULL DEFAULT 'eng',
                temp_path TEXT NOT NULL,
                status TEXT NOT NULL,
                modules_json TEXT NOT NULL,
                report_json TEXT,
                error TEXT
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS analysis_reports (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                payload_json TEXT NOT NULL
            )
        """)
        columns = {row[1] for row in connection.execute("PRAGMA table_info(analysis_jobs)")}
        if "languages" not in columns:
            connection.execute("ALTER TABLE analysis_jobs ADD COLUMN languages TEXT NOT NULL DEFAULT 'eng'")
        connection.commit()


_initialize_database()
_MODULE_UPDATE_LOCK = threading.RLock()


IMAGE_MODULES = [
    ("ocr", "Multilingual OCR"),
    ("ocr_regions", "OCR Region Analysis"),
    ("critical_values", "Critical Value Review"),
    ("claim_analysis", "Claim Analysis"),
    ("claim_evidence", "Claim Evidence Analysis"),
    ("proof_claim", "Proof & Claim"),
    ("disclaimer", "Disclaimer Detection"),
    ("qr", "QR Detection"),
    ("manipulation", "Image Manipulation Detection"),
    ("evaluation", "Advertisement Evaluation"),
    ("risk", "Risk Alerts"),
    ("price_discount", "Price and Discount Verification"),
    ("website_truth", "Website Truth Checker"),
    ("food_verification", "Food Advertisement Verification"),
    ("improvement", "Advertisement Improvement Assistant"),
    ("completeness", "Advertisement Completeness Review"),
    ("verification_report", "Verification Report and QR"),
]

VIDEO_MODULES = [
    ("video_validation", "Video Validation and Timeline"),
    ("frame_ocr_claims", "Sampled Frame OCR and Claims"),
    ("ocr_regions", "OCR Region Analysis"),
    ("critical_values", "Critical Value Review"),
    ("claim_evidence", "Claim Evidence Analysis"),
    ("proof_claim", "Proof & Claim"),
    ("disclaimer", "Disclaimer Detection"),
    ("qr", "QR Detection in Sampled Frames"),
    ("manipulation", "Frame Manipulation Checks"),
    ("evaluation", "Advertisement Evaluation"),
    ("risk", "Risk Alerts"),
    ("price_discount", "Price and Discount Verification"),
    ("website_truth", "Website Truth Checker"),
    ("food_verification", "Food Advertisement Verification"),
    ("improvement", "Advertisement Improvement Assistant"),
    ("completeness", "Advertisement Completeness Review"),
    ("verification_report", "Verification Report and QR"),
]


def _now():
    return datetime.now(timezone.utc).isoformat()


def _new_id():
    return secrets.token_urlsafe(24)


def _load_job(job_id):
    with _connect() as connection:
        row = connection.execute("SELECT * FROM analysis_jobs WHERE id = ?", (job_id,)).fetchone()
    return row


def _update_job(job_id, *, status=None, modules=None, report=None, error=None):
    fields = []
    values = []
    if status is not None:
        fields.append("status = ?")
        values.append(status)
    if modules is not None:
        fields.append("modules_json = ?")
        values.append(json.dumps(modules, ensure_ascii=False, default=str))
    if report is not None:
        fields.append("report_json = ?")
        values.append(json.dumps(report, ensure_ascii=False, default=str))
    if error is not None:
        fields.append("error = ?")
        values.append(error)
    if not fields:
        return
    values.append(job_id)
    with _connect() as connection:
        connection.execute(f"UPDATE analysis_jobs SET {', '.join(fields)} WHERE id = ?", values)
        connection.commit()


def _set_module(job_id, module_id, status, message="", result=None):
    with _MODULE_UPDATE_LOCK:
        row = _load_job(job_id)
        if row is None:
            return
        modules = json.loads(row["modules_json"])
        for module in modules:
            if module["id"] == module_id:
                module.update({"status": status, "message": message})
                if result is not None:
                    module["result"] = result
                break
        _update_job(job_id, modules=modules)


def _run_module(job_id, module_id, function):
    _set_module(job_id, module_id, "RUNNING", "Running")
    try:
        outcome = function()
        status = outcome.pop("_status", "COMPLETED") if isinstance(outcome, dict) else "COMPLETED"
        message = outcome.pop("_message", "Completed") if isinstance(outcome, dict) else "Completed"
        _set_module(job_id, module_id, status, message, outcome)
        return {"status": status, "message": message, "result": outcome}
    except Exception as error:  # one module failure must not discard other results
        message = str(getattr(error, "detail", error))[:500]
        _set_module(job_id, module_id, "FAILED", message)
        return {"status": "FAILED", "message": message, "result": None}


def _skip(message):
    return {"_status": "SKIPPED", "_message": message}


def _unable(message, result=None):
    output = {"_status": "UNABLE_TO_VERIFY", "_message": message}
    if result is not None:
        output["details"] = result
    return output


def _run_parallel(job_id, functions):
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(5, len(functions) or 1)) as executor:
        futures = {
            executor.submit(_run_module, job_id, module_id, function): module_id
            for module_id, function in functions.items()
        }
        return {futures[future]: future.result() for future in concurrent.futures.as_completed(futures)}


def _extract_urls(text):
    found = re.findall(r"https?://[^\s<>()\[\]{}\"']+", text or "", re.IGNORECASE)
    return list(dict.fromkeys(url.rstrip(".,;:!?'") for url in found))


def _food_check(text):
    food_signals = re.compile(r"\b(food|beverage|ingredient|nutrition|sugar[- ]?free|fssai|organic|protein|calorie|edible|supplement)\b", re.I)
    if not food_signals.search(text or ""):
        return _skip("No food-related terms were detected in the extracted text.")
    return _unable(
        "Food-related wording was detected, but no official FSSAI source, lab report, sample details, or accreditation record was supplied for this automated run.",
        {"legal_compliance_checked": False, "human_review_required": True},
    )


def _price_check(text):
    values = re.findall(r"(?:₹|Rs\.?\s*)\s?\d[\d,]*(?:\.\d{1,2})?|\b\d{1,3}\s?%\s?(?:off|discount)\b", text or "", re.I)
    return _unable(
        "Advertisement price/discount text can be extracted, but no verified same-product, size, location, coupon, and validity source was configured. No discount was independently confirmed.",
        {"detected_values": values, "calculation_performed": False, "purchase_performed": False},
    )


def _website_check(text, qr_result=None):
    urls = _extract_urls(text)
    decoded = (qr_result or {}).get("decoded_value")
    if isinstance(decoded, str) and decoded.lower().startswith(("http://", "https://")):
        urls = list(dict.fromkeys(urls + [decoded]))
    if not urls:
        return _skip("No website URL was found in OCR text or the decoded QR value.")
    results = []
    for url in urls[:3]:
        result = bg.truth_check_website(text, url)
        results.append({"url": url, "result": result})
    if not any(item["result"].get("success") for item in results):
        return _unable("A URL was found, but no public website comparison completed. Unsafe/private destinations are rejected.", results)
    return {"checked_urls": results, "_message": "Detected URLs were checked with the existing public-URL/redirect safeguards."}


def _completeness_check(text, disclaimer_result=None):
    value = text or ""
    checks = [
        {"item": "Advertiser or product identification", "present": bool(re.search(r"\b(brand|product|company|shop|store|by|from)\b", value, re.I)), "basis": "OCR text keyword signal only"},
        {"item": "Offer or price details", "present": bool(re.search(r"\b(off|sale|offer|deal|₹|rs\.?|price|%|discount)\b", value, re.I)), "basis": "OCR text pattern"},
        {"item": "Offer terms or validity", "present": bool(re.search(r"\b(terms|conditions|valid|until|till|expires|minimum|excludes)\b", value, re.I)), "basis": "OCR text pattern"},
        {"item": "Contact or destination", "present": bool(re.search(r"https?://|www\.|\b\w+@\w+\.|\+?\d[\d ()-]{7,}\d", value, re.I)), "basis": "OCR text pattern"},
        {"item": "Lower-area disclaimer text", "present": bool((disclaimer_result or {}).get("bottom_text_extracted")), "basis": "Existing disclaimer detector"},
    ]
    missing = [item["item"] for item in checks if not item["present"]]
    return {
        "checks": checks,
        "missing_items": missing,
        "note": "This is a limited text-presence checklist, not a legal or sector-specific completeness determination.",
    }


def _evidence_result(claims):
    result = bg._verify_evidence(claims or [], [])
    proof_claims = []
    for claim in result.get("claims", []):
        status = claim["status"]
        proof_status = {
            "SUPPORTED": "SUPPORTED",
            "QUESTIONABLE": "NEEDS HUMAN REVIEW",
            "EXPIRED": "NEEDS HUMAN REVIEW",
            "MISSING": "EVIDENCE REQUIRED",
        }.get(status, "UNABLE TO VERIFY")
        proof_claims.append({
            "id": claim["id"],
            "claim": claim["claim"],
            "category": claim.get("category"),
            "evidence_required": claim.get("evidence_required"),
            "status": proof_status,
            "explanation": claim["explanation"],
            "matched_evidence": [],
        })
    return result, {"claims": proof_claims, "evidence_documents_supplied": 0,
                    "note": "No supporting certificates were included with the single advertisement upload; no claim is marked verified."}


def _make_verification(report_id):
    frontend_url = os.getenv("BRANDGUARD_FRONTEND_URL", "").strip().rstrip("/")
    parsed = urlparse(frontend_url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        return {"id": report_id, "status": "NOT_CONFIGURED", "url": None, "qr_code_base64": None,
                "message": "Set BRANDGUARD_FRONTEND_URL to the deployed public HTTPS frontend to issue a public verification QR."}
    public_url = f"{frontend_url}/#/verify/{report_id}"
    qr_image = qrcode.make(public_url)
    buffer = io.BytesIO()
    qr_image.save(buffer, format="PNG")
    return {"id": report_id, "status": "READY", "url": public_url,
            "qr_code_base64": base64.b64encode(buffer.getvalue()).decode("ascii"),
            "message": "This QR identifies the saved report; it does not prove that advertising claims are true."}


def _public_report(report):
    modules = {item["id"]: item for item in report.get("modules", [])}
    public_ids = ["claim_analysis", "claim_evidence", "proof_claim", "disclaimer", "qr", "risk",
                  "price_discount", "website_truth", "food_verification", "completeness", "evaluation"]
    public_modules = []
    for module_id in public_ids:
        item = modules.get(module_id)
        if not item:
            continue
        public_item = {"id": item["id"], "label": item["label"], "status": item["status"], "message": item["message"]}
        if module_id in {"claim_analysis", "claim_evidence", "proof_claim", "disclaimer", "risk", "price_discount", "food_verification", "completeness", "evaluation"}:
            public_item["result"] = item.get("result")
        elif module_id == "qr":
            qr = item.get("result") or {}
            public_item["result"] = {key: qr.get(key) for key in ("status", "qr_detected", "is_trust_passport_link") if key in qr}
        public_modules.append(public_item)
    return {
        "success": True,
        "verification_id": report["verification"]["id"],
        "created_at": report["created_at"],
        "media_type": report["media_type"],
        "overall_status": report["overall_status"],
        "risk_summary": report.get("risk_summary"),
        "modules": public_modules,
        "limitations": [
            "A report ID identifies a stored analysis record; cryptographic report-integrity verification is not implemented, and it does not certify claim truth or legal compliance.",
            "OCR and sampled video frames can miss or misread content.",
            "Evidence authenticity and official price/food compliance were not established by this report.",
        ],
    }


def _store_finished_report(report):
    public_payload = _public_report(report)
    with _connect() as connection:
        connection.execute(
            "INSERT OR REPLACE INTO analysis_reports (id, created_at, payload_json) VALUES (?, ?, ?)",
            (report["verification"]["id"], report["created_at"], json.dumps(public_payload, ensure_ascii=False, default=str)),
        )
        connection.commit()


def _run_image_job(job_id, row):
    image = ImageOps.exif_transpose(Image.open(row["temp_path"])).convert("RGB")
    upload = UploadFile(
        filename=row["filename"],
        file=open(row["temp_path"], "rb"),
        headers=Headers({"content-type": row["media_type"]}),
    )
    try:
        ocr = _run_module(job_id, "ocr", lambda: asyncio.run(bg.perform_ocr(upload, row["languages"])))
    finally:
        upload.file.close()
    ocr_data = ocr.get("result") if ocr and ocr.get("status") == "COMPLETED" else None
    text = (ocr_data or {}).get("original_extracted_text", "")
    if ocr_data:
        _run_module(job_id, "ocr_regions", lambda: {"region_ocr": ocr_data.get("region_ocr", {}), "note": "Primary and regional OCR remain separate sources."})
        _run_module(job_id, "critical_values", lambda: {"values": ocr_data.get("primary_critical_values", []), "review": ocr_data.get("critical_value_review", {})})
        claims_out = _run_module(job_id, "claim_analysis", lambda: bg.analyze_claims(text) if text.strip() else _skip("OCR did not return text."))
        claims = ((claims_out.get("result") or {}).get("claims", [])) if claims_out else []
    else:
        for module_id in ("ocr_regions", "critical_values", "claim_analysis"):
            _run_module(job_id, module_id, lambda: _skip("Depends on successful OCR."))
        claims = []

    parallel = {
        "disclaimer": lambda: bg.detect_hidden_disclaimer(image),
        "qr": lambda: bg.detect_embedded_qr(image),
        "manipulation": lambda: bg.detect_manipulation(image),
        "claim_evidence": lambda: _evidence_result(claims)[0],
        "proof_claim": lambda: _evidence_result(claims)[1],
        "price_discount": lambda: _price_check(text),
        "website_truth": lambda: _website_check(text),
        "food_verification": lambda: _food_check(text),
        "improvement": lambda: bg.suggest_improvements(text) if text.strip() else _skip("No readable OCR text to improve."),
        "completeness": lambda: _completeness_check(text),
    }
    outcomes = _run_parallel(job_id, parallel)
    disclaimer = (outcomes.get("disclaimer") or {}).get("result")
    manipulation = (outcomes.get("manipulation") or {}).get("result")
    risk_fn = lambda: bg.compute_risk_alert(
        claims=claims,
        manipulation=manipulation,
        disclaimer=disclaimer,
        ocr_confidence=(ocr_data or {}).get("ocr_confidence"),
    )
    outcomes["risk"] = _run_module(job_id, "risk", risk_fn)
    outcomes["evaluation"] = _run_module(job_id, "evaluation", lambda: {
        "claim_count": len(claims),
        "ocr_confidence": (ocr_data or {}).get("ocr_confidence"),
        "disclaimer_finding": (disclaimer or {}).get("finding"),
        "manipulation_risk": (manipulation or {}).get("risk_level"),
        "note": "Summary of existing checks only; not an approval or legal compliance score.",
    })
    return {"ocr": ocr_data, "text": text, "claims": claims, "outcomes": outcomes}


def _run_video_job(job_id, row):
    upload = UploadFile(filename=row["filename"], file=open(row["temp_path"], "rb"),
                        headers=Headers({"content-type": row["media_type"]}))
    try:
        timeline = _run_module(job_id, "video_validation", lambda: asyncio.run(bg.analyze_video(upload, True)))
    finally:
        upload.file.close()
    video_data = timeline.get("result") if timeline and timeline.get("status") == "COMPLETED" else None
    frames = (video_data or {}).get("sampled_frames", [])
    if video_data:
        frame_text = "\n".join(frame.get("text", "") for frame in frames)
        frame_claims = []
        seen = set()
        for frame in frames:
            for claim in frame.get("claims", []):
                key = (claim.get("text"), frame.get("timestamp_label"))
                if key not in seen:
                    seen.add(key)
                    frame_claims.append({**claim, "timestamp_label": frame.get("timestamp_label")})
        frame_findings = video_data.get("findings", [])
        _run_module(job_id, "frame_ocr_claims", lambda: {"sampled_frames": frames, "findings": frame_findings,
                                                         "audio": video_data.get("audio")})
        all_claims = [
            {"text": item.get("text", ""), "category": item.get("category", "VIDEO_FRAME"),
             "risk_level": item.get("severity", "REVIEW"), "evidence_required": "Supporting documents required; none were included."}
            for item in frame_claims
        ]
        _run_module(job_id, "critical_values", lambda: {"values": bg.critical_values(frame_text), "source": "sampled video frames"})
        _run_module(job_id, "claim_evidence", lambda: _evidence_result(all_claims)[0])
        _run_module(job_id, "proof_claim", lambda: _evidence_result(all_claims)[1])
        _run_module(job_id, "ocr_regions", lambda: _skip("Video sampling returns timestamped frame text, not consolidated spatial OCR regions."))
        image_findings = [frame.get("checks", {}) for frame in frames]
        qr_findings = [frame.get("qr") for frame in frames if frame.get("qr")]
        manipulation_findings = [frame.get("manipulation") for frame in frames if frame.get("manipulation")]
        disclaimers = [frame.get("disclaimer") for frame in frames if frame.get("disclaimer")]
        _run_module(job_id, "disclaimer", lambda: {"frame_results": disclaimers, "timestamped_findings": [f for f in frame_findings if f.get("type") == "DISCLAIMER"]})
        _run_module(job_id, "qr", lambda: {"frame_results": qr_findings, "detected_count": sum(bool(x.get("qr_detected")) for x in qr_findings)})
        _run_module(job_id, "manipulation", lambda: {"frame_results": manipulation_findings, "note": "Heuristic checks are performed on sampled frames only."})
        qr_urls = [item.get("decoded_value") for item in qr_findings if item.get("decoded_value")]
        website_text = frame_text + "\n" + "\n".join(qr_urls)
        _run_module(job_id, "price_discount", lambda: _price_check(frame_text))
        _run_module(job_id, "website_truth", lambda: _website_check(website_text, next((q for q in qr_findings if q.get("decoded_value")), None)))
        _run_module(job_id, "food_verification", lambda: _food_check(frame_text))
        _run_module(job_id, "improvement", lambda: bg.suggest_improvements(frame_text) if frame_text.strip() else _skip("No readable sampled-frame text."))
        _run_module(job_id, "completeness", lambda: _completeness_check(frame_text))
        risk_claims = all_claims
        risk_manipulation = {"findings": [finding for result in manipulation_findings for finding in (result or {}).get("findings", [])]}
        risk_disclaimer = {"findings": [item for item in disclaimers if item]}
        risk = _run_module(job_id, "risk", lambda: bg.compute_risk_alert(claims=risk_claims, manipulation=risk_manipulation,
                                                                           disclaimer=risk_disclaimer, ocr_confidence=None))
        _run_module(job_id, "evaluation", lambda: {"frames_analyzed": video_data.get("frames_analyzed"),
                                                   "timestamped_findings": len(frame_findings),
                                                   "note": "Frame-sampled review only; no compliance verdict."})
        return {"video": video_data, "text": frame_text, "claims": risk_claims}
    for module_id in ("frame_ocr_claims", "ocr_regions", "critical_values", "claim_evidence", "proof_claim", "disclaimer", "qr", "manipulation", "evaluation", "risk", "price_discount", "website_truth", "food_verification", "improvement", "completeness"):
        _run_module(job_id, module_id, lambda: _skip("Depends on successful video decoding and frame sampling."))
    return {"video": None, "text": "", "claims": []}


def _finalize_job(job_id, row, media_kind, analysis):
    current = _load_job(job_id)
    modules = json.loads(current["modules_json"])
    failures = sum(item["status"] == "FAILED" for item in modules)
    report_id = row["report_id"]
    verification = _make_verification(report_id)
    verification_module = _run_module(job_id, "verification_report", lambda: {
        "_status": verification["status"], "_message": verification["message"],
        "verification_id": report_id, "verification_url": verification["url"],
    })
    current = _load_job(job_id)
    modules = json.loads(current["modules_json"])
    risk_module = next((item for item in modules if item["id"] == "risk"), {})
    report = {
        "verification": verification,
        "created_at": row["created_at"],
        "filename": row["filename"],
        "media_type": row["media_type"],
        "media_kind": media_kind,
        "overall_status": "COMPLETED WITH LIMITATIONS" if failures == 0 else "COMPLETED WITH MODULE FAILURES",
        "risk_summary": (risk_module.get("result") or {}).get("alert_level") or (risk_module.get("result") or {}).get("risk_level") or (risk_module.get("result") or {}).get("overall_risk"),
        "modules": modules,
        "ocr": analysis.get("ocr"),
        "video": analysis.get("video"),
        "claims": analysis.get("claims", []),
        "note": "This report is an analysis record, not a certification or legal decision.",
    }
    _store_finished_report(report)
    _update_job(job_id, status="COMPLETED" if failures == 0 else "COMPLETED_WITH_FAILURES", report=report)


def _process_job(job_id):
    row = _load_job(job_id)
    if row is None:
        return
    try:
        _update_job(job_id, status="RUNNING")
        kind = "video" if row["media_type"].startswith("video/") else "image"
        analysis = _run_video_job(job_id, row) if kind == "video" else _run_image_job(job_id, row)
        _finalize_job(job_id, row, kind, analysis)
    except Exception as error:
        message = str(error)[:800]
        current = _load_job(job_id)
        if current:
            modules = json.loads(current["modules_json"])
            for module in modules:
                if module["status"] in {"PENDING", "RUNNING"}:
                    module.update({"status": "FAILED", "message": message})
            _update_job(job_id, status="FAILED", modules=modules, error=message)
    finally:
        try:
            os.unlink(row["temp_path"])
        except OSError:
            pass


@router.post("/api/unified-analysis", status_code=202)
async def start_unified_analysis(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    languages: str = Form("eng"),
):
    media_type = file.content_type or ""
    if not (media_type.startswith("image/") or media_type.startswith("video/")):
        raise HTTPException(status_code=400, detail="Upload one PNG/JPG image or supported video file.")
    selected_languages = bg.validate_languages(languages)
    limit = MAX_VIDEO_BYTES if media_type.startswith("video/") else MAX_IMAGE_BYTES
    suffix = Path(file.filename or "upload").suffix[:12]
    temp_path = None
    size = 0
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temporary:
            temp_path = temporary.name
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > limit:
                    raise HTTPException(status_code=413, detail=f"Upload exceeds the {limit // (1024 * 1024)} MB limit.")
                temporary.write(chunk)
        if size == 0:
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")
        if media_type.startswith("image/"):
            with Image.open(temp_path) as image:
                image.verify()
        else:
            capture = bg.cv2.VideoCapture(temp_path)
            valid = capture.isOpened()
            capture.release()
            if not valid:
                raise HTTPException(status_code=400, detail="The uploaded video could not be decoded.")
    except HTTPException:
        if temp_path:
            try: os.unlink(temp_path)
            except OSError: pass
        raise
    except Exception:
        if temp_path:
            try: os.unlink(temp_path)
            except OSError: pass
        raise HTTPException(status_code=400, detail="The uploaded file is not a valid image or decodable video.")

    media_kind = "video" if media_type.startswith("video/") else "image"
    catalog = VIDEO_MODULES if media_kind == "video" else IMAGE_MODULES
    modules = [{"id": module_id, "label": label, "status": "PENDING", "message": "Queued"} for module_id, label in catalog]
    job_id = _new_id()
    report_id = _new_id()
    created_at = _now()
    with _connect() as connection:
        connection.execute(
        "INSERT INTO analysis_jobs (id, report_id, created_at, filename, media_type, languages, temp_path, status, modules_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (job_id, report_id, created_at, Path(file.filename or "advertisement").name, media_type, selected_languages, temp_path, "QUEUED", json.dumps(modules)),
        )
        connection.commit()
    background_tasks.add_task(_process_job, job_id)
    return {"success": True, "job_id": job_id, "report_id": report_id, "status": "QUEUED", "modules": modules,
            "note": "One upload started the applicable existing checks. External evidence, official price, and sector authority verification remain distinct limitations."}


@router.get("/api/unified-analysis/{job_id}")
def get_unified_analysis_job(job_id: str):
    row = _load_job(job_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Analysis job not found.")
    return {
        "success": row["status"] != "FAILED",
        "job_id": row["id"], "report_id": row["report_id"],
        "created_at": row["created_at"], "status": row["status"],
        "modules": json.loads(row["modules_json"]),
        "report": json.loads(row["report_json"]) if row["report_json"] else None,
        "error": row["error"],
    }


@router.get("/api/analysis-reports/{report_id}")
def get_public_analysis_report(report_id: str):
    with _connect() as connection:
        row = connection.execute("SELECT payload_json FROM analysis_reports WHERE id = ?", (report_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Public analysis report not found or not yet complete.")
    return JSONResponse(json.loads(row["payload_json"]), headers={"Cache-Control": "no-store"})

