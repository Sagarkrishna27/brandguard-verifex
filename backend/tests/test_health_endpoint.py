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
    assert response.json()["status"] == "degraded"
    assert "Tesseract is not installed" in response.json()["message"]


def test_readiness_endpoint_reports_ready_when_english_ocr_is_available(monkeypatch):
    monkeypatch.setattr(main.pytesseract, "get_languages", lambda config="": ["eng", "kan"])
    monkeypatch.setattr(main.pytesseract, "get_tesseract_version", lambda: "5.4.0")

    response = TestClient(main.app).get("/api/ready")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["required_language_models"] == ["eng"]
    assert body["integrations"]["tavily_configured"] is False
    assert body["integrations"]["gemini_configured"] is False


def test_readiness_endpoint_returns_503_when_tesseract_is_unavailable(monkeypatch):
    def unavailable(config=""):
        raise RuntimeError("Tesseract is not installed")

    monkeypatch.setattr(main.pytesseract, "get_languages", unavailable)

    response = TestClient(main.app).get("/api/ready")

    assert response.status_code == 503
    assert response.json()["detail"]["status"] == "not_ready"
    assert response.json()["detail"]["checks"]["tesseract"] == "unavailable"


def test_readiness_endpoint_returns_503_when_english_model_is_missing(monkeypatch):
    monkeypatch.setattr(main.pytesseract, "get_languages", lambda config="": ["kan"])
    monkeypatch.setattr(main.pytesseract, "get_tesseract_version", lambda: "5.4.0")

    response = TestClient(main.app).get("/api/ready")

    assert response.status_code == 503
    assert response.json()["detail"]["checks"]["english_ocr"] == "missing"
