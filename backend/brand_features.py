"""
brand_features.py
-----------------
Genuine (non-simulated) implementations for the remaining BrandGuard
roadmap features. Every check runs real image/text/web analysis using the
libraries installed in this project (Pillow, requests, BeautifulSoup,
pytesseract, numpy via PIL). Nothing returns fabricated success data:
when a check cannot be verified, the response says so explicitly.

Features implemented here (numbered per the approved roadmap):
  3  Video Advertisement Checker (first frame)
  4  Hidden Disclaimer Detector
  5  QR Code Embedded Inside Poster
  6  Ad-to-Website Truth Checker
  7  Brand DNA Intelligence
  8  AI Ad Manipulation Detector (heuristic, honestly labelled)
  9  Fake Review and Testimonial Detector
 10  Real-Time Ad Risk Alert
 11  AI Advertisement Improvement Assistant (rule-based, honestly labelled)
"""

import io
import re
import ipaddress
import socket
from urllib.parse import urljoin, urlparse

from PIL import Image, ImageFilter, ImageStat, ImageEnhance


# --------------------------------------------------
# FEATURE 3 - VIDEO ADVERTISEMENT CHECKER
# --------------------------------------------------

def analyze_video_frame(image):
    """Analyses a video first-frame image with explainable checks."""
    import pytesseract

    data = pytesseract.image_to_data(
        image, output_type=pytesseract.Output.DICT
    )
    words = [w.strip() for w in data["text"] if w and w.strip()]
    text = " ".join(words)
    text_lower = text.lower()

    checks = [
        {
            "check": "Offer text present",
            "passed": any(t in text_lower for t in
                          ["off", "sale", "offer", "discount", "deal",
                           "price", "buy"]),
            "explanation": "The frame should clearly state what is offered.",
        },
        {
            "check": "Disclaimer or terms present",
            "passed": any(t in text_lower for t in
                          ["t&c", "terms", "condition", "disclaimer",
                           "apply"]),
            "explanation": "Offers require visible terms.",
        },
        {
            "check": "Validity or expiry stated",
            "passed": bool(re.search(r"\b(valid|until|till|ends?|expires?)\b",
                                     text_lower)),
            "explanation": "An offer without a validity window can mislead.",
        },
        {
            "check": "Brand or contact identifiable",
            "passed": bool(re.search(r"(\.com|\.in|@|call|www|phone)",
                                     text_lower)),
            "explanation": "Viewers should identify the advertiser.",
        },
    ]

    passed = sum(1 for c in checks if c["passed"])

    return {
        "extracted_text": text,
        "checks": checks,
        "checks_passed": passed,
        "checks_total": len(checks),
        "note": (
            "Video analysis currently checks the first frame only. Full "
            "motion, audio and multi-frame review is not implemented. "
            "Human review is required for final approval."
        ),
    }


# --------------------------------------------------
# FEATURE 4 - HIDDEN DISCLAIMER DETECTOR
# --------------------------------------------------

def detect_hidden_disclaimer(image):
    """Measures band contrast + reads bottom text. Genuine metric."""
    import pytesseract

    gray = image.convert("L")
    width, height = gray.size

    bands = {
        "top": (0, 0, width, int(height * 0.33)),
        "middle": (0, int(height * 0.33), width, int(height * 0.66)),
        "bottom": (0, int(height * 0.66), width, height),
    }

    contrast = {}
    for name, box in bands.items():
        band = gray.crop(box)
        if band.width < 10 or band.height < 10:
            contrast[name] = 0
            continue
        stat = ImageStat.Stat(band)
        contrast[name] = round(stat.stddev[0], 2)

    bottom = gray.crop(bands["bottom"])
    bottom = ImageEnhance.Contrast(bottom).enhance(2.0)
    bottom_text = pytesseract.image_to_string(bottom).strip()

    headline_contrast = max(contrast["top"], 1)
    ratio = contrast["bottom"] / headline_contrast

    if bottom_text and ratio < 0.55:
        finding = "HIDDEN_DISCLAIMER_SUSPECTED"
        detail = (
            "Small text exists in the lower area but its contrast is only "
            + str(round(ratio * 100)) + "% of the headline area. This is "
            "the measurable pattern of low-visibility disclaimers."
        )
    elif bottom_text and ratio < 0.75:
        finding = "LOW_VISIBILITY"
        detail = ("Lower-area text is present but noticeably lower-contrast "
                  "than the headline. Confirm it is readable.")
    elif bottom_text:
        finding = "VISIBLE"
        detail = "Lower-area text is present with reasonable contrast."
    else:
        finding = "NO_TEXT_IN_LOWER_AREA"
        detail = ("No text detected in the lower area. If this poster has "
                  "an offer, its terms may be missing entirely - itself a "
                  "review flag.")

    return {
        "band_contrast_scores": contrast,
        "bottom_vs_headline_ratio": round(ratio, 2),
        "bottom_text_extracted": bottom_text,
        "finding": finding,
        "detail": detail,
        "manual_review_required": True,
    }


# --------------------------------------------------
# FEATURE 5 - QR CODE EMBEDDED INSIDE POSTER
# --------------------------------------------------

def detect_embedded_qr(image):
    """Genuine QR decode via pyzbar or OpenCV when available."""
    result = {
        "qr_detected": False,
        "decoded_value": None,
        "is_trust_passport_link": False,
        "passport_id": None,
        "method": None,
    }

    decoded = None
    method = None
    decoder_available = False

    try:
        from pyzbar.pyzbar import decode as zbar_decode
        decoder_available = True
        found = zbar_decode(image.convert("RGB"))
        if found:
            decoded = found[0].data.decode("utf-8", errors="replace")
            method = "pyzbar"
    except Exception:
        pass

    if decoded is None:
        try:
            import cv2
            import numpy as np
            decoder_available = True

            arr = np.array(image.convert("RGB"))
            detector = cv2.QRCodeDetector()
            value, _, _ = detector.detectAndDecode(arr)
            if value:
                decoded = value
                method = "opencv"
        except Exception:
            pass

    if decoded is None:
        result["method"] = "opencv" if decoder_available else "none_available"
        result["status"] = "NO_QR_FOUND" if decoder_available else "DECODER_UNAVAILABLE"
        result["note"] = ("No QR code was detected in the image." if decoder_available else
                           "No QR decoding library is available, so detection could not run.")
        return result

    result["qr_detected"] = True
    result["decoded_value"] = decoded
    result["method"] = method
    result["status"] = "QR_DETECTED"

    match = re.search(r"/api/trust-passport/([0-9a-fA-F-]{8,})", decoded)
    if match:
        result["is_trust_passport_link"] = True
        result["passport_id"] = match.group(1)

    return result


# --------------------------------------------------
# FEATURE 6 - AD-TO-WEBSITE TRUTH CHECKER
# --------------------------------------------------

def _safe_public_url(url):
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or parsed.username or parsed.password or not parsed.hostname:
        raise ValueError("Only public http(s) URLs are allowed.")
    addresses = socket.getaddrinfo(parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)
    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified:
            raise ValueError("The URL resolves to a private or reserved network address.")
    return url


def truth_check_website(ad_text, url):
    """Fetch a public webpage with SSRF and response-size protections."""
    import requests
    from bs4 import BeautifulSoup

    headers = {"User-Agent": "BrandGuard Truth Checker (Team Verifex)"}

    try:
        current_url = _safe_public_url(url)
        response = None
        for _ in range(4):
            response = requests.get(current_url, headers=headers, timeout=(4, 8), allow_redirects=False, stream=True)
            if response.is_redirect or response.is_permanent_redirect:
                location = response.headers.get("location")
                if not location: raise ValueError("Unsafe redirect without a destination.")
                current_url = _safe_public_url(urljoin(current_url, location))
                continue
            response.raise_for_status()
            break
        else:
            raise ValueError("Too many redirects.")
        content_length = int(response.headers.get("content-length", "0") or 0)
        if content_length > 2 * 1024 * 1024:
            raise ValueError("The webpage response exceeds the 2 MB limit.")
        chunks = []
        size = 0
        for chunk in response.iter_content(chunk_size=65536):
            size += len(chunk)
            if size > 2 * 1024 * 1024: raise ValueError("The webpage response exceeds the 2 MB limit.")
            chunks.append(chunk)
        response._content = b"".join(chunks)
    except requests.exceptions.Timeout:
        return {"success": False,
                "error": "The website did not respond within 12 seconds."}
    except requests.exceptions.SSLError:
        return {"success": False,
                "error": "The website's SSL certificate could not be verified."}
    except requests.exceptions.ConnectionError:
        return {"success": False,
                "error": "Could not connect to the website. Check the URL."}
    except requests.exceptions.RequestException as error:
        return {"success": False,
                "error": "Could not fetch the website: " + str(error)}
    except (ValueError, socket.gaierror, OSError) as error:
        return {"success": False, "error": str(error)}

    if "text/html" not in response.headers.get("content-type", ""):
        return {"success": False,
                "error": "The URL did not return a webpage."}

    soup = BeautifulSoup(response.text, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    website_text = soup.get_text(" ", strip=True).lower()

    verifiable_patterns = {
        "percentage_discounts": r"\b\d{1,3}(?:\.\d+)?\s*%",
        "currency_prices": r"(?:rs\.?|inr|[$])\s*\d[\d,]*(?:\.\d+)?",
        "absolute_superlatives": r"\b(best|fastest|cheapest|#1)\b",
        "guarantee_words": r"\b(guarantee[d]?|assured|risk[- ]free)\b",
        "award_words": r"\b(award|winner|certified|accredited)\b",
    }

    comparison = {}
    for claim_type, pattern in verifiable_patterns.items():
        in_ad = sorted(set(re.findall(pattern, ad_text, re.IGNORECASE)))
        in_web = sorted(set(re.findall(pattern, website_text, re.IGNORECASE)))
        matched = [i for i in in_ad
                   if i.lower() in [w.lower() for w in in_web]]

        if matched and len(matched) >= len(in_ad) * 0.5:
            status = "MATCHED"
        elif in_ad and not matched:
            status = "NOT_FOUND_ON_WEBSITE"
        else:
            status = "NOT_PRESENT_IN_AD"

        comparison[claim_type] = {
            "in_advertisement": in_ad,
            "on_website": in_web[:20],
            "matched": matched,
            "status": status,
        }

    mismatches = [
        {"type": ctype, "values": data["in_advertisement"]}
        for ctype, data in comparison.items()
        if data["status"] == "NOT_FOUND_ON_WEBSITE"
    ]

    return {
        "success": True,
        "checked_url": url,
        "website_title": (soup.title.string.strip()
                          if soup.title and soup.title.string else None),
        "comparison": comparison,
        "possible_mismatches": mismatches,
        "manual_review_required": True,
        "note": (
            "A value not appearing on the website is a review flag, not "
            "proof of a false claim. Human verification is required."
        ),
    }


# --------------------------------------------------
# FEATURE 7 - BRAND DNA INTELLIGENCE
# --------------------------------------------------

def build_brand_dna(scan_history):
    """Real statistical profile of a brand's analysed posters."""
    if not scan_history:
        return {
            "success": False,
            "message": ("No scans available yet. Analyse a poster first "
                        "to build Brand DNA."),
        }

    claim_counter = {}
    punct = {"exclamations": 0, "questions": 0, "superlatives": 0}
    emphasis = {"discounts": 0, "guarantees": 0, "urgency": 0}

    for entry in scan_history:
        text = entry.get("text", "")
        lower = text.lower()

        for claim in entry.get("claims", []):
            claim_counter[claim] = claim_counter.get(claim, 0) + 1

        punct["exclamations"] += text.count("!")
        punct["questions"] += text.count("?")
        punct["superlatives"] += len(
            re.findall(r"\b(best|greatest|finest|ultimate|perfect)\b", lower))

        emphasis["discounts"] += len(
            re.findall(r"\d+\s*%|off|sale|discount", lower))
        emphasis["guarantees"] += len(
            re.findall(r"guarantee|assured|risk[- ]free", lower))
        emphasis["urgency"] += len(
            re.findall(r"hurry|now|today|last chance|limited", lower))

    total = len(scan_history)

    tone = []
    if punct["exclamations"] >= total:
        tone.append("High-energy promotional tone")
    if punct["superlatives"] >= total * 0.5:
        tone.append("Superlative-heavy language")
    if punct["questions"] >= total * 0.5:
        tone.append("Question-led copy")
    if not tone:
        tone.append("Neutral descriptive tone")

    dominant = sorted(claim_counter.items(),
                      key=lambda item: item[1], reverse=True)[:5]

    return {
        "success": True,
        "scans_analyzed": total,
        "tone_profile": tone,
        "punctuation_style": punct,
        "value_emphasis": emphasis,
        "most_frequent_claim_categories": [
            {"category": c, "count": n} for c, n in dominant
        ],
        "note": ("Brand DNA is a statistical description of this brand's "
                 "own posters analysed in this session. It is not a "
                 "compliance judgement."),
    }


# --------------------------------------------------
# FEATURE 8 - AI AD MANIPULATION DETECTOR (HEURISTIC)
# --------------------------------------------------

def detect_manipulation(image):
    """Real, explainable image-forensics heuristics (not deepfake AI)."""
    import numpy as np

    rgb = image.convert("RGB")
    arr = np.asarray(rgb, dtype="float32")
    gray = np.asarray(rgb.convert("L"), dtype="float32")

    findings = []

    # Heuristic 1: ELA-style compression inconsistency.
    buffer = io.BytesIO()
    rgb.save(buffer, format="JPEG", quality=90)
    buffer.seek(0)
    resaved = Image.open(buffer).convert("L")
    ela = np.abs(np.asarray(resaved, dtype="float32") - gray)
    ela_score = float(ela.std()) / max(float(ela.mean()), 1)

    findings.append({
        "heuristic": "Error-level inconsistency",
        "score": round(ela_score, 2),
        "reading": ("High variance in compression error can indicate "
                    "regions edited or re-saved separately."
                    if ela_score > 1.6 else
                    "Compression error is fairly uniform."),
        "flag": ela_score > 1.6,
    })

    # Heuristic 2: Edge-sharpness variance.
    edge_map = rgb.convert("L").filter(ImageFilter.FIND_EDGES)
    edge_stat = ImageStat.Stat(edge_map)
    edge_score = edge_stat.stddev[0] / max(edge_stat.mean[0], 1)

    findings.append({
        "heuristic": "Edge-sharpness variance",
        "score": round(edge_score, 2),
        "reading": ("Sharpness varies strongly across regions - common in "
                    "composite artwork."
                    if edge_score > 1.5 else
                    "Sharpness is reasonably consistent."),
        "flag": edge_score > 1.5,
    })

    # Heuristic 3: RGB channel correlation break.
    def corr(a, b):
        a = a.flatten()
        b = b.flatten()
        num = ((a - a.mean()) * (b - b.mean())).mean()
        den = a.std() * b.std()
        return float(num / den) if den else 0

    min_corr = min(corr(arr[:, :, 0], arr[:, :, 1]),
                   corr(arr[:, :, 0], arr[:, :, 2]),
                   corr(arr[:, :, 1], arr[:, :, 2]))

    findings.append({
        "heuristic": "RGB channel correlation",
        "score": round(min_corr, 3),
        "reading": ("One colour channel correlates poorly with the others "
                    "- seen in digitally inserted elements."
                    if min_corr < 0.75 else
                    "Colour channels correlate naturally."),
        "flag": min_corr < 0.75,
    })

    flags = sum(1 for f in findings if f["flag"])

    return {
        "method": "Classical image forensics heuristics (NOT deepfake AI)",
        "findings": findings,
        "flags_raised": flags,
        "risk_level": ("HIGH_REVIEW" if flags >= 2 else
                       "REVIEW" if flags == 1 else "LOW"),
        "note": ("Statistical heuristics, not proof of manipulation. "
                 "Heavily designed posters can legitimately trigger flags. "
                 "A human must make the final judgement."),
    }


# --------------------------------------------------
# FEATURE 9 - FAKE REVIEW AND TESTIMONIAL DETECTOR
# --------------------------------------------------

def detect_fake_reviews(text):
    """Real linguistic analysis with explainable flags."""
    if not isinstance(text, str) or not text.strip():
        return {"success": False, "message": "Review text is required."}

    reviews = [s.strip() for s in re.split(r"\n+", text) if s.strip()]

    vague_praise = re.compile(
        r"\b(amazing|awesome|best ever|life.?changing|perfect|love it|"
        r"highly recommend|must buy|excellent|superb|incredible)\b",
        re.IGNORECASE)

    specific = re.compile(
        r"\b\d+\b|rs\.?|[$]|weeks?|days?|months?|years?|bought|ordered|"
        r"delivered|used it for|since|model",
        re.IGNORECASE)

    template_name = re.compile(r"\b([A-Z][a-z]+ [A-Z]\.|[A-Z]\. [A-Z][a-z]+)\b")

    findings = []
    for review in reviews:
        flags = []
        praise = len(vague_praise.findall(review))
        specs = len(specific.findall(review))

        if praise >= 2 and specs == 0:
            flags.append({
                "flag": "UNSPECIFIC_PRAISE",
                "detail": (str(praise) + " strong praise words and no "
                           "concrete details (numbers, dates, purchases).")})
        if len(review.split()) < 6 and praise >= 1:
            flags.append({
                "flag": "VERY_SHORT_GENERIC",
                "detail": "Very short review with only generic praise."})
        if template_name.search(review):
            flags.append({
                "flag": "TEMPLATE_NAME",
                "detail": ("Reviewer name follows the 'Firstname L.' "
                           "template common in fabricated testimonials.")})
        if re.search(r"\b(government approved|certified|award)\b",
                     review.lower()):
            flags.append({
                "flag": "REGULATORY_WORDING_IN_REVIEW",
                "detail": ("A testimonial mentioning certifications or "
                           "approvals is unusual and needs evidence.")})

        if flags:
            findings.append({
                "review": review,
                "flags": flags,
                "assessment": "NEEDS_VERIFICATION",
            })

    return {
        "success": True,
        "reviews_analyzed": len(reviews),
        "suspicious_reviews": findings,
        "suspicious_count": len(findings),
        "note": ("Linguistic flags are indicators, not proof a review is "
                 "fake. Genuine enthusiastic customers exist. Human review "
                 "decides."),
    }


# --------------------------------------------------
# FEATURE 10 - REAL-TIME AD RISK ALERT
# --------------------------------------------------

def compute_risk_alert(claims, manipulation, disclaimer, ocr_confidence):
    """Aggregates already-computed BrandGuard signals into one score."""
    score = 0
    reasons = []

    claims = claims or []
    high = [c for c in claims if c.get("risk_level") == "HIGH"]
    medium = [c for c in claims if c.get("risk_level") == "MEDIUM"]
    review = [c for c in claims if c.get("risk_level") == "REVIEW"]

    score += len(high) * 25 + len(medium) * 12 + len(review) * 5
    if high:
        reasons.append(str(len(high)) + " high-risk claim(s) detected")
    if medium:
        reasons.append(str(len(medium)) + " medium-risk claim(s) detected")
    if review:
        reasons.append(str(len(review)) + " claim(s) need context review")

    if manipulation:
        mflags = manipulation.get("flags_raised", 0)
        score += mflags * 15
        if mflags:
            reasons.append(str(mflags) + " image-forensics flag(s) raised")

    if disclaimer:
        finding = disclaimer.get("finding")
        if finding == "HIDDEN_DISCLAIMER_SUSPECTED":
            score += 20
            reasons.append("Possible hidden disclaimer (low-contrast text)")
        elif finding == "NO_TEXT_IN_LOWER_AREA":
            score += 10
            reasons.append("No terms found in lower poster area")

    if ocr_confidence is not None:
        if ocr_confidence < 40:
            score += 15
            reasons.append("Very low OCR confidence ("
                           + str(ocr_confidence) + "%) - text may be misread")
        elif ocr_confidence < 65:
            score += 8
            reasons.append("Low OCR confidence ("
                           + str(ocr_confidence) + "%)")

    score = min(score, 100)

    if score >= 60:
        level = "CRITICAL_ALERT"
    elif score >= 35:
        level = "WARNING"
    elif score > 0:
        level = "MINOR_NOTICES"
    else:
        level = "NO_ALERTS"

    return {
        "risk_score": score,
        "alert_level": level,
        "reasons": reasons,
        "manual_review_required": True,
        "note": ("This score aggregates BrandGuard's own review flags. It "
                 "is a review-priority indicator, not a legal verdict."),
    }


# --------------------------------------------------
# FEATURE 11 - AI AD IMPROVEMENT ASSISTANT (RULE-BASED)
# --------------------------------------------------

def suggest_improvements(text):
    """Real rule-based copy suggestions. Every rule is explainable."""
    if not isinstance(text, str) or not text.strip():
        return {"success": False, "message": "Advertisement text is required."}

    suggestions = []
    lower = text.lower()

    if re.search(r"\b(best|#1|number one|no\.?\s*1)\b", lower):
        suggestions.append({
            "issue": "Unsupported superlative",
            "suggestion": ("Replace absolute superlatives with evidence you "
                           "can back, e.g. 'rated 4.8/5 by 2,300 verified "
                           "customers' instead of 'the best'."),
            "rule": "Superlatives require substantiation.",
        })

    if re.search(r"\b(guaranteed|100%\s*(results?|guarantee)|risk[- ]free)\b",
                 lower):
        suggestions.append({
            "issue": "Unconditional guarantee",
            "suggestion": ("State the guarantee's conditions next to the "
                           "promise, e.g. '30-day money-back guarantee - "
                           "T&C apply'."),
            "rule": "Guarantee claims must show their limits.",
        })

    if re.search(r"\b(government approved|govt\.?\s*approved|certified)\b",
                 lower):
        suggestions.append({
            "issue": "Unverified authority claim",
            "suggestion": ("Name the authority and keep the certificate "
                           "reference, e.g. 'FSSAI Lic. No. ...' - or remove "
                           "the claim."),
            "rule": "Approval claims need an identifiable issuing body.",
        })

    if re.search(r"\d{1,3}\s*%\s*off", lower) and not re.search(
            r"(?:mrp|was|original price|worth)", lower):
        suggestions.append({
            "issue": "Discount without reference price",
            "suggestion": ("Show the original price beside the discount, "
                           "e.g. '40% off MRP 1,999'."),
            "rule": "Comparative price claims need their baseline stated.",
        })

    has_offer = bool(re.search(r"\b(offer|sale|discount|deal)\b", lower))
    has_validity = bool(re.search(r"\b(valid|until|till|ends?|expires?)\b",
                                  lower))
    if has_offer and not has_validity:
        suggestions.append({
            "issue": "Offer without validity window",
            "suggestion": ("Add the offer period, e.g. 'Valid 20-30 "
                           "November only'."),
            "rule": "Time-limited offers must state their time limit.",
        })

    if not re.search(r"(t&c|terms|conditions|disclaimer)", lower):
        if re.search(r"\b(offer|guarantee|approved|certified|results?)\b",
                     lower):
            suggestions.append({
                "issue": "Missing terms/disclaimer",
                "suggestion": ("Add a visible 'T&C apply' line referencing "
                               "the full terms."),
                "rule": "Conditional claims need visible conditions.",
            })

    if re.search(r"\b(hurry|last chance|limited stock|ends today)\b", lower):
        suggestions.append({
            "issue": "Pressure wording",
            "suggestion": ("Keep urgency wording only if factually true "
                           "today, e.g. real stock counts with a date."),
            "rule": "False urgency misleads consumers.",
        })

    if len(re.findall(r"[A-Z]{4,}", text)) >= 3:
        suggestions.append({
            "issue": "Heavy capitalisation",
            "suggestion": ("Use capitals for headline words only; full-caps "
                           "sentences reduce readability."),
            "rule": "Readability and tone guidance.",
        })

    gemini_suggestions = []
    gemini_status = "UNAVAILABLE"

    try:
        import os
        import json
        from google import genai
        from google.genai import types

        api_key = os.getenv("GEMINI_API_KEY")
        if api_key:
            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model="gemini-3.5-flash-lite",
                contents=(
                    "Review this advertisement copy and suggest specific, "
                    "truthful improvements to clarity, readability, claim "
                    "wording and disclaimers. Do not invent evidence or "
                    "certifications. Return JSON with a 'suggestions' array. "
                    "Each item must contain issue, suggestion and rule. "
                    "Ad text:\\n" + text[:12000]
                ),
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.2,
                ),
            )
            data = json.loads(response.text or "{}")
            items = data.get("suggestions", [])
            if isinstance(items, list):
                gemini_suggestions = [
                    {
                        "issue": str(item["issue"])[:300],
                        "suggestion": str(item["suggestion"])[:1000],
                        "rule": str(item["rule"])[:500],
                    }
                    for item in items[:8]
                    if isinstance(item, dict)
                    and all(item.get(k) for k in ("issue", "suggestion", "rule"))
                ]
            gemini_status = "COMPLETED"
    except Exception:
        gemini_status = "UNAVAILABLE"

    return {
        "success": True,
        "assistant_type": "Rule-based review with Gemini contextual suggestions",
        "suggestions": suggestions,
        "suggestion_count": len(suggestions),
        "gemini_suggestions": gemini_suggestions,
        "gemini_suggestion_count": len(gemini_suggestions),
        "gemini_status": gemini_status,
        "note": ("Copy-review suggestions for a human to accept or reject. "
                 "Nothing is changed automatically."),
    }
