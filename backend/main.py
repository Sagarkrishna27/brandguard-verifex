import io
import os
from dotenv import load_dotenv
import re
import cv2
import shutil
import tempfile
from datetime import datetime, timezone
from claim_analyzer import analyze_claims
from ad_investigation import investigate_advertisement
from collections import defaultdict

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image, ImageOps, ImageEnhance, ImageFilter
import pytesseract
from pytesseract import Output

try:
    from spellchecker import SpellChecker
    spell = SpellChecker()
except Exception:
    spell = None


# --------------------------------------------------
# CONFIGURATION
# --------------------------------------------------

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

VERSION = "3.0.0"

TESSERACT_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

if os.path.exists(TESSERACT_PATH):
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH

MAX_FILE_SIZE = 10 * 1024 * 1024
MAX_IMAGE_WIDTH = 2400
MAX_IMAGE_HEIGHT = 3200
MAX_OCR_IMAGE_SIDE = 1600

PSM_MODES = [6, 11, 12]

# All 13 installed Indian language models + English.
SUPPORTED_LANGUAGES = {
    "eng": "English",
    "hin": "Hindi",
    "kan": "Kannada",
    "tam": "Tamil",
    "tel": "Telugu",
    "mal": "Malayalam",
    "ben": "Bengali",
    "guj": "Gujarati",
    "mar": "Marathi",
    "pan": "Punjabi",
    "ori": "Odia",
    "asm": "Assamese",
    "urd": "Urdu",
    "san": "Sanskrit"
}

# "all" is supported, but selecting only the languages
# actually present in an advertisement is recommended.
ALL_LANGUAGES = list(SUPPORTED_LANGUAGES.keys())


# --------------------------------------------------
# FASTAPI APPLICATION
# --------------------------------------------------

app = FastAPI(
    title="BrandGuard API",
    description="Multilingual advertisement OCR and critical value analysis",
    version=VERSION
)
from trust_passport import router as trust_passport_router
app.include_router(trust_passport_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in os.getenv("BRANDGUARD_ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173,https://brandguard-seven.vercel.app").split(",") if origin.strip()],
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1|\[::1\])(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)


# --------------------------------------------------
# LANGUAGE VALIDATION
# --------------------------------------------------

def validate_languages(language_input):

    if not language_input:
        language_input = "eng"

    language_input = language_input.strip().lower()

    if language_input == "all":
        selected = ALL_LANGUAGES.copy()

    else:
        # Accept: eng+kan, eng,kan or eng kan
        requested = re.split(r"[+,\s]+", language_input)

        selected = []

        for code in requested:

            if not code:
                continue

            if code not in SUPPORTED_LANGUAGES:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Unsupported language: {code}. "
                        f"Supported codes: "
                        f"{', '.join(SUPPORTED_LANGUAGES.keys())}"
                    )
                )

            if code not in selected:
                selected.append(code)

    if not selected:
        raise HTTPException(
            status_code=400,
            detail="Please select at least one OCR language."
        )

    return "+".join(selected)


def language_details(language_string):

    codes = language_string.split("+")

    return {
        "language_codes": codes,
        "language_names": [
            SUPPORTED_LANGUAGES[code]
            for code in codes
        ],
        "language_count": len(codes)
    }


# --------------------------------------------------
# IMAGE PREPROCESSING
# --------------------------------------------------

def prepare_images(image):

    image = ImageOps.exif_transpose(image).convert("RGB")

    image.thumbnail(
        (MAX_IMAGE_WIDTH, MAX_IMAGE_HEIGHT),
        Image.Resampling.LANCZOS
    )

    gray = ImageOps.grayscale(image)

    enhanced = ImageEnhance.Contrast(gray).enhance(1.8)
    enhanced = ImageEnhance.Sharpness(enhanced).enhance(2.0)

    threshold = enhanced.point(
        lambda pixel: 255 if pixel > 150 else 0
    )

    denoised = enhanced.filter(
        ImageFilter.MedianFilter(size=3)
    )

    return {
        "enhanced_grayscale": enhanced,
        "threshold": threshold,
        "denoised": denoised
    }


# --------------------------------------------------
# OCR ENGINE
# --------------------------------------------------

def _clean_ocr_token(value):
    """Normalize spacing without changing the recognized characters."""
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _line_text(words):
    """Join Tesseract tokens while repairing character-spaced words."""
    if not words:
        return ""

    pieces = []
    for word in words:
        text = word["text"]
        if not pieces:
            pieces.append({
                "text": text,
                "x": word["x"],
                "width": word["width"],
                "height": word["height"],
            })
            continue

        previous = pieces[-1]
        gap = word["x"] - (previous["x"] + previous["width"])
        close_character_tokens = (
            len(previous["text"]) <= 2
            and len(text) <= 2
            and gap <= max(8, int(max(previous["height"], word["height"]) * 0.45))
        )

        if close_character_tokens:
            previous["text"] += text
            previous["width"] = (word["x"] + word["width"]) - previous["x"]
        elif text[0] in ".,;:!?%)]}" or previous["text"][-1:] in "([{₹$€£":
            previous["text"] += text
            previous["width"] = (word["x"] + word["width"]) - previous["x"]
        else:
            pieces.append({"text": text, "x": word["x"], "width": word["width"], "height": word["height"]})

    return " ".join(item["text"] for item in pieces)


def _group_ocr_lines(words):
    """Create readable line boxes using OCR hierarchy plus word geometry."""
    # Tesseract sometimes assigns individually detected characters to
    # separate line ids, especially with large display type. Re-group by
    # baseline proximity so the UI does not expose engine bookkeeping as
    # artificial line breaks. The original hierarchy remains on each word.
    clusters = []
    for word in sorted(words, key=lambda item: (item["y"], item["x"])):
        matching = []
        for index, cluster in enumerate(clusters):
            word_top = word["y"]
            word_bottom = word["y"] + word["height"]
            vertical_gap = max(
                cluster["top"] - word_bottom,
                word_top - cluster["bottom"],
                0,
            )
            tolerance = max(4, min(word["height"], cluster["height"]) * 0.25)
            if vertical_gap <= tolerance:
                matching.append(index)

        if matching:
            cluster = clusters[matching[0]]
            cluster["words"].append(word)
            cluster["top"] = min(item["y"] for item in cluster["words"])
            cluster["bottom"] = max(item["y"] + item["height"] for item in cluster["words"])
            cluster["height"] = max(item["height"] for item in cluster["words"])
        else:
            clusters.append({
                "words": [word],
                "top": word["y"],
                "bottom": word["y"] + word["height"],
                "height": word["height"],
            })

    line_groups = []
    for cluster in clusters:
        line_words = cluster["words"]
        ordered = sorted(line_words, key=lambda item: (item["x"], item["y"]))
        unique = []
        seen = set()
        for word in ordered:
            signature = (
                word["text"], word["x"], word["y"],
                word["width"], word["height"]
            )
            if signature not in seen:
                seen.add(signature)
                unique.append(word)

        if not unique:
            continue

        left = min(item["x"] for item in unique)
        top = min(item["y"] for item in unique)
        right = max(item["x"] + item["width"] for item in unique)
        bottom = max(item["y"] + item["height"] for item in unique)
        confidence = sum(item["confidence"] for item in unique) / len(unique)

        line_groups.append({
            "text": _line_text(unique),
            "confidence": round(confidence, 2),
            "word_count": len(unique),
            "bbox": {
                "x": left,
                "y": top,
                "width": max(0, right - left),
                "height": max(0, bottom - top),
            },
            "words": unique,
            "source_keys": sorted({
                (item.get("page_num", 1), item.get("block_num", 0),
                 item.get("par_num", 0), item.get("line_num", 0))
                for item in unique
            }),
        })

    return sorted(
        line_groups,
        key=lambda line: (line["bbox"]["y"], line["bbox"]["x"])
    )


def run_ocr(image, psm=11, language="eng", geometry_origin=(0, 0), geometry_scale=1.0):

    config = f"--oem 3 --psm {psm}"

    data = pytesseract.image_to_data(
        image,
        config=config,
        lang=language,
        output_type=Output.DICT,
        timeout=60
    )

    words = []
    confidences = []
    raw_tokens = []

    for i, raw in enumerate(data["text"]):

        word = _clean_ocr_token(raw)

        if not word:
            continue

        try:
            confidence = float(data["conf"][i])
        except (ValueError, TypeError):
            confidence = -1

        if confidence < 0:
            continue

        left = int(data["left"][i])
        top = int(data["top"][i])
        box_width = int(data["width"][i])
        box_height = int(data["height"][i])
        origin_x, origin_y = geometry_origin
        word_record = {
            "text": word,
            "confidence": round(confidence, 2),
            "x": round(origin_x + left / geometry_scale, 2),
            "y": round(origin_y + top / geometry_scale, 2),
            "width": round(box_width / geometry_scale, 2),
            "height": round(box_height / geometry_scale, 2),
            "page_num": int(data["page_num"][i]),
            "block_num": int(data["block_num"][i]),
            "par_num": int(data["par_num"][i]),
            "line_num": int(data["line_num"][i]),
        }

        raw_tokens.append(word)
        confidences.append(confidence)
        words.append(word_record)

    line_groups = _group_ocr_lines(words)
    extracted_lines = [line["text"] for line in line_groups if line["text"]]

    extracted_text = "\n".join(extracted_lines)

    average_confidence = (
        sum(confidences) / len(confidences)
        if confidences else 0
    )

    return {
        "text": extracted_text.strip(),
        "word_count": len(words),
        "average_confidence": round(average_confidence, 2),
        "words": words,
        "lines": extracted_lines,
        "line_groups": line_groups,
        "raw_text": " ".join(raw_tokens),
        "coordinate_space": {
            "width": image.width,
            "height": image.height,
        },
    }


def candidate_score(result):

    # Ranking aid only. Not a measurement of accuracy.

    confidence = result["average_confidence"]
    word_count = result["word_count"]

    coverage_bonus = min(word_count, 80) * 0.03

    return round(confidence + coverage_bonus, 2)


# --------------------------------------------------
# MULTIPLE FULL-IMAGE OCR PASSES
# --------------------------------------------------

def run_multiple_ocr_passes(prepared, language):

    results = {}

    for pass_index, (image_name, processed_image) in enumerate(prepared.items()):

        if pass_index >= len(PSM_MODES):
            break

        psm = PSM_MODES[pass_index]
        pass_name = f"{image_name}_psm_{psm}"

        try:
            result = run_ocr(
                processed_image,
                psm=psm,
                language=language
            )
        except RuntimeError:
            continue

        result["candidate_score"] = candidate_score(result)
        result["image_processing"] = image_name
        result["psm_mode"] = psm

        results[pass_name] = result

    return results


# --------------------------------------------------
# SELECT BEST OCR RESULT
# --------------------------------------------------

def select_best_candidate(results):

    best_name = max(
        results,
        key=lambda name: results[name]["candidate_score"]
    )

    return best_name, results[best_name]


# --------------------------------------------------
# REGION-BASED OCR
# --------------------------------------------------

def get_regions(image, language):

    width, height = image.size

    areas = {
        "headline": (
            0, 0,
            width, int(height * 0.38)
        ),

        "offer_and_promo_code": (
            0, int(height * 0.12),
            width, int(height * 0.62)
        ),

        "conditions": (
            0, int(height * 0.45),
            width, int(height * 0.90)
        ),

        "footer": (
            0, int(height * 0.72),
            width, height
        )
    }

    region_modes = {
        "headline": [6],
        "offer_and_promo_code": [6],
        "conditions": [6],
        "footer": [6]
    }

    results = {}

    for region_name, coordinates in areas.items():

        crop = image.crop(coordinates)
        crop_scale = 1.0

        crop = ImageOps.grayscale(crop)
        crop = ImageEnhance.Contrast(crop).enhance(1.8)
        crop = ImageEnhance.Sharpness(crop).enhance(2.0)

        region_candidates = {}

        for psm in region_modes[region_name]:

            try:
                result = run_ocr(
                    crop,
                    psm=psm,
                    language=language,
                    geometry_origin=(coordinates[0], coordinates[1]),
                    geometry_scale=crop_scale,
                )
            except RuntimeError:
                continue

            region_candidates[str(psm)] = {
                "text": result["text"],
                "raw_text": result["raw_text"],
                "word_count": result["word_count"],
                "average_confidence": result["average_confidence"],
                "words": result["words"],
                "line_groups": result["line_groups"],
                "coordinate_space": {
                    "width": image.width,
                    "height": image.height,
                },
            }

        if not region_candidates:
            results[region_name] = {
                "best_psm_mode": None,
                "text": "",
                "raw_text": "",
                "word_count": 0,
                "average_confidence": 0,
                "words": [],
                "line_groups": [],
                "coordinate_space": {"width": width, "height": height},
                "all_modes": {},
            }
            continue

        best_mode = max(
            region_candidates,
            key=lambda mode: (
                region_candidates[mode]["average_confidence"]
                + min(region_candidates[mode]["word_count"], 80) * 0.03
            )
        )

        results[region_name] = {
            "best_psm_mode": int(best_mode),
            "text": region_candidates[best_mode]["text"],
            "raw_text": region_candidates[best_mode]["raw_text"],
            "word_count": region_candidates[best_mode]["word_count"],
            "average_confidence": region_candidates[best_mode]["average_confidence"],
            "words": region_candidates[best_mode]["words"],
            "line_groups": region_candidates[best_mode]["line_groups"],
            "coordinate_space": region_candidates[best_mode]["coordinate_space"],
            "all_modes": region_candidates
        }

    return results


# --------------------------------------------------
# CRITICAL ADVERTISING VALUE EXTRACTION
# --------------------------------------------------

def critical_values(text):

    values = {
        "discounts": set(),
        "currency_amounts": set(),
        "times": set(),
        "long_numbers": set(),
        "promo_codes": set()
    }

    discount_pattern = r"\b\d{1,3}(?:\.\d+)?\s*%"

    for match in re.findall(
        discount_pattern, text, re.IGNORECASE
    ):
        values["discounts"].add(
            re.sub(r"\s+", "", match).upper()
        )

    currency_patterns = [
        r"\b\d[\d,]*(?:\.\d+)?\s*(?:TK|BDT|INR|USD|RS\.?)\b",
        r"\b(?:TK|BDT|INR|USD|RS\.?)\s*\d[\d,]*(?:\.\d+)?\b"
    ]

    for pattern in currency_patterns:

        for match in re.findall(
            pattern, text, re.IGNORECASE
        ):
            values["currency_amounts"].add(
                re.sub(r"\s+", " ", match.strip()).upper()
            )

    time_patterns = [
        r"\b\d{1,2}:\d{2}\s*(?:AM|PM)?\b",
        r"\b\d{1,2}\s*(?:AM|PM)\b"
    ]

    for pattern in time_patterns:

        for match in re.findall(
            pattern, text, re.IGNORECASE
        ):
            values["times"].add(
                re.sub(r"\s+", " ", match.strip()).upper()
            )

    for match in re.findall(r"\b\d{5,}\b", text):
        values["long_numbers"].add(match)

    promo_pattern = (
        r"\b(?:use\s+code|promo\s+code|coupon\s+code)"
        r"\s*[:\-]?\s*([A-Z0-9]{4,15})\b"
    )

    for match in re.findall(
        promo_pattern, text, re.IGNORECASE
    ):

        code = match.upper()

        if code not in {
            "CODE", "PROMO", "COUPON", "USE"
        }:
            values["promo_codes"].add(code)

    return {
        category: sorted(found)
        for category, found in values.items()
    }


# --------------------------------------------------
# CRITICAL VALUE COMPARISON
# --------------------------------------------------

def compare_critical_values(results):

    values_by_pass = {}

    observations = defaultdict(
        lambda: defaultdict(set)
    )

    for pass_name, result in results.items():

        extracted = critical_values(result["text"])

        values_by_pass[pass_name] = extracted

        for category, found_values in extracted.items():

            for value in found_values:
                observations[category][value].add(pass_name)

    conflicts = []
    uncorroborated = []

    for category, category_values in observations.items():

        if len(category_values) > 1:

            conflict_readings = []

            for value, detected_in in category_values.items():

                conflict_readings.append({
                    "value": value,
                    "detected_in": sorted(detected_in)
                })

            conflicts.append({
                "category": category,
                "readings": conflict_readings,
                "review_required": True
            })

        for value, detected_in in category_values.items():

            if len(detected_in) == 1:

                uncorroborated.append({
                    "category": category,
                    "value": value,
                    "detected_in": sorted(detected_in),
                    "review_required": True
                })

    return {
        "has_conflicts": bool(conflicts),
        "conflicts": conflicts,
        "uncorroborated_values": uncorroborated,
        "values_by_pass": values_by_pass
    }


# --------------------------------------------------
# SPELLING SUGGESTIONS
# --------------------------------------------------

def spelling_suggestions(text, language):

    # SpellChecker is English-only.
    # Do not apply English spelling corrections to
    # Kannada, Hindi or other Indian language text.

    if spell is None or "eng" not in language.split("+"):
        return []

    suggestions = []

    words = set(
        re.findall(r"\b[a-zA-Z]{5,}\b", text)
    )

    for word in words:

        if word.lower() in spell:
            continue

        correction = spell.correction(word.lower())

        if correction and correction.lower() != word.lower():

            suggestions.append({
                "original": word,
                "suggestion": correction
            })

    return suggestions[:20]


# --------------------------------------------------
# API ROUTES
# --------------------------------------------------

@app.get("/")
def home():

    return {
        "message": "BrandGuard Multilingual API is running",
        "version": VERSION,
        "supported_languages": SUPPORTED_LANGUAGES
    }


@app.get("/api/health")
def health():

    try:

        installed = pytesseract.get_languages(config="")

        return {
            "status": "healthy",
            "version": VERSION,
            "tesseract": str(
                pytesseract.get_tesseract_version()
            ),
            "installed_languages": installed,
            "supported_languages": SUPPORTED_LANGUAGES,
            "missing_language_models": [
                code for code in ALL_LANGUAGES
                if code not in installed
            ]
        }

    except Exception as error:

        return {
            "status": "error",
            "message": str(error)
        }


@app.get("/api/languages")
def get_languages():

    try:

        installed = pytesseract.get_languages(config="")

        return {
            "supported_languages": SUPPORTED_LANGUAGES,
            "installed_languages": installed,
            "missing_language_models": [
                code for code in ALL_LANGUAGES
                if code not in installed
            ]
        }

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=f"Could not read Tesseract languages: {str(error)}"
        )


# --------------------------------------------------
# MAIN MULTILINGUAL OCR ENDPOINT
# --------------------------------------------------

@app.post("/api/ocr")
async def perform_ocr(
    file: UploadFile = File(...),
    languages: str = Form("eng")
):

    if (
        not file.content_type
        or not file.content_type.startswith("image/")
    ):

        raise HTTPException(
            status_code=400,
            detail="Please upload a valid image."
        )

    try:

        # Validate requested OCR languages.
        selected_language = validate_languages(languages)

        # Check that all requested language files exist.
        installed = pytesseract.get_languages(config="")

        requested_codes = selected_language.split("+")

        missing = [
            code for code in requested_codes
            if code not in installed
        ]

        if missing:

            raise HTTPException(
                status_code=400,
                detail=(
                    "Missing Tesseract language files: "
                    + ", ".join(missing)
                )
            )

        contents = await file.read()

        if len(contents) > MAX_FILE_SIZE:

            raise HTTPException(
                status_code=413,
                detail="Image must be 10 MB or smaller."
            )

        if not contents:

            raise HTTPException(
                status_code=400,
                detail="Uploaded image is empty."
            )

        image = Image.open(io.BytesIO(contents))
        image.load()

        if image.width < 100 or image.height < 100:

            raise HTTPException(
                status_code=400,
                detail="Image resolution is too small."
            )

        original = ImageOps.exif_transpose(
            image
        ).convert("RGB")
        if max(original.size) > MAX_OCR_IMAGE_SIDE:
            original.thumbnail(
                (MAX_OCR_IMAGE_SIDE, MAX_OCR_IMAGE_SIDE),
                Image.Resampling.LANCZOS,
            )

        # Image preprocessing.
        prepared = prepare_images(original)

        # At most three full-image OCR passes.
        pass_results = run_multiple_ocr_passes(
            prepared,
            selected_language
        )
        if not pass_results:
            raise HTTPException(
                status_code=504,
                detail="OCR timed out before a result could be produced. Please try again.",
            )

        # Select the highest-ranked candidate.
        best_name, best = select_best_candidate(
            pass_results
        )

        primary_text = best["text"]

        # Gemini fallback when Tesseract confidence is below 60%.
        gemini_fallback_used = False

        if float(best.get("average_confidence", 0) or 0) < 60:
            gemini_result = run_gemini_ocr(
                contents,
                file.content_type or "image/jpeg"
            )

            if (
                gemini_result.get("status") == "GEMINI_COMPLETED"
                and gemini_result.get("text", "").strip()
            ):
                primary_text = gemini_result["text"].strip()
                gemini_fallback_used = True

        # Four regional OCR analyses.
        regions = get_regions(
            original,
            selected_language
        )

        # Compare critical values.
        review = compare_critical_values(
            pass_results
        )

        comparison = {}

        for name, result in pass_results.items():

            comparison[name] = {
                "candidate_score": result["candidate_score"],
                "word_count": result["word_count"],
                "average_confidence": result["average_confidence"],
                "psm_mode": result["psm_mode"],
                "image_processing": result["image_processing"]
            }

        primary_critical_values = critical_values(
            primary_text
        )

        return {

            "status": "OCR completed successfully",
            "version": VERSION,

            # Language information.
            "selected_languages": language_details(
                selected_language
            ),

            "original_extracted_text": primary_text,
            "best_candidate_text": primary_text,
            "best_ocr_pass": best_name,
            "best_psm_mode": best["psm_mode"],
            "candidate_score": best["candidate_score"],

            # No blind merging or automatic correction.
            "merged_text": primary_text,
            "merged_word_count": best["word_count"],
            "merged_word_confidence": best["average_confidence"],
            "ocr_confidence": best["average_confidence"],
            "gemini_fallback_used": gemini_fallback_used,
            "ocr_engine": "Gemini + Tesseract" if gemini_fallback_used else "Tesseract",

            "primary_critical_values": primary_critical_values,

            "spelling_suggestions": spelling_suggestions(
                primary_text,
                selected_language
            ),

            "pass_comparison": comparison,
            "total_ocr_passes": len(pass_results),

            "region_ocr": regions,
            "region_count": len(regions),

            "critical_value_review": review,

            # Human verification remains mandatory.
            "manual_review_required": True,

            "important_note": (
                "OCR output is machine-generated and may contain "
                "missing, incorrect or misleading readings. "
                "Candidate scores are ranking aids, not accuracy "
                "percentages. Multilingual OCR quality depends on "
                "image quality, font, script and selected languages. "
                "Selecting unnecessary languages may reduce "
                "recognition quality. Regional OCR is supporting "
                "evidence and does not automatically replace primary "
                "OCR output. Human verification is mandatory."
            )
        }

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"OCR processing failed: {str(e)}"
        )


# --------------------------------------------------
# CLAIM ANALYSIS ENDPOINT
# --------------------------------------------------

@app.post("/api/analyze-claims")
async def analyze_advertisement_claims(payload: dict):

    text = payload.get("text", "")

    if not isinstance(text, str) or not text.strip():
        raise HTTPException(
            status_code=400,
            detail="Advertisement text is required."
        )

    return analyze_claims(text)

# --------------------------------------------------

@app.post("/api/investigate-claims")
async def investigate_advertisement_claims(payload: dict):
    text = payload.get("text", "")

    if not isinstance(text, str) or not text.strip():
        raise HTTPException(
            status_code=400,
            detail="Advertisement text is required."
        )

    return investigate_advertisement(text)
# FEATURES 3-11 ENDPOINTS (brand_features.py)
# --------------------------------------------------

from brand_features import (
    analyze_video_frame,
    detect_hidden_disclaimer,
    detect_embedded_qr,
    truth_check_website,
    detect_manipulation,
    detect_fake_reviews,
    compute_risk_alert,
    suggest_improvements,
)

from poster_generator import generate_poster


def _load_image_from_upload(file: UploadFile):
    """Shared helper: validates and loads an uploaded image."""
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Please upload a valid image.")

    contents = file.file.read()

    if not contents:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    try:
        image = Image.open(io.BytesIO(contents))
        image.load()
        return image
    except Exception:
        raise HTTPException(status_code=400, detail="Uploaded file is not a valid image.")


@app.post("/api/video-check")
async def video_check_endpoint(file: UploadFile = File(...)):
    """Feature 3: checks the first frame of a video advertisement."""
    image = _load_image_from_upload(file)
    return analyze_video_frame(image)


@app.post("/api/detect-disclaimer")
async def detect_disclaimer_endpoint(file: UploadFile = File(...)):
    """Feature 4: hidden disclaimer detector."""
    image = _load_image_from_upload(file)
    return detect_hidden_disclaimer(image)


@app.post("/api/detect-qr")
async def detect_qr_endpoint(file: UploadFile = File(...)):
    """Feature 5: detects a QR code embedded in a poster."""
    image = _load_image_from_upload(file)
    return detect_embedded_qr(image)


@app.post("/api/truth-check")
async def truth_check_endpoint(payload: dict):
    """Feature 6: compares ad claims against the brand's live website."""
    ad_text = payload.get("text", "")
    url = payload.get("url", "")

    if not isinstance(ad_text, str) or not ad_text.strip():
        raise HTTPException(status_code=400, detail="Advertisement text is required.")

    if not isinstance(url, str) or not url.strip().startswith(("http://", "https://")):
        raise HTTPException(
            status_code=400,
            detail="A valid website URL starting with http:// or https:// is required."
        )

    return truth_check_website(ad_text, url.strip())


@app.post("/api/fake-reviews")
async def fake_reviews_endpoint(payload: dict):
    """Feature 9: linguistic fake-review analysis."""
    text = payload.get("text", "")

    if not isinstance(text, str) or not text.strip():
        raise HTTPException(status_code=400, detail="Review text is required.")

    return detect_fake_reviews(text)


@app.post("/api/improve-ad")
async def improve_ad_endpoint(payload: dict):
    """Feature 11: rule-based copy improvement suggestions."""
    text = payload.get("text", "")

    if not isinstance(text, str) or not text.strip():
        raise HTTPException(status_code=400, detail="Advertisement text is required.")

    return suggest_improvements(text)


@app.post("/api/manipulation-check")
async def manipulation_check_endpoint(file: UploadFile = File(...)):
    """Feature 8: image forensics heuristics."""
    image = _load_image_from_upload(file)
    return detect_manipulation(image)


@app.post("/api/media-forensics")
async def media_forensics_endpoint(file: UploadFile = File(...)):
    """Explainable image/video forensics; no unsupported deepfake verdicts."""
    content_type = (file.content_type or "").lower()
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded media is empty.")

    from media_forensics import (
        MAX_IMAGE_BYTES, MAX_VIDEO_BYTES, analyze_image, analyze_video,
    )

    if content_type.startswith("image/"):
        if len(content) > MAX_IMAGE_BYTES:
            raise HTTPException(status_code=413, detail="Image must be below 15 MB.")
        try:
            image = Image.open(io.BytesIO(content))
            image.load()
        except Exception:
            raise HTTPException(status_code=400, detail="Uploaded image could not be decoded.")
        return analyze_image(image, detect_manipulation)

    if content_type.startswith("video/"):
        if len(content) > MAX_VIDEO_BYTES:
            raise HTTPException(status_code=413, detail="Video must be below 200 MB.")
        suffix = os.path.splitext(file.filename or "upload.mp4")[1] or ".mp4"
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp:
                temp.write(content)
                temp_path = temp.name
            return analyze_video(temp_path, detect_manipulation)
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error))
        finally:
            if temp_path:
                try:
                    os.unlink(temp_path)
                except OSError:
                    pass

    raise HTTPException(status_code=400, detail="Upload an image or video file.")


@app.post("/api/risk-alert")
async def risk_alert_endpoint(payload: dict):
    """Feature 10: aggregates all signals into one explainable alert."""
    return compute_risk_alert(
        claims=payload.get("claims"),
        manipulation=payload.get("manipulation"),
        disclaimer=payload.get("disclaimer"),
        ocr_confidence=payload.get("ocr_confidence"),
    )


@app.post("/api/generate-poster")
async def generate_poster_endpoint(payload: dict):
    """AI Poster Generator: composes a poster from a brief."""
    brief = {
        "brand_name": payload.get("brand_name", ""),
        "headline": payload.get("headline", ""),
        "description": payload.get("description", ""),
        "offer": payload.get("offer", ""),
        "cta": payload.get("cta", "Learn More"),
        "disclaimer": payload.get("disclaimer", ""),
        "prompt": payload.get("prompt", ""),
        "style": payload.get("style", ""),
        "size": payload.get("size", ""),
        "colour_theme": payload.get("colour_theme", ""),
    }

    return generate_poster(brief)


@app.post("/api/brand-dna")
async def brand_dna_endpoint(payload: dict):
    """Feature 7: builds a brand style profile from past scan summaries."""
    history = payload.get("scan_history", [])

    if not isinstance(history, list):
        raise HTTPException(status_code=400, detail="scan_history must be a list.")

    return build_brand_dna_from_payload(history)


def build_brand_dna_from_payload(history):
    from brand_features import build_brand_dna

    normalised = []
    for entry in history:
        if isinstance(entry, dict):
            normalised.append({
                "text": entry.get("text", ""),
                "claims": entry.get("claims", []),
            })

    return build_brand_dna(normalised)


# --------------------------------------------------
# ROUND 3: EVIDENCE-BASED CLAIM VERIFICATION
# --------------------------------------------------

def _evidence_expiry(text):
    dates = re.findall(r"\b(20\d{2})[-/](\d{1,2})[-/](\d{1,2})\b|\b(\d{1,2})[-/](\d{1,2})[-/](20\d{2})\b", text)
    for match in dates:
        try:
            if match[0]: value = datetime(int(match[0]), int(match[1]), int(match[2]), tzinfo=timezone.utc)
            else: value = datetime(int(match[5]), int(match[3]), int(match[4]), tzinfo=timezone.utc)
            return value
        except ValueError:
            continue
    return None


def _verify_evidence(claims, evidence):
    now = datetime.now(timezone.utc)
    verified = []
    for index, claim in enumerate(claims, 1):
        claim_text = claim.get("text", "")
        words = {word.lower() for word in re.findall(r"[a-zA-Z]{4,}", claim_text)}
        matches = []
        expired = []
        strong_match = False
        for item in evidence:
            evidence_words = {word.lower() for word in re.findall(r"[a-zA-Z]{4,}", item["text"])}
            overlap = len(words & evidence_words)
            if overlap >= max(1, min(3, len(words) // 5)) or claim.get("category", "").lower().replace("_", " ") in item["text"].lower():
                expiry = _evidence_expiry(item["text"])
                if expiry and expiry < now: expired.append(item["name"])
                else:
                    matches.append(item["name"])
                    strong_match = strong_match or overlap >= 3
        if expired and not matches:
            status, explanation = "REVIEW_REQUIRED", "A matching document appears to contain a past date. Confirm whether it is an expiry date and obtain current evidence if needed."
        elif matches:
            status = "UNDER_REVIEW" if strong_match else "INSUFFICIENT"
            explanation = "Text overlaps with this claim. Automated matching does not validate authenticity, scope, issuer, or whether the document substantiates the advertised wording. Human review is required."
        elif any(item.get("extraction_status") not in {None, "COMPLETED"} for item in evidence):
            status, explanation = "INSUFFICIENT", "A document was supplied, but its text could not be reliably extracted for matching. Review it manually or provide a readable copy."
        else:
            status, explanation = "MISSING", "No supplied document matched this claim. The claim remains unsupported until evidence is provided."
        verified.append({"id": f"claim-{index}", "claim": claim_text, "category": claim.get("category"), "status": status, "risk_level": claim.get("risk_level"), "explanation": explanation, "matched_evidence": matches + expired, "evidence_required": claim.get("evidence_required")})
    status_counts = {status: sum(item["status"] == status for item in verified) for status in ("MISSING", "UNDER_REVIEW", "INSUFFICIENT", "REVIEW_REQUIRED")}
    return {"success": True, "claims": verified, "documents": [{"name": item["name"], "extraction_status": item.get("extraction_status", "COMPLETED"), "message": item.get("message", "Text extracted.")} for item in evidence], "summary": {"claim_count": len(verified), "supported_count": 0, "flagged_count": len(verified), "review_required": bool(verified), "evidence_count": len(evidence), **status_counts}, "note": "Text overlap is only a triage signal. No uploaded document is automatically treated as authentic or sufficient proof."}


def _extract_evidence_document(name, content_type, content):
    suffix = os.path.splitext(name)[1].lower()
    if content_type == "application/pdf" or suffix == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError:
            return {"name": name, "text": "", "extraction_status": "NOT_CONFIGURED", "message": "PDF text extraction is not installed on this backend."}
        try:
            reader = PdfReader(io.BytesIO(content), strict=False)
            if reader.is_encrypted:
                return {"name": name, "text": "", "extraction_status": "UNAVAILABLE", "message": "Password-protected PDFs cannot be read."}
            page_count = len(reader.pages)
            text = "\n".join((page.extract_text() or "") for page in reader.pages[:100])
            if not text.strip():
                return {"name": name, "text": "", "extraction_status": "INSUFFICIENT", "message": "No selectable text was extracted; scanned PDFs need OCR before review."}
            status = "INSUFFICIENT" if page_count > 100 else "COMPLETED"
            message = "Only the first 100 pages were extracted." if page_count > 100 else "PDF text extracted; document authenticity is not checked."
            return {"name": name, "text": text[:1_000_000], "extraction_status": status, "message": message}
        except Exception:
            return {"name": name, "text": "", "extraction_status": "FAILED", "message": "The PDF could not be parsed. Check that it is readable and not damaged."}

    if content_type.startswith("image/"):
        try:
            image = Image.open(io.BytesIO(content)).convert("RGB")
            text = pytesseract.image_to_string(image, timeout=60)
            return {"name": name, "text": text, "extraction_status": "COMPLETED" if text.strip() else "INSUFFICIENT", "message": "Image text extracted with OCR; recognition may be incomplete."}
        except Exception:
            return {"name": name, "text": "", "extraction_status": "FAILED", "message": "The image could not be read by OCR."}

    if content_type.startswith("text/") or suffix in {".txt", ".md", ".json", ".csv"}:
        try:
            text = content.decode("utf-8-sig")
            return {"name": name, "text": text, "extraction_status": "COMPLETED" if text.strip() else "INSUFFICIENT", "message": "Text decoded as UTF-8."}
        except UnicodeDecodeError:
            return {"name": name, "text": "", "extraction_status": "FAILED", "message": "Text files must use UTF-8 encoding."}

    return {"name": name, "text": "", "extraction_status": "UNAVAILABLE", "message": "This file type is not supported for text extraction."}


@app.post("/api/verify-claims-evidence")
async def verify_claims_evidence(text: str = Form(...), evidence_files: list[UploadFile] = File(default=[])):
    if not text.strip():
        raise HTTPException(status_code=400, detail="Advertisement text is required.")
    analysis = analyze_claims(text)
    evidence = []
    for uploaded in evidence_files:
        content = await uploaded.read()
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(status_code=413, detail=f"Evidence file {uploaded.filename} exceeds {MAX_FILE_SIZE // (1024 * 1024)} MB.")
        evidence.append(_extract_evidence_document(
            uploaded.filename or "unnamed evidence",
            uploaded.content_type or "",
            content,
        ))
    return _verify_evidence(analysis.get("claims", []), evidence)


# --------------------------------------------------
# ROUND 3: FULL VIDEO TIMELINE ANALYSIS
# --------------------------------------------------

def _timestamp(seconds):
    return f"{int(seconds // 60):02d}:{int(seconds % 60):02d}"


@app.post("/api/analyze-video")
async def analyze_video(file: UploadFile = File(...), include_frame_checks: bool = Form(False)):
    if not file.content_type or not file.content_type.startswith("video/"):
        raise HTTPException(status_code=400, detail="Please upload a video advertisement.")
    content = await file.read()
    if not content: raise HTTPException(status_code=400, detail="Uploaded video is empty.")
    if len(content) > 200 * 1024 * 1024: raise HTTPException(status_code=413, detail="Video must be below 200 MB.")
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename or ".mp4")[1]) as temp:
            temp.write(content); temp_path = temp.name
        capture = cv2.VideoCapture(temp_path)
        if not capture.isOpened(): raise HTTPException(status_code=400, detail="The video could not be decoded by OpenCV.")
        fps = capture.get(cv2.CAP_PROP_FPS) or 25
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        duration = frame_count / fps if frame_count else 0
        sample_count = min(24, max(1, int(duration // 2) + 1))
        findings = []; analyzed = 0; seen = set(); sampled_frames = []
        last_frame_time = max(0.0, duration - (1.0 / fps))
        for i in range(sample_count):
            # Seeking to exactly `duration` can land one frame beyond the end
            # of the stream and silently drop the final sample.
            seconds = 0 if sample_count == 1 else last_frame_time * i / (sample_count - 1)
            capture.set(cv2.CAP_PROP_POS_MSEC, seconds * 1000)
            ok, frame = capture.read()
            if not ok: continue
            analyzed += 1
            frame_image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            try:
                text = pytesseract.image_to_string(frame_image, timeout=60).strip()
            except RuntimeError:
                text = ""
            claim_data = analyze_claims(text)
            frame_record = {
                "timestamp_seconds": round(seconds, 2),
                "timestamp_label": _timestamp(seconds),
                "text": text,
                "claims": claim_data.get("claims", []),
            }
            if include_frame_checks:
                frame_record["qr"] = detect_embedded_qr(frame_image)
                frame_record["disclaimer"] = detect_hidden_disclaimer(frame_image)
                frame_record["manipulation"] = detect_manipulation(frame_image)
            sampled_frames.append(frame_record)
            if not text: continue
            for claim in claim_data.get("claims", []):
                key = (round(seconds, 1), claim["text"])
                if key not in seen:
                    seen.add(key); findings.append({"timestamp_seconds": round(seconds, 2), "timestamp_label": _timestamp(seconds), "type": "CLAIM", "severity": claim.get("risk_level", "REVIEW"), "text": claim["text"], "explanation": claim.get("explanation", "Human review required.")})
            if re.search(r"terms|conditions|valid|disclaimer|applicable|subject to", text, re.I):
                findings.append({"timestamp_seconds": round(seconds, 2), "timestamp_label": _timestamp(seconds), "type": "DISCLAIMER", "severity": "REVIEW", "text": text, "explanation": "Disclaimer-like text was visible in this sampled frame; check readability and whether it remains on screen long enough."})
        capture.release()
        audio_present = False
        ffprobe = shutil.which("ffprobe")
        audio_status = "NOT TESTED"; audio_explanation = "Audio transcription was not tested because ffprobe is unavailable. No audio claim can be confirmed from this result."
        if ffprobe:
            import subprocess
            probe = subprocess.run([ffprobe, "-v", "error", "-select_streams", "a", "-show_entries", "stream=index", "-of", "csv=p=0", temp_path], capture_output=True, text=True, timeout=15)
            audio_present = bool(probe.stdout.strip())
            audio_status = "PRESENT — TRANSCRIPTION NOT CONFIGURED" if audio_present else "NO AUDIO STREAM DETECTED"
            audio_explanation = "The file contains an audio stream, but speech transcription is not configured in this build." if audio_present else "ffprobe found no audio stream in the uploaded file."
        return {"success": True, "status": "ANALYZED WITH HUMAN REVIEW REQUIRED", "duration_seconds": round(duration, 2), "frames_analyzed": analyzed, "findings": findings, "sampled_frames": sampled_frames, "audio": {"status": audio_status, "present": audio_present, "explanation": audio_explanation}, "note": "Frame sampling can miss brief text. Audio is not transcribed unless an approved speech-to-text service is configured."}
    finally:
        if temp_path: 
            try: os.unlink(temp_path)
            except OSError: pass


from unified_analysis import router as unified_analysis_router
app.include_router(unified_analysis_router)

from google import genai
from google.genai import types

def run_gemini_ocr(image_bytes: bytes, mime_type: str = "image/jpeg"):
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return {"status": "GEMINI_NOT_CONFIGURED", "text": None}

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model="gemini-3.5-flash-lite",
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                (
                    "Read all visible advertisement text exactly. Preserve the original "
                    "languages and scripts. Include brand names, discounts, promo codes, "
                    "conditions, validity, website and phone numbers. Do not guess unclear text."
                ),
            ],
        )
        return {
            "status": "GEMINI_COMPLETED",
            "text": response.text or "",
        }
    except Exception as exc:
        return {
            "status": "GEMINI_FAILED",
            "text": None,
            "error": str(exc)[:300],
        }

