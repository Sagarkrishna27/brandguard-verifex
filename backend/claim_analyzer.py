import re
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
            r"\b(we guarantee|will definitely|assured results?)\b",
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
    "MEDICAL": {
        "patterns": [
            r"\b(cures?|heals?|treats?|prevents?|clinically proven|doctor recommended)\b",
            r"\b(guaranteed weight loss|instant relief|no side effects)\b",
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
            r"\b(customer review|customer testimonial|real customer|trusted by \d+)\b",
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
    parts = re.split(r"(?<=[.!?])\s+|\n+", text)
    return [part.strip() for part in parts if part.strip()]


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

        for category, rule in CLAIM_RULES.items():
            matched = any(
                re.search(pattern, sentence_lower, re.IGNORECASE)
                for pattern in rule["patterns"]
            )

            if not matched:
                continue

            # A negation needs context review instead of automatic classification.
            if NEGATION.search(sentence_lower):
                claims.append({
                    "text": sentence,
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
                "text": sentence,
                "category": category,
                "risk_level": rule["risk"],
                "status": "EVIDENCE_REQUIRED",
                "explanation": (
                    f"This statement may make a {category.lower().replace('_', ' ')} "
                    "advertising claim. Supporting evidence should be checked."
                ),
                "evidence_required": rule["evidence"],
            })

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