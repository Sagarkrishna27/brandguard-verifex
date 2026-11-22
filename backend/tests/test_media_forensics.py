from PIL import Image
import numpy as np

import media_forensics
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


def test_image_forensics_reports_missing_face_detector_as_not_configured(monkeypatch):
    monkeypatch.delattr(media_forensics.cv2, "CascadeClassifier", raising=False)
    image = Image.new("RGB", (160, 120), "white")

    result = analyze_image(image, lambda _image: {"risk_level": "LOW", "findings": []})

    assert result["face_analysis"]["status"] == "NOT_CONFIGURED"
    assert result["face_analysis"]["count"] == 0
    assert "does not provide" in result["face_analysis"]["message"]

def test_image_manipulation_triage_summarizes_observable_signals():
    image = Image.new("RGB", (160, 120), "white")
    result = analyze_image(
        image,
        lambda _image: {
            "risk_level": "MEDIUM",
            "findings": ["metadata anomaly", "compression inconsistency"],
        },
    )

    triage = result["manipulation_triage"]
    assert triage["status"] == "COMPLETED"
    assert triage["observable_signals"]["heuristic_finding_count"] == 2
    assert triage["ai_deepfake_detection"] == "NOT_CONFIGURED"
    assert triage["verdict"] is None
    assert triage["human_review_required"] is True


def test_image_manipulation_triage_handles_heuristic_failure():
    image = Image.new("RGB", (160, 120), "white")

    def fail(_image):
        raise RuntimeError("forensics unavailable")

    result = analyze_image(image, fail)
    triage = result["manipulation_triage"]

    assert triage["status"] == "PARTIAL"
    assert triage["observable_signals"]["heuristic_finding_count"] is None
    assert triage["verdict"] is None

def test_video_manipulation_triage_summarizes_visual_and_audio_signals(monkeypatch):
    frames = [
        np.zeros((48, 64, 3), dtype=np.uint8),
        np.full((48, 64, 3), 255, dtype=np.uint8),
    ]

    class FakeCapture:
        def __init__(self):
            self.position = 0

        def isOpened(self):
            return True

        def get(self, prop):
            if prop == media_forensics.cv2.CAP_PROP_FPS:
                return 1.0
            if prop == media_forensics.cv2.CAP_PROP_FRAME_COUNT:
                return len(frames)
            return 0

        def set(self, prop, value):
            self.position = int(value)
            return True

        def read(self):
            if 0 <= self.position < len(frames):
                frame = frames[self.position].copy()
                self.position += 1
                return True, frame
            return False, None

        def release(self):
            pass

    monkeypatch.setattr(
        media_forensics.cv2, "VideoCapture", lambda _path: FakeCapture()
    )
    monkeypatch.setattr(
        media_forensics,
        "_audio_stream_info",
        lambda _path: {
            "status": "COMPLETED",
            "present": True,
            "streams": [{"codec": "aac"}],
        },
    )

    result = media_forensics.analyze_video(
        "simulated.mp4",
        lambda _image: {"findings": ["test signal"]},
    )

    triage = result["manipulation_triage"]
    signals = triage["observable_signals"]

    assert result["media_type"] == "video"
    assert result["frames_sampled"] == 2
    assert triage["status"] == "COMPLETED"
    assert signals["heuristic_finding_count"] == 2
    assert signals["audio_stream_present"] is True
    assert triage["ai_deepfake_detection"] == "NOT_CONFIGURED"
    assert triage["voice_clone_detection"] == "NOT_CONFIGURED"
    assert triage["verdict"] is None
    assert triage["human_review_required"] is True
