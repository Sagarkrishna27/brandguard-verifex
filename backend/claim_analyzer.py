import re
import os
import json
from google import genai
from google.genai import types
from typing import List, Dict


CLAIM_RULES = {
    "SUPERIORITY": {
        "patterns": [
            r"\b(best|number\s*1|no\.?\s*1|leading|top[- ]rated|superior|greatest)\b",
            r"\b(better than|better than all|unmatched|world[- ]class)\b",
        ],
        "evidence": "Independent comparison, ranking, or award evidence.",
        "risk": "HIGH",
    },
    "GUARANTEE": {
        "patterns": [
            r"\b(guaranteed|100%\s*results?|sure[- ]shot|risk[- ]free|money[- ]back)\b",
            r"\b(we guarantee|will definitely|assured results?|money\s+back)\b",
        ],
        "evidence": "Written guarantee terms, conditions, and proof supporting the promise.",
        "risk": "HIGH",
    },
    "GOVERNMENT_APPROVAL": {
        "patterns": [
            r"\b(government approved|government certified|govt\.?\s*approved)\b",
            r"\b(approved by ministry|officially approved)\b",
        ],
        "evidence": "Valid approval document from the named government authority.",
        "risk": "HIGH",
    },
    "CERTIFICATION": {
        "patterns": [
            r"\b(ISO\s*9001|ISO\s*14001|certified|certification|accredited)\b",
        ],
        "evidence": "Valid certificate, issuing body, scope, and expiry date.",
        "risk": "MEDIUM",
    },
    "INGREDIENT": {
        "patterns": [
            r"\b(100%\s*)?(natural|organic)\s+ingredients?\b",
            r"\b(made with|formulated with)\b.{0,60}\b(natural|organic)\b",
        ],
        "evidence": "Full ingredient list, formulation records, and relevant natural or organic certification where claimed.",
        "risk": "MEDIUM",
    },
    "MEDICAL": {
        "patterns": [
            r"\b(cures?|heals?|treats?|prevents?|clinically proven|clinically tested|dermatologist[- ]tested|doctor recommended)\b",
            r"\b(guaranteed weight loss|instant relief|no side effects)\b",
            r"\b(reduces?|fades?|removes?)\b.{0,80}\bby\s+\d+(?:\.\d+)?\s*%",
        ],
        "evidence": "Appropriate clinical evidence, approvals, and substantiation.",
        "risk": "HIGH",
    },
    "FINANCIAL": {
        "patterns": [
            r"\b(guaranteed returns?|double your money|zero risk|assured profit)\b",
            r"\b(earn \d+%|returns? up to \d+%)\b",
        ],
        "evidence": "Verified financial data, assumptions, risks, and applicable disclosures.",
        "risk": "HIGH",
    },
    "PERFORMANCE": {
        "patterns": [
            r"\b(works? \d+% faster|saves? \d+%|increases? by \d+%)\b",
            r"\b(last(s|ing)? \d+ hours?|twice as fast|instant results?)\b",
        ],
        "evidence": "Reproducible performance tests and supporting data.",
        "risk": "MEDIUM",
    },
    "DISCOUNT_OR_OFFER": {
        "patterns": [
            r"\b(\d+%\s*off|flat\s*\d+%|buy one get one|bogo|free delivery)\b",
            r"\b(save \d+%|limited time offer|special offer)\b",
        ],
        "evidence": "Offer terms, eligibility, original price, and validity dates.",
        "risk": "MEDIUM",
    },
    "TESTIMONIAL": {
        "patterns": [
            r"\b(customer review|customer testimonial|real customer|trusted by (?:over\s+)?\d+)\b",
            r"\b(\d+ satisfied customers|users love us)\b",
        ],
        "evidence": "Authentic customer consent and records supporting the testimonial.",
        "risk": "MEDIUM",
    },
    "ENVIRONMENTAL": {
        "patterns": [
            r"\b(100%\s*eco[- ]friendly|zero carbon|carbon neutral|environmentally friendly)\b",
            r"\b(fully sustainable|biodegradable|plastic[- ]free)\b",
        ],
        "evidence": "Relevant testing, certification, or lifecycle/environmental evidence.",
        "risk": "MEDIUM",
    },
    "SCARCITY": {
        "patterns": [
            r"\b(only \d+ left|last chance|limited stock|selling fast|ends today)\b",
        ],
        "evidence": "Current stock or offer records supporting the scarcity statement.",
        "risk": "MEDIUM",
    },
    "DELIVERY": {
        "patterns": [
            r"\b(delivery within \d+ hours?|delivered in \d+ days?|same[- ]day delivery)\b",
            r"\b(instant delivery|guaranteed delivery)\b",
        ],
        "evidence": "Delivery service terms and records supporting the promised timeline.",
        "risk": "MEDIUM",
    },
    "OUTCOME": {
        "patterns": [
            r"\b(shape your body|lose \d+(?:\.\d+)?\s*(?:kg|kilograms?|lb|lbs|pounds?)|results?)\s+(?:in|within)\s+\d+\s+days?\b",
        ],
        "evidence": "Programme documentation and an individual-results-vary disclaimer.",
        "risk": "HIGH",
    },
}


QUESTION_START = re.compile(
    r"^\s*(are|is|am|do|does|did|can|could|would|will|should|what|why|how)\b",
    re.IGNORECASE,
)

NEGATION = re.compile(
    r"\b(not|never|cannot|can't|isn't|aren't|don't|doesn't|won't|without|no claim)\b",
    re.IGNORECASE,
)


def split_into_sentences(text: str) -> List[str]:
    # Protect abbreviations such as "No. 1" before splitting sentences.
    protected = re.sub(r"\bNo\.(?=\s*\d)", "No<NO_DOT>", text, flags=re.IGNORECASE)
    parts = re.split(r"(?<=[.!?])\s+|\n+", protected)
    parts = [part.replace("<NO_DOT>", ".") for part in parts]
    return [part.strip() for part in parts if part.strip()]



def _gemini_context_claims(text: str) -> List[Dict]:
    """Find possible implied claims missed by deterministic rules."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return []

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model="gemini-3.5-flash-lite",
            contents=[
                "Review this advertisement text for implied or context-dependent "
                "factual, comparative, medical, financial, performance, environmental, "
                "or other advertising claims that may be missed by keyword rules. "
                "Return JSON only in this format: "
                '{"claims":[{"text":"exact quoted text from the ad",'
                '"category":"one category from the supplied list",'
                '"explanation":"why this may imply a claim",'
                '"evidence_required":"evidence needed to substantiate it"}]}. '
                "Allowed categories: " + ", ".join(CLAIM_RULES.keys()) + ". "
                "Only return claims supported by the supplied text. Do not invent "
                "claims, facts, evidence, or legal violations. If none, return "
                '{"claims":[]}. Advertisement text:\n' + text[:12000]
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.1,
            ),
        )

        data = json.loads(response.text or "{}")
        suggestions = data.get("claims", [])
        if not isinstance(suggestions, list):
            return []

        results = []
        for item in suggestions[:10]:
            if not isinstance(item, dict):
                continue

            quote = str(item.get("text", "")).strip()
            category = str(item.get("category", "")).upper().strip()

            if (
                not quote
                or quote.casefold() not in text.casefold()
                or category not in CLAIM_RULES
            ):
                continue

            results.append({
                "text": quote,
                "category": category,
                "risk_level": "REVIEW",
                "status": "CONTEXT_REVIEW_REQUIRED",
                "explanation": (
                    "Gemini identified a possible implied or context-dependent "
                    "claim: " + str(item.get("explanation", "Human review is required."))
                ),
                "evidence_required": str(
                    item.get("evidence_required")
                    or CLAIM_RULES[category]["evidence"]
                ),
            })

        return results

    except Exception:
        # Gemini failure must never interrupt the existing rule-based analysis.
        return []

def analyze_claims(text: str) -> Dict:
    if not isinstance(text, str) or not text.strip():
        return {
            "success": False,
            "message": "No advertisement text was provided.",
            "total_claims": 0,
            "claims": [],
        }

    claims = []
    sentences = split_into_sentences(text)

    for sentence in sentences:
        sentence_lower = sentence.lower()

        # Avoid automatically flagging questions as factual claims.
        if QUESTION_START.search(sentence):
            continue

        # Check comma/semicolon-separated claims independently.
        segments = [
            part.strip()
            for part in re.split(r"[,;]", sentence)
            if part.strip()
        ]

        for category, rule in CLAIM_RULES.items():
            matching_segments = [
                segment for segment in segments
                if any(
                    re.search(pattern, segment, re.IGNORECASE)
                    for pattern in rule["patterns"]
                )
            ]

            for claim_text in matching_segments:
                # Keep negated statements under human review.
                if NEGATION.search(sentence_lower):
                    claims.append({
                        "text": claim_text,
                        "category": category,
                        "risk_level": "REVIEW",
                        "status": "CONTEXT_REVIEW_REQUIRED",
                        "explanation": (
                            "A claim-related phrase appears with negation. "
                            "Its full meaning needs human review."
                        ),
                        "evidence_required": rule["evidence"],
                    })
                    continue

                claims.append({
                    "text": claim_text,
                    "category": category,
                    "risk_level": rule["risk"],
                    "status": "EVIDENCE_REQUIRED",
                    "explanation": (
                        f"This statement may make a {category.lower().replace('_', ' ')} "
                        "advertising claim. Supporting evidence should be checked."
                    ),
                    "evidence_required": rule["evidence"],
                })

    # Supplement deterministic findings with Gemini contextual suggestions.
    existing = {
        (claim["text"].casefold(), claim["category"])
        for claim in claims
    }
    for suggestion in _gemini_context_claims(text):
        key = (suggestion["text"].casefold(), suggestion["category"])
        if key not in existing:
            claims.append(suggestion)
            existing.add(key)

    return {
        "success": True,
        "analysis_type": "Context-aware rule-based claim analysis",
        "total_claims": len(claims),
        "manual_review_required": True,
        "claims": claims,
        "message": (
            "Detected claims are potential review flags, not proof of "
            "misleading advertising or legal violations."
        ),
    }