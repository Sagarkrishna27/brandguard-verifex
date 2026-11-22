import json
import os
import re

import requests

from claim_analyzer import analyze_claims


TAVILY_URL = "https://api.tavily.com/search"
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
MAX_CLAIMS = 5
MAX_SOURCES_PER_CLAIM = 5
REQUEST_TIMEOUT = (8, 25)


def _search_claim(claim_text):
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        return [], "TAVILY_NOT_CONFIGURED"

    payload = {
        "query": (
            f'"{claim_text}" independent evidence verification '
            "official data research"
        ),
        "topic": "general",
        "search_depth": "basic",
        "max_results": MAX_SOURCES_PER_CLAIM,
        "include_answer": False,
        "include_raw_content": False,
    }

    try:
        response = requests.post(
            TAVILY_URL,
            json=payload,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()

        sources = []
        for item in data.get("results", []):
            url = item.get("url", "")
            if not isinstance(url, str) or not url.startswith(("https://", "http://")):
                continue

            sources.append({
                "title": str(item.get("title", "Untitled source"))[:300],
                "url": url,
                "snippet": str(item.get("content", ""))[:1200],
                "published_date": item.get("published_date"),
            })

        return sources, "SEARCH_COMPLETED"

    except requests.exceptions.Timeout:
        return [], "SEARCH_TIMEOUT"
    except requests.exceptions.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else 0
        return [], f"SEARCH_HTTP_ERROR_{status}"
    except (requests.RequestException, ValueError):
        return [], "SEARCH_FAILED"


def _assess_sources(claim, sources):
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None, "GEMINI_NOT_CONFIGURED"

    if not sources:
        return None, "NO_SOURCES_TO_ASSESS"

    prompt = {
        "claim": claim.get("text", ""),
        "category": claim.get("category", ""),
        "evidence_required": claim.get("evidence_required", ""),
        "sources": sources,
        "instructions": [
            "Assess only the supplied source titles, URLs and snippets.",
            "Do not invent facts, sources, quotations or citations.",
            "A search result snippet is not authenticated proof.",
            "Distinguish supporting indications from contradictory indications.",
            "Consider source relevance, independence, date and limitations.",
            "If evidence is inadequate or ambiguous, use INSUFFICIENT.",
            "Never declare an advertising claim legally or factually verified.",
            "Always require human review.",
            "Return JSON with: assessment, reasoning, supporting_source_urls, "
            "contradicting_source_urls, limitations.",
            "assessment must be SUPPORTING_INDICATION, "
            "CONTRADICTING_INDICATION, MIXED or INSUFFICIENT.",
        ],
    }

    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_MODEL}:generateContent"
    )

    try:
        response = requests.post(
            url,
            headers={"x-goog-api-key": api_key},
            json={
                "contents": [{
                    "parts": [{
                        "text": json.dumps(prompt, ensure_ascii=False)
                    }]
                }],
                "generationConfig": {
                    "responseMimeType": "application/json",
                    "temperature": 0.1,
                },
            },
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()

        text = data["candidates"][0]["content"]["parts"][0]["text"]
        result = json.loads(text)

        allowed = {
            "SUPPORTING_INDICATION",
            "CONTRADICTING_INDICATION",
            "MIXED",
            "INSUFFICIENT",
        }
        assessment = result.get("assessment")
        if assessment not in allowed:
            return None, "INVALID_AI_RESPONSE"

        valid_urls = {source["url"] for source in sources}
        result["supporting_source_urls"] = [
            item for item in result.get("supporting_source_urls", [])
            if item in valid_urls
        ]
        result["contradicting_source_urls"] = [
            item for item in result.get("contradicting_source_urls", [])
            if item in valid_urls
        ]
        result["human_review_required"] = True
        result["verified"] = False

        return result, "AI_ASSESSMENT_COMPLETED"

    except (requests.RequestException, KeyError, IndexError, ValueError, TypeError):
        return None, "AI_ASSESSMENT_FAILED"


def investigate_advertisement(text):
    if not isinstance(text, str) or not text.strip():
        return {
            "success": False,
            "message": "Advertisement text is required.",
            "claims": [],
        }

    analysis = analyze_claims(text)
    claims = analysis.get("claims", [])[:MAX_CLAIMS]
    reports = []

    for claim in claims:
        if claim.get("status") == "CONTEXT_REVIEW_REQUIRED":
            reports.append({
                **claim,
                "investigation_status": "UNDER_REVIEW",
                "sources": [],
                "ai_assessment": None,
                "message": "Human review is required before researching this wording.",
            })
            continue

        sources, search_status = _search_claim(claim.get("text", ""))
        assessment, ai_status = _assess_sources(claim, sources)

        reports.append({
            **claim,
            "investigation_status": (
                assessment["assessment"]
                if assessment else
                "INSUFFICIENT" if sources else search_status
            ),
            "sources": sources,
            "ai_assessment": assessment,
            "search_status": search_status,
            "ai_status": ai_status,
            "human_review_required": True,
            "verified": False,
            "message": (
                "Preliminary research only. Sources and claims require "
                "independent human verification."
            ),
        })

    return {
        "success": True,
        "analysis_type": "Tavily public-source research with Gemini preliminary assessment",
        "total_claims_detected": analysis.get("total_claims", 0),
        "claims_investigated": len(reports),
        "claims_omitted_limit": max(0, len(analysis.get("claims", [])) - MAX_CLAIMS),
        "human_review_required": True,
        "verified": False,
        "claims": reports,
        "message": (
            "Research findings are preliminary. Search snippets and AI "
            "assessments are not proof of claim accuracy or legal compliance."
        ),
    }
