import ad_investigation


def test_missing_api_keys_never_claims_verification(monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    result = ad_investigation.investigate_advertisement(
        "Our product is the best skincare brand."
    )

    assert result["success"] is True
    assert result["verified"] is False
    assert result["human_review_required"] is True
    assert result["claims"]
    assert result["claims"][0]["search_status"] == "TAVILY_NOT_CONFIGURED"
    assert result["claims"][0]["ai_assessment"] is None


import ad_investigation


class FakeResponse:
    def __init__(self, data):
        self.data = data

    def raise_for_status(self):
        pass

    def json(self):
        return self.data


def test_investigation_uses_only_returned_source_urls(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "test-tavily-key")
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")

    calls = []

    def fake_post(url, **kwargs):
        calls.append(url)

        if "tavily" in url:
            return FakeResponse({
                "results": [{
                    "title": "Independent skincare study",
                    "url": "https://example.org/study",
                    "content": "A study discussing skincare products.",
                    "published_date": "2026-01-01",
                }]
            })

        return FakeResponse({
            "candidates": [{
                "content": {
                    "parts": [{
                        "text": (
                            '{"assessment":"SUPPORTING_INDICATION",'
                            '"reasoning":"The source mentions skincare.",'
                            '"supporting_source_urls":["https://example.org/study",'
                            '"https://fake.example/fabricated"],'
                            '"contradicting_source_urls":[],'
                            '"limitations":"Snippet only; not proof."}'
                        )
                    }]
                }
            }]
        })

    monkeypatch.setattr(ad_investigation.requests, "post", fake_post)

    result = ad_investigation.investigate_advertisement(
        "Our product is the best skincare brand."
    )

    claim = result["claims"][0]

    assert len(calls) == 2
    assert claim["ai_assessment"]["assessment"] == "SUPPORTING_INDICATION"
    assert claim["ai_assessment"]["supporting_source_urls"] == [
        "https://example.org/study"
    ]
    assert claim["verified"] is False
    assert claim["human_review_required"] is True
