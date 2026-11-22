from claim_analyzer import analyze_claims


def test_no_1_period_does_not_split_sentence():
    result = analyze_claims("India's No. 1 skincare brand.")

    assert any(
        claim["category"] == "SUPERIORITY"
        and claim["text"] == "India's No. 1 skincare brand."
        for claim in result["claims"]
    )


def test_comma_separated_claims_are_extracted_independently():
    result = analyze_claims(
        "India's No. 1 skincare brand, trusted by 10 million customers."
    )

    claims = {
        (claim["category"], claim["text"])
        for claim in result["claims"]
    }

    assert ("SUPERIORITY", "India's No. 1 skincare brand") in claims
    assert ("TESTIMONIAL", "trusted by 10 million customers.") in claims


def test_medical_claim_remains_complete():
    result = analyze_claims(
        "Clinically proven to reduce acne by 100% within 7 days."
    )

    assert any(
        claim["category"] == "MEDICAL"
        and claim["text"] == "Clinically proven to reduce acne by 100% within 7 days."
        for claim in result["claims"]
    )


def test_glownaturals_ad_extracts_all_expected_claim_categories():
    text = (
        "GlowNaturals is India's leading organic skincare brand, "
        "trusted by over 2 million happy customers. "
        "Our dermatologist-tested vitamin C serum visibly reduces dark spots "
        "by 85% in just 14 days. Made with 100% natural ingredients and "
        "clinically tested for all skin types. "
        "Get glowing skin guaranteed or your money back!"
    )
    result = analyze_claims(text)
    categories = {claim["category"] for claim in result["claims"]}

    assert "SUPERIORITY" in categories
    assert "TESTIMONIAL" in categories
    assert "MEDICAL" in categories
    assert "INGREDIENT" in categories
    assert "GUARANTEE" in categories


def test_trusted_by_over_customer_count_is_detected():
    result = analyze_claims("Trusted by over 2 million happy customers.")

    assert any(claim["category"] == "TESTIMONIAL" for claim in result["claims"])
