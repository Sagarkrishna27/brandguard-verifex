from fastapi.testclient import TestClient

import main


def test_health_endpoint_reports_status(monkeypatch):
    monkeypatch.setattr(main.pytesseract, "get_languages", lambda config="": ["eng", "kan"])
    monkeypatch.setattr(main.pytesseract, "get_tesseract_version", lambda: "5.4.0")

    client = TestClient(main.app)
    response = client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
    assert body["version"] == main.VERSION
    assert body["tesseract"] == "5.4.0"
    assert "eng" in body["installed_languages"]
    assert body["missing_language_models"]


def test_health_endpoint_surfaces_tesseract_unavailable(monkeypatch):
    def unavailable(config=""):
        raise RuntimeError("Tesseract is not installed")

    monkeypatch.setattr(main.pytesseract, "get_languages", unavailable)
    client = TestClient(main.app)
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["status"] == "error"
    assert "Tesseract is not installed" in response.json()["message"]
