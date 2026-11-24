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
MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_OCR_IMAGE_SIDE = 1600


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
                error TEXT,
                evidence_json TEXT NOT NULL DEFAULT '[]',
                revision_of TEXT
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
        if "evidence_json" not in columns:
            connection.execute("ALTER TABLE analysis_jobs ADD COLUMN evidence_json TEXT NOT NULL DEFAULT '[]'")
        if "revision_of" not in columns:
            connection.execute("ALTER TABLE analysis_jobs ADD COLUMN revision_of TEXT")
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
    ("media_forensics", "Multimodal Media Forensics"),
    ("evaluation", "Advertisement Evaluation"),
    ("risk", "Risk Alerts"),
    ("price_discount", "Price and Discount Verification"),
    ("website_truth", "Website Truth Checker"),
    ("food_verification", "Food Advertisement Verification"),
    ("legal_compliance", "Legal Compliance Intelligence"),
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
    ("media_forensics", "Video and Audio Forensics"),
    ("evaluation", "Advertisement Evaluation"),
    ("risk", "Risk Alerts"),
    ("price_discount", "Price and Discount Verification"),
    ("website_truth", "Website Truth Checker"),
    ("food_verification", "Food Advertisement Verification"),
    ("legal_compliance", "Legal Compliance Intelligence"),
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
    result = _unable(
        "Food-related wording was detected, but no official FSSAI source, lab report, sample details, or accreditation record was supplied for this automated run.",
        {"legal_compliance_checked": False, "human_review_required": True},
    )

    try:
        api_key = os.getenv("GEMINI_API_KEY")
        if api_key:
            client = bg.genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model=os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite"),
                contents=(
                    "Contextually review this food advertisement text. Identify "
                    "food, nutrition, health, organic, ingredient and certification "
                    "claims; explain what evidence each claim would need. Do not "
                    "declare a product safe, unsafe, compliant, certified or "
                    "FSSAI-approved. Do not invent regulations or evidence. "
                    "Require human verification.\nAdvertisement text:\n" + text[:12000]
                ),
                config=bg.types.GenerateContentConfig(temperature=0.2),
            )
            result["gemini_context_review"] = response.text or ""
            result["gemini_status"] = "COMPLETED"
        else:
            result["gemini_status"] = "UNAVAILABLE"
    except Exception:
        result["gemini_context_review"] = "Gemini review unavailable."
        result["gemini_status"] = "UNAVAILABLE"

    return result



def _legal_compliance_check(text):
    text = text or ""
    findings = []

    rules = [
        {
            "category": "SUPERIORITY",
            "patterns": [r"\b(no\.?\s*1|number\s*one|best|leading|top[- ]rated|world'?s best)\b"],
            "issue": "Superiority or ranking claim needs independent substantiation.",
            "references": ["ASCI Code, Chapter I, Clause 1.1", "ASCI Code, Chapter I, Clause 1.4"],
            "evidence": "Independent rankings, comparison methodology, award records, and date of evidence.",
        },
        {
            "category": "QUANTIFIED_PERFORMANCE",
            "patterns": [r"\b(?:reduces?|increases?|improves?|removes?|fades?|saves?)\b.{0,100}\b(?:by\s*)?\d+(?:\.\d+)?\s*%"],
            "issue": "Quantified product-performance claim needs reliable supporting data.",
            "references": ["ASCI Code, Chapter I, Clause 1.1", "ASCI Code, Chapter I, Clause 1.2"],
            "evidence": "Product-specific test reports, sample size, methodology, results, and research source/date.",
        },
        {
            "category": "SCIENTIFIC_OR_MEDICAL",
            "patterns": [r"\b(clinically proven|clinically tested|scientifically proven|dermatologist[- ]tested|doctor recommended|cures?|heals?|treats?|prevents?)\b"],
            "issue": "Scientific, clinical, medical, or expert-related claim needs appropriate substantiation.",
            "references": ["ASCI Code, Chapter I, Clauses 1.1 and 1.2", "CCPA Misleading Advertisements Guidelines, 2022"],
            "evidence": "Relevant clinical or scientific reports, study design, product identity, expert credentials, and applicable approvals.",
        },
        {
            "category": "TESTIMONIAL_OR_ENDORSEMENT",
            "patterns": [r"\b(trusted by|recommended by|endorsed by|loved by)\b.{0,70}\b\d[\d,.]*\s*(?:million|lakh|crore|customers?|users?|people)?", r"\b(customer testimonial|customer review|real customer|celebrity endorsed)\b"],
            "issue": "Customer or endorsement claim needs authentic records and appropriate due diligence.",
            "references": ["ASCI Code, Chapter I, Clauses 1.1 and 1.3", "CCPA Misleading Advertisements Guidelines, 2022, Clause 13"],
            "evidence": "Authentic customer records, consent, representative methodology, and endorser's genuine and current experience.",
        },
        {
            "category": "NATURAL_OR_ORGANIC",
            "patterns": [r"\b(100%\s*)?(natural|organic)\s+ingredients?\b", r"\b(organic|natural|chemical[- ]free|toxin[- ]free)\s+(?:product|formula|skincare|ingredients?)\b"],
            "issue": "Natural or organic positioning needs evidence that supports the specific wording and scope.",
            "references": ["ASCI Code, Chapter I, Clauses 1.1 and 1.4", "CCPA Guidelines for Prevention and Regulation of Greenwashing or Misleading Environmental Claims, 2024"],
            "evidence": "Complete ingredient list, formulation records, relevant certifications, and substantiation for the exact claim.",
        },
        {
            "category": "GUARANTEE_OR_REFUND",
            "patterns": [r"\b(guaranteed|guarantee|money[- ]back|risk[- ]free|assured results?)\b"],
            "issue": "Guarantee or refund promise needs clear terms and must not create a misleading impression.",
            "references": ["ASCI Code, Chapter I, Clauses 1.1 and 1.4", "CCPA Misleading Advertisements Guidelines, 2022"],
            "evidence": "Written guarantee/refund policy, eligibility, exclusions, time limits, and conditions.",
        },
        {
            "category": "FREE_OR_PRICE_CLAIM",
            "patterns": [r"\b(free|zero cost|100%\s*free|no extra cost)\b"],
            "issue": "Free or zero-cost wording needs checking for conditions, charges, and qualifications.",
            "references": ["ASCI Code, Chapter I, Clause 1.4", "CCPA Misleading Advertisements Guidelines, 2022"],
            "evidence": "Full offer terms, applicable charges, eligibility, and price history where relevant.",
        },
        {
            "category": "URGENCY_OR_SCARCITY",
            "patterns": [r"\b(limited offer|only today|last chance|limited stock|only \d+ left|ends today|selling fast)\b"],
            "issue": "Urgency or availability statement should reflect actual offer dates and stock.",
            "references": ["ASCI Code, Chapter I, Clauses 1.1 and 1.4", "CCPA Misleading Advertisements Guidelines, 2022"],
            "evidence": "Dated offer terms, inventory records, and campaign validity.",
        },
    ]

    for rule in rules:
        matched = []
        for pattern in rule["patterns"]:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                value = match.group(0).strip()
                if value and value not in matched:
                    matched.append(value)

        for value in matched:
            findings.append({
                "category": rule["category"],
                "matched_text": value,
                "issue": rule["issue"],
                "references": rule["references"],
                "evidence_to_request": rule["evidence"],
                "status": "HUMAN_REVIEW_REQUIRED",
            })

    # Gemini contextual review supplements, but never replaces, rule checks.
    try:
        api_key = os.getenv("GEMINI_API_KEY")
        if api_key:
            client = bg.genai.Client(api_key=api_key)
            categories = [rule["category"] for rule in rules]
            response = client.models.generate_content(
                model=os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite"),
                contents=(
                    "Review this advertisement for additional implied or contextual "
                    "claims relevant to Indian advertising compliance. Return JSON only: "
                    '{"findings":[{"text":"exact quote","category":"category",'
                    '"issue":"potential concern","evidence":"evidence needed"}]}. '
                    "Allowed categories: " + ", ".join(categories) +
                    ". Only quote text present in the advertisement. Do not invent "
                    "claims, laws, evidence, or legal conclusions. Advertisement: "
                    + text[:12000]
                ),
                config=bg.types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.1,
                ),
            )
            ai_data = json.loads(response.text or "{}")
            existing = {
                (f.get("text", "").casefold(), f.get("category"))
                for f in findings
            }
            for item in ai_data.get("findings", [])[:10]:
                quote = str(item.get("text", "")).strip()
                category = str(item.get("category", "")).strip().upper()
                key = (quote.casefold(), category)
                if quote and quote.casefold() in text.casefold() and category in categories and key not in existing:
                    findings.append({
                        "text": quote,
                        "category": category,
                        "issue": str(item.get("issue", "Possible contextual claim requires review.")),
                        "references": [],
                        "evidence_to_request": str(item.get("evidence", "Relevant supporting evidence.")),
                        "status": "HUMAN_REVIEW_REQUIRED",
                    })
                    existing.add(key)
    except Exception:
        pass

    return {
        "_status": "COMPLETED",
        "_message": "Expanded preliminary advertising compliance screening completed. Findings are indicators for review, not legal conclusions.",
        "findings": findings,
        "finding_count": len(findings),
        "human_review_required": True,
        "legal_conclusion": False,
        "screening_method": "Rule-based keyword and phrase screening with Gemini contextual review",
        "sources": [
            {
                "name": "ASCI Code",
                "url": "https://www.ascionline.in/the-asci-code/"
            },
            {
                "name": "CCPA Misleading Advertisements Guidelines, 2022",
                "url": "https://thc.nic.in/Central%20Governmental%20Schemes/Guidelines%20for%20Prevention%20of%20Misleading%20Advertisements%20%26%20Endorsements%20for%20Mislaeding%20Advertisements%2C%202022.pdf"
            },
            {
                "name": "CCPA Greenwashing Guidelines, 2024",
                "url": "https://ccpa.doca.gov.in/guidelines"
            }
        ]
    }


def _price_check(text):
    values = re.findall(r"(?:â‚¹|Rs\.?\s*)\s?\d[\d,]*(?:\.\d{1,2})?|\b\d{1,3}\s?%\s?(?:off|discount)\b", text or "", re.I)
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
        {"item": "Offer or price details", "present": bool(re.search(r"\b(off|sale|offer|deal|â‚¹|rs\.?|price|%|discount)\b", value, re.I)), "basis": "OCR text pattern"},
        {"item": "Offer terms or validity", "present": bool(re.search(r"\b(terms|conditions|valid|until|till|expires|minimum|excludes)\b", value, re.I)), "basis": "OCR text pattern"},
        {"item": "Contact or destination", "present": bool(re.search(r"https?://|www\.|\b\w+@\w+\.|\+?\d[\d ()-]{7,}\d", value, re.I)), "basis": "OCR text pattern"},
        {"item": "Lower-area disclaimer text", "present": bool((disclaimer_result or {}).get("bottom_text_extracted")), "basis": "Existing disclaimer detector"},
    ]
    missing = [item["item"] for item in checks if not item["present"]]
    result = {
        "checks": checks,
        "missing_items": missing,
        "note": "This is a limited text-presence checklist, not a legal or sector-specific completeness determination.",
    }

    try:
        api_key = os.getenv("GEMINI_API_KEY")
        if api_key:
            client = bg.genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model=os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite"),
                contents=(
                    "Review this advertisement for potentially missing information. "
                    "Return JSON with 'additional_missing_information' as a list "
                    "and 'explanation' as a short string. Consider advertiser identity, "
                    "offer conditions, validity, contact details, disclaimers and "
                    "claim qualifications. Do not assume every item is legally required. "
                    "Do not make a legal compliance verdict. Require human review.\n"
                    "Advertisement text:\n" + value[:12000]
                ),
                config=bg.types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.2,
                ),
            )
            data = json.loads(response.text or "{}")
            result["gemini_context_review"] = {
                "additional_missing_information": [
                    str(item)[:300]
                    for item in data.get("additional_missing_information", [])[:10]
                ] if isinstance(data.get("additional_missing_information"), list) else [],
                "explanation": str(data.get("explanation", ""))[:1500],
                "human_review_required": True,
            }
            result["gemini_status"] = "COMPLETED"
        else:
            result["gemini_status"] = "UNAVAILABLE"
    except Exception:
        result["gemini_status"] = "UNAVAILABLE"

    return result


def _evidence_result(claims, evidence=None):
    evidence = evidence or []
    result = bg._verify_evidence(claims or [], evidence)
    proof_claims = []

    for claim in result.get("claims", []):
        status = claim["status"]
        proof_status = {
            "REVIEW_REQUIRED": "NEEDS HUMAN REVIEW",
            "UNDER_REVIEW": "NEEDS HUMAN REVIEW",
            "INSUFFICIENT": "NEEDS HUMAN REVIEW",
            "MISSING": "EVIDENCE REQUIRED",
        }.get(status, "UNABLE TO VERIFY")

        proof_claims.append({
            "id": claim["id"],
            "claim": claim["claim"],
            "category": claim.get("category"),
            "evidence_required": claim.get("evidence_required"),
            "status": proof_status,
            "explanation": claim["explanation"],
            "matched_evidence": claim.get("matched_evidence", []),
        })

    proof_result = {
        "claims": proof_claims,
        "evidence_documents_supplied": len(evidence),
        "documents": result.get("documents", []),
        "summary": result.get("summary", {}),
        "note": result.get("note", "All claims require human review. No claim is automatically verified."),
    }
    return result, proof_result


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
        "improvement_report": report.get("improvement_report"),
        "revision_of": report.get("revision_of"),
        "revision_number": report.get("revision_number", 1),
        "poster_data_url": report.get("poster_data_url"),
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
    evidence = json.loads(row["evidence_json"] or "[]")
    image = ImageOps.exif_transpose(Image.open(row["temp_path"])).convert("RGB")
    ocr_image = image.copy()
    ocr_image.thumbnail(
        (MAX_OCR_IMAGE_SIDE, MAX_OCR_IMAGE_SIDE),
        Image.Resampling.LANCZOS,
    )
    ocr_buffer = io.BytesIO()
    ocr_image.save(ocr_buffer, format="PNG")
    ocr_buffer.seek(0)
    upload = UploadFile(
        filename=Path(row["filename"]).stem + ".png",
        file=ocr_buffer,
        headers=Headers({"content-type": "image/png"}),
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

    from media_forensics import analyze_image as run_media_forensics

    def _image_gemini_review(result, source_image):
        try:
            buffer = io.BytesIO()
            source_image.save(buffer, format="JPEG")
            client = bg.genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
            response = client.models.generate_content(
                model=os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite"),
                contents=[
                    bg.types.Part.from_bytes(
                        data=buffer.getvalue(), mime_type="image/jpeg"
                    ),
                    "Review this advertisement image. Describe visible content, "
                    "visual inconsistencies and disclaimer visibility. Do not "
                    "declare it fake or AI-generated. Require human verification."
                ],
            )
            result["gemini_context_review"] = response.text or ""
        except Exception as error:
            result["gemini_context_review"] = "Gemini review unavailable."
            result["gemini_status"] = "UNAVAILABLE"
            result["gemini_error"] = f"{type(error).__name__}: {str(error)[:220]}"
        else:
            result["gemini_status"] = "COMPLETED"
            result["gemini_error"] = None
        return result

    parallel = {
        "media_forensics": lambda: _image_gemini_review(run_media_forensics(image, bg.detect_manipulation), image),
        "disclaimer": lambda: _image_gemini_review(
            bg.detect_hidden_disclaimer(image), image
        ),
        "qr": lambda: bg.detect_embedded_qr(image),
        "manipulation": lambda: bg.detect_manipulation(image),
        "claim_evidence": lambda: _evidence_result(claims, evidence)[0],
        "proof_claim": lambda: _evidence_result(claims, evidence)[1],
        "legal_compliance": lambda: _legal_compliance_check(text),
        "price_discount": lambda: _price_check(text),
        "website_truth": lambda: _website_check(text),
        "food_verification": lambda: _food_check(text),
        "improvement": lambda: bg.suggest_improvements(text, image=image) if text.strip() else _skip("No readable OCR text to improve."),
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
    evidence = json.loads(row["evidence_json"] or "[]")
    upload = UploadFile(filename=row["filename"], file=open(row["temp_path"], "rb"),
                        headers=Headers({"content-type": row["media_type"]}))
    try:
        timeline = _run_module(job_id, "video_validation", lambda: asyncio.run(bg.analyze_video(upload, True)))
    finally:
        upload.file.close()
    video_data = timeline.get("result") if timeline and timeline.get("status") == "COMPLETED" else None
    frames = (video_data or {}).get("sampled_frames", [])
    if video_data:
        from media_forensics import analyze_video as run_video_forensics
        def _video_gemini_review(result):
            try:
                frames_to_review = frames[:6]
                prompt = (
                    "Review these sampled advertisement video frames in timestamp order. "
                    "Describe visible content, possible visual inconsistencies, disclaimer "
                    "visibility and context. Do not declare the video fake or AI-generated. "
                    "Do not invent audio or events. Human verification is required."
                )
                contents = [prompt]
                for frame in frames_to_review:
                    frame_image = frame.get("image")
                    if isinstance(frame_image, Image.Image):
                        buffer = io.BytesIO()
                        frame_image.save(buffer, format="JPEG")
                        contents.append(bg.types.Part.from_bytes(
                            data=buffer.getvalue(), mime_type="image/jpeg"
                        ))

                client = bg.genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
                response = client.models.generate_content(
                    model=os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite"),
                    contents=contents,
                )
                result["gemini_context_review"] = response.text or ""
            except Exception:
                result["gemini_context_review"] = "Gemini review unavailable."
            return result

        _run_module(
            job_id,
            "media_forensics",
            lambda: _video_gemini_review(
                run_video_forensics(row["temp_path"], bg.detect_manipulation)
            ),
        )
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
        _run_module(job_id, "claim_evidence", lambda: _evidence_result(all_claims, evidence)[0])
        _run_module(job_id, "proof_claim", lambda: _evidence_result(all_claims, evidence)[1])
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
        _run_module(job_id, "legal_compliance", lambda: _legal_compliance_check(frame_text))
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
    for module_id in ("frame_ocr_claims", "ocr_regions", "critical_values", "claim_evidence", "proof_claim", "disclaimer", "qr", "manipulation", "media_forensics", "evaluation", "risk", "price_discount", "website_truth", "food_verification", "legal_compliance", "improvement", "completeness"):
        _run_module(job_id, module_id, lambda: _skip("Depends on successful video decoding and frame sampling."))
    return {"video": None, "text": "", "claims": []}



def _build_improvement_report(modules, risk_summary=None):
    """Build one traceable, actionable report from all module outcomes."""
    groups = [
        ("Copy, OCR & readability", ["ocr", "ocr_regions", "critical_values"]),
        ("Claims & supporting evidence", ["claim_analysis", "claim_evidence", "proof_claim"]),
        ("Legal wording & disclaimers", ["legal_compliance", "disclaimer"]),
        ("Offers, prices & destination", ["price_discount", "website_truth", "food_verification", "qr"]),
        ("Visual quality & authenticity", ["media_forensics", "manipulation"]),
        ("Overall quality & risk", ["evaluation", "risk", "completeness", "improvement"]),
    ]
    by_id = {item.get("id"): item for item in modules}
    sections, actions, limitations = [], [], []
    for title, ids in groups:
        checks = []
        for module_id in ids:
            item = by_id.get(module_id)
            if not item:
                continue
            status = item.get("status", "UNKNOWN")
            result = item.get("result") or {}
            findings = []
            if isinstance(result, dict):
                for key, value in result.items():
                    if isinstance(value, str) and value.strip():
                        findings.append(key.replace("_", " ").title() + ": " + value.strip()[:700])
                    elif isinstance(value, list):
                        for entry in value[:8]:
                            if isinstance(entry, str) and entry.strip():
                                findings.append(entry.strip()[:700])
                            elif isinstance(entry, dict):
                                short = "; ".join(str(k).replace("_", " ") + ": " + str(v)[:180]
                                                  for k, v in list(entry.items())[:5]
                                                  if isinstance(v, (str, int, float, bool)))
                                if short:
                                    findings.append(short)
            checks.append({"feature": item.get("label", module_id), "status": status,
                           "message": item.get("message", ""), "findings": findings[:8]})
            if status != "COMPLETED":
                limitations.append({"feature": item.get("label", module_id), "status": status,
                                    "message": item.get("message", "No result returned.")})
                actions.append({"priority": "Review", "action": "Manually review " + item.get("label", module_id),
                                "reason": item.get("message") or ("Check status: " + status),
                                "source": item.get("label", module_id)})
        if checks:
            sections.append({"title": title, "checks": checks})
    improvement = by_id.get("improvement", {}).get("result") or {}
    if isinstance(improvement, dict):
        for key in ("suggestions", "improvements", "recommendations", "issues"):
            values = improvement.get(key)
            if isinstance(values, list):
                for value in values[:15]:
                    if isinstance(value, str) and value.strip():
                        actions.append({"priority": "Recommended", "action": value.strip(),
                                        "reason": "Advertisement Improvement Assistant finding.",
                                        "source": "Advertisement Improvement Assistant"})
    if risk_summary:
        actions.insert(0, {"priority": "High attention",
                           "action": "Review all high-risk findings before publishing.",
                           "reason": "BrandGuard risk signal: " + str(risk_summary),
                           "source": "Risk Alerts"})
    return {"title": "BrandGuard – Complete Advertisement Improvement Report",
            "summary": "Consolidated findings from the applicable advertisement checks, with traceable sources and an action plan.",
            "risk_summary": risk_summary, "sections": sections, "action_plan": actions[:30],
            "limitations": limitations,
            "disclaimer": "Decision-support only. This report is not legal advice, proof that claims are true, or certification of media authenticity. Human review and supporting evidence remain necessary."}


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
        "improvement_report": _build_improvement_report(modules, (risk_module.get("result") or {}).get("alert_level") or (risk_module.get("result") or {}).get("risk_level") or (risk_module.get("result") or {}).get("overall_risk")),
        "revision_of": row["revision_of"] if "revision_of" in row.keys() else None,
        "revision_number": 2 if ("revision_of" in row.keys() and row["revision_of"]) else 1,
        "poster_data_url": ("data:" + row["media_type"] + ";base64," + base64.b64encode(Path(row["temp_path"]).read_bytes()).decode("ascii")) if media_kind == "image" else None,
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
    evidence_files: list[UploadFile] = File(default=[]),
    revision_of: str = Form(default=""),
):
    media_type = file.content_type or ""
    if not (media_type.startswith("image/") or media_type.startswith("video/")):
        raise HTTPException(status_code=400, detail="Upload one PNG/JPG image or supported video file.")
    selected_languages = bg.validate_languages(languages)
    evidence_documents = []
    if len(evidence_files) > 10:
        raise HTTPException(status_code=413, detail="Upload up to 10 evidence documents.")

    for evidence_file in evidence_files:
        try:
            evidence_name = Path(evidence_file.filename or "evidence").name
            evidence_content = await evidence_file.read(10 * 1024 * 1024 + 1)
            if len(evidence_content) > 10 * 1024 * 1024:
                raise HTTPException(status_code=413, detail=f"Evidence file exceeds the 10 MB limit: {evidence_name}")
            if not evidence_content:
                raise HTTPException(status_code=400, detail=f"Evidence file is empty: {evidence_name}")

            document = bg._extract_evidence_document(
                evidence_name,
                evidence_file.content_type or "application/octet-stream",
                evidence_content,
            )
            document["text"] = (document.get("text") or "")[:1_000_000]
            evidence_documents.append(document)
        finally:
            await evidence_file.close()

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
        "INSERT INTO analysis_jobs (id, report_id, created_at, filename, media_type, languages, temp_path, status, modules_json, evidence_json, revision_of) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (job_id, report_id, created_at, Path(file.filename or "advertisement").name, media_type, selected_languages, temp_path, "QUEUED", json.dumps(modules), json.dumps(evidence_documents, ensure_ascii=False), revision_of.strip() or None),
        )
        connection.commit()
    background_tasks.add_task(_process_job, job_id)
    return {"success": True, "job_id": job_id, "report_id": report_id, "status": "QUEUED", "modules": modules,
            "note": "Advertisement analysis started. Supplied evidence documents are checked for text overlap only and always require human review."}


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




