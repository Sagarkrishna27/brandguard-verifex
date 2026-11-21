# Backend tests

Run these commands from the repository root in PowerShell:

```powershell
py -m venv backend/.venv
backend/.venv/Scripts/Activate.ps1
python -m pip install -r backend/requirements-dev.txt
python -m pytest backend/tests -v
```

The current starter suite checks language-input validation and the health endpoint. The health tests mock the Tesseract executable calls, so they do not require local Tesseract installation. OCR accuracy still needs a separate labelled image test set containing English, Kannada, Hindi and mixed-script examples.

Do not interpret a passing unit suite as proof of OCR accuracy, legal compliance or deepfake detection performance.
