from PIL import Image

from media_forensics import analyze_image


def test_image_forensics_labels_ai_detection_as_not_configured():
    image = Image.new("RGB", (160, 120), "white")
    result = analyze_image(
        image,
        lambda _image: {"risk_level": "LOW", "findings": []},
    )

    assert result["media_type"] == "image"
    assert result["image_forensics"]["status"] == "COMPLETED"
    assert result["ai_generated_media_detection"]["status"] == "NOT_CONFIGURED"
    assert result["human_review_required"] is True
    assert any("do not prove" in item for item in result["limitations"])


def test_image_forensics_does_not_hide_existing_heuristic_failure():
    image = Image.new("RGB", (160, 120), "white")

    def fail(_image):
        raise RuntimeError("forensics unavailable")

    result = analyze_image(image, fail)

    assert result["image_forensics"]["status"] == "FAILED"
    assert result["image_forensics"]["result"]["error"] == "forensics unavailable"
    assert result["ai_generated_media_detection"]["status"] == "NOT_CONFIGURED"
