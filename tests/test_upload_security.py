"""Regression tests for the public upload attack surface reviewed in #92."""

from __future__ import annotations

import asyncio
import io
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from starlette.datastructures import UploadFile

from api.main import app
from api.middleware import upload_security
from api.routes import verify

client = TestClient(app, headers={"X-API-Key": "test-pro-key"})


def _image_bytes(image_format="PNG", size=(80, 120)):
    buffer = io.BytesIO()
    Image.new("RGB", size, "white").save(buffer, format=image_format)
    return buffer.getvalue()


def _batch_result():
    return {
        "verdict": "AUTHENTIC",
        "verdict_color": "#10b981",
        "tamper_risk_percentage": 2.0,
        "recommendation": "Proceed",
        "flagged_regions": [],
        "findings_summary": [],
        "extracted_metadata": {
            "detected_bank_code": "COMBANK",
            "bank_name": "Commercial Bank",
        },
    }


@pytest.mark.parametrize(
    "filename",
    [
        "../outside.png",
        "..\\outside.png",
        "/etc/receipt.png",
        "C:\\Windows\\receipt.png",
        "nested/path/receipt.png",
        "<img src=x onerror=alert(1)>.png",
        "control\x00name.png",
    ],
)
def test_batch_never_reflects_or_uses_untrusted_filenames(
    filename, monkeypatch, tmp_path
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        verify, "_analyze_image", lambda *args, **kwargs: _batch_result()
    )

    response = client.post(
        "/api/v1/batch-verify",
        files=[("files", (filename, _image_bytes(), "image/png"))],
    )

    assert response.status_code == 200
    assert response.json()["items"][0]["filename"] == "upload_001"
    assert filename not in response.text
    assert list(tmp_path.iterdir()) == []


def test_frontend_assigns_batch_filename_as_text_not_html():
    source = (Path(__file__).parents[1] / "web" / "js" / "app.js").read_text(
        encoding="utf-8"
    )
    assert "<span>${item.filename}</span>" not in source
    assert '.querySelector(".batch-file-name").textContent = item.filename' in source


@pytest.mark.parametrize(
    "filename,content_type",
    [("receipt.svg", "image/svg+xml"), ("receipt.png", "image/png")],
)
def test_svg_script_content_is_rejected_even_when_disguised(filename, content_type):
    svg = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'
    response = client.post(
        "/api/v1/verify", files={"file": (filename, svg, content_type)}
    )
    assert response.status_code == 400
    assert response.json() == {
        "detail": "Uploaded file is not a valid, complete JPEG or PNG image."
    }
    assert "SVG" not in response.text
    assert "script" not in response.text


def test_actual_png_is_accepted_despite_spoofed_extension_and_content_type(
    monkeypatch,
):
    result = _batch_result()
    result.update(
        {
            "confidence_score": 0.98,
            "layer_breakdowns": {},
        }
    )
    monkeypatch.setattr(verify, "_analyze_image", lambda *args, **kwargs: result)
    response = client.post(
        "/api/v1/verify",
        files={"file": ("../../payload.svg", _image_bytes(), "text/html")},
    )
    assert response.status_code == 200


def test_request_body_limit_runs_before_multipart_handler(monkeypatch):
    reader = AsyncMock(side_effect=AssertionError("route handler must not run"))
    monkeypatch.setattr(verify, "_read_bounded_upload", reader)
    monkeypatch.setitem(upload_security.UPLOAD_BODY_LIMITS, "/api/v1/verify", 64)

    response = client.post(
        "/api/v1/verify",
        files={"file": ("receipt.png", _image_bytes(), "image/png")},
    )

    assert response.status_code == 413
    assert response.json() == {"detail": "Upload request exceeds the permitted size."}
    assert response.headers["X-Request-ID"]
    reader.assert_not_called()


def test_streamed_body_limit_does_not_require_content_length(monkeypatch):
    monkeypatch.setitem(upload_security.UPLOAD_BODY_LIMITS, "/api/v1/verify", 4)
    sent = []
    messages = iter(
        [
            {"type": "http.request", "body": b"123", "more_body": True},
            {"type": "http.request", "body": b"45", "more_body": False},
        ]
    )

    async def receive():
        return next(messages)

    async def consume_body(scope, receive, send):
        while True:
            message = await receive()
            if not message.get("more_body", False):
                break

    async def send(message):
        sent.append(message)

    middleware = upload_security.UploadBodyLimitMiddleware(consume_body)
    asyncio.run(
        middleware(
            {"type": "http", "method": "POST", "path": "/api/v1/verify", "headers": []},
            receive,
            send,
        )
    )

    assert sent[0]["status"] == 413


def test_extremely_long_filename_is_not_reflected(monkeypatch):
    filename = ("a" * 5_000) + ".png"
    monkeypatch.setattr(
        verify, "_analyze_image", lambda *args, **kwargs: _batch_result()
    )

    response = client.post(
        "/api/v1/batch-verify",
        files=[("files", (filename, _image_bytes(), "image/png"))],
    )

    assert response.status_code in {200, 400}
    assert filename not in response.text
    if response.status_code == 200:
        assert response.json()["items"][0]["filename"] == "upload_001"


def test_invalid_content_length_is_rejected_safely():
    response = client.post(
        "/api/v1/verify",
        headers={"Content-Length": "invalid"},
        content=b"not parsed",
    )
    assert response.status_code == 400
    assert response.json() == {"detail": "Upload request is malformed."}


def test_corrupt_image_error_does_not_leak_malicious_path():
    malicious = "C:\\private\\server\\..\\receipt.png"
    response = client.post(
        "/api/v1/verify",
        files={"file": (malicious, b"not an image", "image/png")},
    )
    assert response.status_code == 400
    assert malicious not in response.text
    assert "private" not in response.text


def test_decompression_bomb_is_rejected_at_public_endpoint(monkeypatch):
    payload = _image_bytes(size=(15, 10))
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 100)
    response = client.post(
        "/api/v1/verify",
        files={"file": ("receipt.png", payload, "image/png")},
    )
    assert response.status_code == 413
    assert response.json()["detail"] == "Image dimensions exceed the permitted limit."


def test_upload_spool_is_closed_after_bounded_read():
    spool = tempfile.SpooledTemporaryFile(max_size=1)
    spool.write(_image_bytes())
    spool.seek(0)
    upload = UploadFile(file=spool, filename="../../receipt.png")

    contents = asyncio.run(verify._read_bounded_upload(upload))

    assert contents.startswith(b"\x89PNG")
    assert spool.closed
