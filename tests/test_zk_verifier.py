"""Security and API tests for issue #120's ZK verification boundary."""

import hashlib
import json
import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routes import crypto as crypto_route
from api.middleware.rate_limiter import ApiKeyRateLimitMiddleware, ApiKeyRegistry, InMemoryRateLimitStore
from api.middleware.request_tracing import RequestTracingMiddleware
from core.crypto.zk_verifier import (
    Groth16Verifier,
    InMemoryReplayGuard,
    ZKConfigurationError,
    ZKVerificationError,
)


def _proof():
    return {
        "pi_a": ["1", "2", "1"],
        "pi_b": [["1", "2"], ["3", "4"], ["1", "0"]],
        "pi_c": ["1", "2", "1"],
        "protocol": "groth16",
        "curve": "bn128",
    }


def _signals(timestamp=None):
    values = [1, 2, 3, 4, 100, 200, 300, timestamp or int(time.time()), 400, 500]
    return [str(value) for value in values]


def test_verifier_invokes_node_without_shell_and_accepts_valid_result(tmp_path, monkeypatch):
    version_dir = tmp_path / "slip-audit-v1"
    version_dir.mkdir()
    (version_dir / "verification_key.json").write_text("{}", encoding="utf-8")
    observed = {}

    def fake_run(command, **kwargs):
        observed.update(command=command, kwargs=kwargs)
        proof = json.loads(open(command[-2], encoding="utf-8").read())
        assert proof == _proof()
        return type("Result", (), {"stdout": '{"valid":true}', "returncode": 0})()

    monkeypatch.setattr("core.crypto.zk_verifier.subprocess.run", fake_run)
    assert Groth16Verifier(tmp_path).verify("slip-audit-v1", _proof(), _signals())
    assert observed["kwargs"]["shell"] is False
    assert observed["kwargs"]["timeout"] == 5.0


@pytest.mark.parametrize("signals", [[], ["1"] * 9, ["-1"] * 10, ["x"] * 10])
def test_malformed_public_signals_are_rejected_before_subprocess(tmp_path, signals):
    with pytest.raises(ZKVerificationError, match="Invalid public signals"):
        Groth16Verifier(tmp_path).verify("slip-audit-v1", _proof(), signals)


def test_unknown_version_and_missing_artifact_fail_closed(tmp_path):
    verifier = Groth16Verifier(tmp_path)
    with pytest.raises(ZKVerificationError, match="Unsupported proof version"):
        verifier.verify("future", _proof(), _signals())
    with pytest.raises(ZKConfigurationError, match="not configured"):
        verifier.verify("slip-audit-v1", _proof(), _signals())


def test_replay_guard_is_atomic_and_expires():
    guard = InMemoryReplayGuard(ttl_seconds=10)
    assert guard.consume("slip-audit-v1", _signals(), now=100)
    assert not guard.consume("slip-audit-v1", _signals(), now=101)
    assert guard.consume("slip-audit-v1", _signals(), now=111)


def test_api_valid_invalid_replay_and_timestamp(monkeypatch):
    app = FastAPI()
    app.include_router(crypto_route.router)
    crypto_route.replay_guard = InMemoryReplayGuard()
    monkeypatch.setattr(crypto_route.verifier, "verify", lambda *args: True)
    client = TestClient(app)
    body = {"version": "slip-audit-v1", "proof": _proof(), "public_signals": _signals()}
    assert client.post("/api/v1/crypto/zk-verify", json=body).status_code == 200
    assert client.post("/api/v1/crypto/zk-verify", json=body).status_code == 409

    stale = {**body, "public_signals": _signals(1)}
    assert client.post("/api/v1/crypto/zk-verify", json=stale).status_code == 400

    crypto_route.replay_guard = InMemoryReplayGuard()
    monkeypatch.setattr(crypto_route.verifier, "verify", lambda *args: False)
    response = client.post("/api/v1/crypto/zk-verify", json=body)
    assert response.status_code == 422
    assert response.json() == {"detail": "Proof is invalid."}


def test_api_does_not_accept_private_witness_fields(monkeypatch):
    app = FastAPI()
    app.include_router(crypto_route.router)
    monkeypatch.setattr(crypto_route.verifier, "verify", lambda *args: True)
    body = {
        "version": "slip-audit-v1",
        "proof": _proof(),
        "public_signals": _signals(),
        "raw_slip": "private receipt bytes",
        "amount_cents": 999,
    }
    response = TestClient(app).post("/api/v1/crypto/zk-verify", json=body)
    assert response.status_code == 200
    assert "private receipt bytes" not in response.text


def test_crypto_endpoint_remains_api_key_protected(monkeypatch):
    app = FastAPI()
    app.include_router(crypto_route.router)
    app.add_middleware(
        ApiKeyRateLimitMiddleware,
        registry=ApiKeyRegistry({hashlib.sha256(b"configured-key").hexdigest(): "free"}),
        store=InMemoryRateLimitStore(),
    )
    app.add_middleware(RequestTracingMiddleware)

    response = TestClient(app).post(
        "/api/v1/crypto/zk-verify",
        json={"version": "slip-audit-v1", "proof": _proof(), "public_signals": _signals()},
    )
    assert response.status_code == 401
    assert response.headers["X-Request-ID"]
    assert "proof" not in response.text.lower()

    monkeypatch.setattr(crypto_route.verifier, "verify", lambda *args: True)
    crypto_route.replay_guard = InMemoryReplayGuard()
    accepted = TestClient(app).post(
        "/api/v1/crypto/zk-verify",
        headers={"X-API-Key": "configured-key"},
        json={"version": "slip-audit-v1", "proof": _proof(), "public_signals": _signals()},
    )
    assert accepted.status_code == 200
    assert accepted.headers["X-RateLimit-Remaining"] == "9"


def test_api_hides_internal_crypto_errors_and_private_values(monkeypatch, caplog):
    secret = "private-account-fixture"
    app = FastAPI()
    app.include_router(crypto_route.router)

    def fail(*args):
        raise ZKVerificationError(f"internal path /srv/keys/{secret}")

    monkeypatch.setattr(crypto_route.verifier, "verify", fail)
    response = TestClient(app).post(
        "/api/v1/crypto/zk-verify",
        json={"version": "slip-audit-v1", "proof": _proof(), "public_signals": _signals()},
    )
    assert response.status_code == 400
    assert response.json() == {"detail": "Proof request is invalid."}
    assert secret not in response.text
    assert secret not in caplog.text
