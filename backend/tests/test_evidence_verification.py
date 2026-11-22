import main


def test_text_overlap_never_automatically_supports_a_claim():
    result = main._verify_evidence(
        [{"text": "India's number one skincare brand", "category": "SUPERIORITY"}],
        [{
            "name": "market-study.txt",
            "text": "India's number one skincare brand according to independent market research",
        }],
    )

    assert result["claims"][0]["status"] == "UNDER_REVIEW"
    assert result["summary"]["supported_count"] == 0
    assert result["summary"]["UNDER_REVIEW"] == 1


def test_pdf_bytes_are_not_used_as_evidence_when_extraction_is_unavailable():
    document = main._extract_evidence_document(
        "certificate.pdf",
        "application/pdf",
        b"%PDF-1.7\x00binary-content",
    )

    assert document["text"] == ""
    assert document["extraction_status"] in {"NOT_CONFIGURED", "FAILED"}


def test_selectable_pdf_text_is_extracted():
    content = b"BT /F1 12 Tf 10 100 Td (Number one skincare brand) Tj ET"
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 300] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"\nendstream",
    ]
    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, body in enumerate(objects, 1):
        offsets.append(len(pdf))
        pdf.extend(f"{index} 0 obj\n".encode() + body + b"\nendobj\n")
    xref_offset = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode())
    pdf.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF".encode()
    )

    document = main._extract_evidence_document("claim.pdf", "application/pdf", bytes(pdf))

    assert document["extraction_status"] == "COMPLETED"
    assert "Number one skincare brand" in document["text"]


def test_non_utf8_text_is_not_silently_matched():
    document = main._extract_evidence_document("certificate.txt", "text/plain", b"\xff\xfe")

    assert document["text"] == ""
    assert document["extraction_status"] == "FAILED"


def test_unreadable_uploaded_document_is_insufficient_not_missing():
    document = main._extract_evidence_document(
        "certificate.pdf",
        "application/pdf",
        b"%PDF-1.7\x00binary-content",
    )
    result = main._verify_evidence(
        [{"text": "India's number one skincare brand", "category": "SUPERIORITY"}],
        [document],
    )

    assert result["claims"][0]["status"] == "INSUFFICIENT"
    assert result["summary"]["INSUFFICIENT"] == 1