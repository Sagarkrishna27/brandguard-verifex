import os
import io
import uuid
import sqlite3
import hashlib
import base64
import secrets

from datetime import datetime, timezone
from pathlib import Path

import qrcode

from fastapi import APIRouter, Header, UploadFile, File, Form, HTTPException
from fastapi.responses import StreamingResponse


# --------------------------------------------------
# CONFIGURATION
# --------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv("BRANDGUARD_DATA_DIR", str(BASE_DIR))).expanduser().resolve()
DATA_DIR.mkdir(parents=True, exist_ok=True)

DATABASE_PATH = DATA_DIR / "trust_passports.db"

PUBLIC_BASE_URL = os.getenv(
    "BRANDGUARD_PUBLIC_URL",
    "http://127.0.0.1:8000"
).rstrip("/")

REVIEWER_TOKEN = os.getenv("BRANDGUARD_REVIEWER_TOKEN", "").strip()

MAX_FILE_SIZE = 15 * 1024 * 1024

ALLOWED_STATUSES = {
    "VERIFIED",
    "NEEDS REVIEW",
    "UNSUPPORTED",
    "REJECTED"
}

router = APIRouter(
    prefix="/api/trust-passport",
    tags=["Trust Passport"]
)


# --------------------------------------------------
# DATABASE
# --------------------------------------------------

def get_connection():
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def require_reviewer(token):
    """Require an explicitly configured server-side reviewer token."""
    if not REVIEWER_TOKEN:
        raise HTTPException(
            status_code=503,
            detail="Authorized reviewer workflow is not configured on this server."
        )
    if not token or not secrets.compare_digest(token, REVIEWER_TOKEN):
        raise HTTPException(status_code=401, detail="Authorized reviewer token required.")


def initialize_database():

    with get_connection() as connection:

        connection.execute("""
            CREATE TABLE IF NOT EXISTS trust_passports (
                id TEXT PRIMARY KEY,
                advertisement_name TEXT NOT NULL,
                file_hash TEXT NOT NULL,
                review_status TEXT NOT NULL,
                risk_score REAL NOT NULL,
                reviewer TEXT NOT NULL,
                notes TEXT,
                version INTEGER NOT NULL,
                created_at TEXT NOT NULL
            )
        """)

        connection.commit()


initialize_database()


# --------------------------------------------------
# QR CODE GENERATION
# --------------------------------------------------

def generate_qr(passport_id):

    verification_url = (
        f"{PUBLIC_BASE_URL}/api/trust-passport/{passport_id}"
    )

    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4
    )

    qr.add_data(verification_url)
    qr.make(fit=True)

    image = qr.make_image(
        fill_color="black",
        back_color="white"
    )

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")

    buffer.seek(0)

    return buffer, verification_url


# --------------------------------------------------
# CREATE TRUST PASSPORT
# --------------------------------------------------

@router.post("/")
async def create_trust_passport(
    file: UploadFile = File(...),
    advertisement_name: str = Form(...),
    review_status: str = Form("NEEDS REVIEW"),
    risk_score: float = Form(0),
    reviewer: str = Form("Team Verifex"),
    notes: str = Form(""),
    version: int = Form(1)
):

    if not advertisement_name.strip():
        raise HTTPException(
            status_code=400,
            detail="Advertisement name is required"
        )

    # Public submissions are always unreviewed. Only a separately protected
    # reviewer workflow may assign an official outcome.
    status = "NEEDS REVIEW"
    risk_score = 0
    reviewer = "UNASSIGNED"

    if version < 1:
        raise HTTPException(
            status_code=400,
            detail="Version must be at least 1"
        )

    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="Please upload an advertisement image"
        )

    content = await file.read()

    if not content:
        raise HTTPException(
            status_code=400,
            detail="Uploaded file is empty"
        )

    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail="File exceeds 15 MB limit"
        )

    # Verify that the uploaded file is a valid image.
    try:
        from PIL import Image

        image = Image.open(io.BytesIO(content))
        image.verify()

    except Exception:
        raise HTTPException(
            status_code=400,
            detail="Uploaded file is not a valid image"
        )

    # SHA-256 hash of the exact uploaded image bytes.
    file_hash = hashlib.sha256(content).hexdigest()

    passport_id = str(uuid.uuid4())

    created_at = datetime.now(
        timezone.utc
    ).isoformat()

    with get_connection() as connection:

        connection.execute("""
            INSERT INTO trust_passports (
                id,
                advertisement_name,
                file_hash,
                review_status,
                risk_score,
                reviewer,
                notes,
                version,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            passport_id,
            advertisement_name.strip(),
            file_hash,
            status,
            risk_score,
            reviewer.strip(),
            notes.strip(),
            version,
            created_at
        ))

        connection.commit()

    qr_buffer, verification_url = generate_qr(passport_id)

    qr_base64 = base64.b64encode(
        qr_buffer.getvalue()
    ).decode("utf-8")

    return {
        "success": True,
        "message": "Trust Passport created successfully",
        "passport_id": passport_id,
        "advertisement_name": advertisement_name.strip(),
        "review_status": status,
        "risk_score": risk_score,
        "reviewer": reviewer.strip(),
        "version": version,
        "sha256": file_hash,
        "created_at": created_at,
        "verification_url": verification_url,
        "qr_code_base64": qr_base64
    }


# --------------------------------------------------
# VERIFY TRUST PASSPORT
# --------------------------------------------------

@router.get("/{passport_id}")
def verify_trust_passport(passport_id: str):

    with get_connection() as connection:

        record = connection.execute("""
            SELECT * FROM trust_passports
            WHERE id = ?
        """, (passport_id,)).fetchone()

    if record is None:
        raise HTTPException(
            status_code=404,
            detail="Trust Passport not found"
        )

    return {
        "success": True,
        "verified_record": True,
        "passport_id": record["id"],
        "advertisement_name": record["advertisement_name"],
        "review_status": record["review_status"],
        "risk_score": record["risk_score"],
        "reviewer": record["reviewer"],
        "notes": record["notes"],
        "version": record["version"],
        "sha256": record["file_hash"],
        "created_at": record["created_at"],
        "official_review": record["review_status"] in {"VERIFIED", "REJECTED", "UNSUPPORTED"} and record["reviewer"] != "UNASSIGNED",
        "message": (
            "This record exists in the BrandGuard database. NEEDS REVIEW is an unreviewed submission, not an approval or certification. "
            "No review status is a guarantee of legal compliance."
        )
    }


# --------------------------------------------------
# DOWNLOAD QR CODE
# --------------------------------------------------

@router.get("/{passport_id}/qr")
def download_trust_passport_qr(passport_id: str):

    with get_connection() as connection:

        record = connection.execute("""
            SELECT id FROM trust_passports
            WHERE id = ?
        """, (passport_id,)).fetchone()

    if record is None:
        raise HTTPException(
            status_code=404,
            detail="Trust Passport not found"
        )

    qr_buffer, _ = generate_qr(passport_id)

    return StreamingResponse(
        qr_buffer,
        media_type="image/png",
        headers={
            "Content-Disposition":
                f'attachment; filename="trust-passport-{passport_id}.png"'
        }
    )


# --------------------------------------------------
# LIST TRUST PASSPORTS
# --------------------------------------------------

@router.get("/")
def list_trust_passports(x_reviewer_token: str | None = Header(default=None)):

    require_reviewer(x_reviewer_token)

    with get_connection() as connection:

        records = connection.execute("""
            SELECT
                id,
                advertisement_name,
                review_status,
                risk_score,
                reviewer,
                version,
                created_at
            FROM trust_passports
            ORDER BY created_at DESC
        """).fetchall()

    return {
        "success": True,
        "total": len(records),
        "passports": [
            dict(record) for record in records
        ]
    }


@router.patch("/{passport_id}/review")
def review_trust_passport(
    passport_id: str,
    review_status: str = Form(...),
    risk_score: float = Form(...),
    reviewer: str = Form(...),
    notes: str = Form(""),
    x_reviewer_token: str | None = Header(default=None),
):
    """Assign an official review outcome only through the protected reviewer flow."""
    require_reviewer(x_reviewer_token)

    status = review_status.strip().upper()
    reviewer_name = reviewer.strip()
    if status not in ALLOWED_STATUSES:
        raise HTTPException(status_code=400, detail="Unsupported review status.")
    if not reviewer_name or reviewer_name == "UNASSIGNED":
        raise HTTPException(status_code=400, detail="Reviewer name is required.")
    if risk_score < 0 or risk_score > 100:
        raise HTTPException(status_code=400, detail="Risk score must be between 0 and 100.")

    with get_connection() as connection:
        updated = connection.execute("""
            UPDATE trust_passports
            SET review_status = ?, risk_score = ?, reviewer = ?, notes = ?
            WHERE id = ?
        """, (status, risk_score, reviewer_name, notes.strip(), passport_id)).rowcount
        connection.commit()

    if not updated:
        raise HTTPException(status_code=404, detail="Trust Passport not found")
    return verify_trust_passport(passport_id)
