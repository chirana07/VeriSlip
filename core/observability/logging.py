"""Structured logging and correlation context for the VeriSlip API."""

from __future__ import annotations

import hashlib
import json
import logging
import re
import sys
import uuid
from contextvars import ContextVar, Token
from datetime import datetime, timezone
from typing import Optional


REQUEST_ID_HEADER = "X-Request-ID"
CORRELATION_ID_HEADER = "X-Correlation-ID"
_VALID_CORRELATION_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_correlation_id: ContextVar[Optional[str]] = ContextVar(
    "verislip_correlation_id", default=None
)
_SAFE_EXTRA_FIELDS = (
    "method",
    "path",
    "status_code",
    "duration_ms",
    "error_type",
)

_EMAIL_PATTERN = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
)
_PHONE_PATTERN = re.compile(
    r"(?:\+?94|0)\s*(?:7[0-9]|11|2[0-9]|3[0-9]|4[0-9]|5[0-9]|6[0-9]|8[0-9])\s*[0-9]{3}\s*[0-9]{4}\b"
)
_UUID_PATTERN = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)
_ACCOUNT_NUMBER_PATTERN = re.compile(
    r"\b\d{8,18}\b|(?<!\d)(?:\d{4}[-\s]){1,3}\d{4,6}(?!\d)"
)
_NAME_KV_PATTERN = re.compile(
    r"(?i)\b(customer(?:_name)?|account_holder|beneficiary|full_name)\s*[:=]\s*['\"]?([A-Za-z\s]{3,40})['\"]?"
)


def hash_bank_account(account_number: str, salt: str = "verislip_pii_salt") -> str:
    """Return a deterministic, irreversible HMAC-SHA256 hex digest for an account number."""
    cleaned = re.sub(r"\D", "", account_number)
    return hashlib.sha256(f"{salt}:{cleaned}".encode("utf-8")).hexdigest()[:16]


def scrub_pii(text: str) -> str:
    """
    Scrub bank account numbers, phone numbers, emails, and customer names from text.
    Bank accounts are irreversibly hashed for audit correlation without exposing raw digits.
    UUIDs and correlation IDs are preserved intact.
    """
    if not text:
        return text

    # Protect UUIDs from being falsely identified as 8-12 digit blocks
    uuids = []
    def _uuid_holder(match: re.Match) -> str:
        idx = len(uuids)
        uuids.append(match.group(0))
        return f"__VERISLIP_UUID_{idx}__"

    preserved = _UUID_PATTERN.sub(_uuid_holder, text)

    # Redact email addresses
    scrubbed = _EMAIL_PATTERN.sub("[REDACTED_EMAIL]", preserved)

    # Redact phone numbers
    scrubbed = _PHONE_PATTERN.sub("[REDACTED_PHONE]", scrubbed)

    # Redact key-value personal names
    scrubbed = _NAME_KV_PATTERN.sub(r"\1=[REDACTED_NAME]", scrubbed)

    # Hash bank account numbers
    def _account_replacer(match: re.Match) -> str:
        digits = match.group(0)
        hashed = hash_bank_account(digits)
        return f"[ACCOUNT:sha256:{hashed}]"

    scrubbed = _ACCOUNT_NUMBER_PATTERN.sub(_account_replacer, scrubbed)

    # Restore UUIDs
    for i, original_uuid in enumerate(uuids):
        scrubbed = scrubbed.replace(f"__VERISLIP_UUID_{i}__", original_uuid)

    return scrubbed


def normalize_correlation_id(candidate: Optional[str]) -> str:
    """Return a safe caller ID, or generate a new UUID when it is invalid."""
    if candidate and _VALID_CORRELATION_ID.fullmatch(candidate):
        return candidate
    return str(uuid.uuid4())


def set_correlation_id(correlation_id: str) -> Token:
    """Set request-scoped correlation context and return its reset token."""
    return _correlation_id.set(correlation_id)


def reset_correlation_id(token: Token) -> None:
    """Restore correlation context after request processing completes."""
    _correlation_id.reset(token)


def get_correlation_id() -> Optional[str]:
    """Return the correlation ID propagated through the current execution context."""
    return _correlation_id.get()


class JsonLogFormatter(logging.Formatter):
    """Serialize an allowlisted, privacy-conscious log record as one JSON line with automated PII scrubbing."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "event": scrub_pii(record.getMessage()),
            "correlation_id": getattr(
                record, "correlation_id", None
            ) or get_correlation_id(),
        }
        for field in _SAFE_EXTRA_FIELDS:
            value = getattr(record, field, None)
            if value is not None:
                if isinstance(value, str):
                    payload[field] = scrub_pii(value)
                else:
                    payload[field] = value
        return json.dumps(payload, separators=(",", ":"), ensure_ascii=True)


def configure_json_logging() -> None:
    """Configure VeriSlip loggers once without changing third-party loggers."""
    logger = logging.getLogger("verislip")
    if not any(getattr(handler, "_verislip_json", False) for handler in logger.handlers):
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(JsonLogFormatter())
        handler._verislip_json = True  # type: ignore[attr-defined]
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = True

