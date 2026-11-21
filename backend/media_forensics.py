"""Explainable media-forensics triage for images and videos.

This module does not claim to identify AI-generated media. It reports
observable signals and explicitly labels unsupported detection capabilities.
"""
import os
import shutil
import subprocess
import tempfile

import cv2
import numpy as np
from PIL import Image


MAX_VIDEO_BYTES = 200 * 1024 * 1024
MAX_IMAGE_BYTES = 15 * 1024 * 1024
MAX_VIDEO_SAMPLES = 12


def _face_regions(image):
    """Return face-like regions from OpenCV's bundled frontal-face cascade."""
    cascade_path = os.path.join(cv2.data.haarcascades, "haarcascade_frontalface_default.xml")
    classifier = cv2.CascadeClassifier(cascade_path)
    if classifier.empty():
        return {"status": "NOT_CONFIGURED", "count": 0, "regions": []}

    rgb = image.convert("RGB")
    gray = cv2.cvtColor(np.asarray(rgb), cv2.COLOR_RGB2GRAY)
    height, width = gray.shape[:2]
    scale = min(1.0, 1200 / max(width, height))
    if scale < 1:
        gray = cv2.resize(gray, (max(1, int(width * scale)), max(1, int(height * scale))))
    boxes = classifier.detectMultiScale(
        gray, scaleFactor=1.1, minNeighbors=5, minSize=(24, 24)
    )
    regions = []
    for x, y, w, h in boxes:
        regions.append({
            "x": round(float(x / scale), 1),
            "y": round(float(y / scale), 1),
            "width": round(float(w / scale), 1),
            "height": round(float(h / scale), 1),
        })
    return {
        "status": "COMPLETED",
        "count": len(regions),
        "regions": regions,
        "meaning": "Face-like regions only. This is not face identity or deepfake detection.",
    }


def analyze_image(image, image_forensics_fn):
    image = image.convert("RGB")
    try:
        manipulation = image_forensics_fn(image)
        manipulation_status = "COMPLETED"
    except Exception as error:
        manipulation = {"error": str(error)[:300]}
        manipulation_status = "FAILED"

    faces = _face_regions(image)
    return {
        "media_type": "image",
        "image_forensics": {
            "status": manipulation_status,
            "result": manipulation,
        },
        "face_analysis": faces,
        "ai_generated_media_detection": {
            "status": "NOT_CONFIGURED",
            "message": "No validated AI-image or face-swap detection model is configured. No AI-generation verdict is made.",
        },
        "limitations": [
            "Compression, resizing, filters and poster design can trigger forensic heuristics.",
            "Face detection can miss faces or detect face-like patterns.",
            "These signals do not prove editing, deception or AI generation.",
        ],
        "human_review_required": True,
    }


def _audio_stream_info(video_path):
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return {
            "status": "NOT_CONFIGURED",
            "present": None,
            "message": "ffprobe is unavailable; audio stream presence could not be checked.",
            "deepfake_voice_detection": "NOT_CONFIGURED",
        }
    try:
        probe = subprocess.run(
            [
                ffprobe, "-v", "error", "-select_streams", "a",
                "-show_entries", "stream=index,codec_name",
                "-of", "json", video_path,
            ],
            capture_output=True, text=True, timeout=20, check=False,
        )
        if probe.returncode != 0:
            return {
                "status": "UNABLE_TO_VERIFY", "present": None,
                "message": "ffprobe could not inspect the audio stream.",
                "deepfake_voice_detection": "NOT_CONFIGURED",
            }
        import json
        streams = json.loads(probe.stdout or "{}").get("streams", [])
        return {
            "status": "COMPLETED",
            "present": bool(streams),
            "streams": [{"codec": item.get("codec_name")} for item in streams],
            "message": "Audio stream metadata only; speech is not transcribed or classified.",
            "deepfake_voice_detection": "NOT_CONFIGURED",
        }
    except Exception as error:
        return {
            "status": "UNABLE_TO_VERIFY", "present": None,
            "message": str(error)[:300],
            "deepfake_voice_detection": "NOT_CONFIGURED",
        }


def analyze_video(video_path, image_forensics_fn):
    capture = cv2.VideoCapture(video_path)
    if not capture.isOpened():
        raise ValueError("The video could not be decoded by OpenCV.")

    try:
        fps = capture.get(cv2.CAP_PROP_FPS) or 25.0
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        duration = frame_count / fps if frame_count > 0 else 0.0
        sample_count = min(MAX_VIDEO_SAMPLES, max(1, frame_count))
        indices = np.linspace(0, max(0, frame_count - 1), sample_count, dtype=int) if frame_count else [0]
        samples = []
        previous_hist = None
        previous_hash = None
        repeated_frames = 0
        scene_changes = []

        for index in indices:
            capture.set(cv2.CAP_PROP_POS_FRAMES, int(index))
            ok, frame = capture.read()
            if not ok:
                continue
            timestamp = float(index / fps)
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            image = Image.fromarray(rgb)
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            small = cv2.resize(gray, (32, 32))
            frame_hash = cv2.dct(np.float32(small))
            hash_bits = frame_hash[:8, :8] > np.median(frame_hash[:8, :8])
            histogram = cv2.calcHist([frame], [0, 1], None, [16, 16], [0, 256, 0, 256])
            cv2.normalize(histogram, histogram)
            if previous_hash is not None and np.array_equal(hash_bits, previous_hash):
                repeated_frames += 1
            if previous_hist is not None:
                similarity = float(cv2.compareHist(previous_hist, histogram, cv2.HISTCMP_CORREL))
                if similarity < 0.25:
                    scene_changes.append({
                        "timestamp_seconds": round(timestamp, 2),
                        "histogram_similarity": round(similarity, 3),
                        "note": "Large visual change between sampled frames; may be a normal cut or transition.",
                    })
            previous_hash = hash_bits
            previous_hist = histogram
            frame_report = analyze_image(image, image_forensics_fn)
            samples.append({
                "timestamp_seconds": round(timestamp, 2),
                "frame_forensics": frame_report["image_forensics"],
                "face_analysis": frame_report["face_analysis"],
            })
    finally:
        capture.release()

    return {
        "media_type": "video",
        "duration_seconds": round(duration, 2),
        "frames_sampled": len(samples),
        "frame_analysis": samples,
        "temporal_signals": {
            "repeated_sampled_frames": repeated_frames,
            "large_visual_changes": scene_changes,
            "note": "These are sampling signals, not proof of frame insertion, editing or deepfake generation.",
        },
        "audio": _audio_stream_info(video_path),
        "ai_generated_video_detection": {
            "status": "NOT_CONFIGURED",
            "message": "No validated deepfake video model or temporal identity model is configured.",
        },
        "limitations": [
            "Only a maximum of 12 frames are sampled; brief edits can be missed.",
            "Scene changes and repeated frames can be normal editing choices.",
            "Audio is inspected for stream metadata only; speech is not transcribed or classified.",
            "Face-like region detection is not facial identity or deepfake detection.",
        ],
        "human_review_required": True,
    }
