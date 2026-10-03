"""Versioned, bounded Groth16 verification for privacy-preserving slip audits.

Only proofs and public signals cross this boundary. Private witness values and
receipt bytes must never be passed to this verifier or written to logs.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import time
from typing import Any, Mapping, Sequence


PROOF_VERSION = "slip-audit-v1"
PUBLIC_SIGNAL_COUNT = 10
BN254_SCALAR_FIELD = 21888242871839275222246405745257275088548364400416034343698204186575808495617


class ZKVerificationError(Exception):
    """Safe, non-sensitive proof verification failure."""


class ZKConfigurationError(ZKVerificationError):
    """The selected proof version is not provisioned."""


def _json_size(value: Any) -> int:
    return len(json.dumps(value, separators=(",", ":")).encode("utf-8"))


def _validate_public_signals(signals: Sequence[Any]) -> list[str]:
    if not isinstance(signals, list) or len(signals) != PUBLIC_SIGNAL_COUNT:
        raise ZKVerificationError("Invalid public signals.")
    normalized: list[str] = []
    for value in signals:
        if not isinstance(value, (str, int)) or isinstance(value, bool):
            raise ZKVerificationError("Invalid public signals.")
        text = str(value)
        if not text.isdigit() or len(text) > 78:
            raise ZKVerificationError("Invalid public signals.")
        number = int(text)
        if number >= BN254_SCALAR_FIELD:
            raise ZKVerificationError("Invalid public signals.")
        normalized.append(str(number))
    return normalized


def _validate_proof(proof: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(proof, dict) or _json_size(proof) > 16_384:
        raise ZKVerificationError("Invalid proof payload.")
    if set(proof) != {"pi_a", "pi_b", "pi_c", "protocol", "curve"}:
        raise ZKVerificationError("Invalid proof payload.")
    if proof.get("protocol") != "groth16" or proof.get("curve") != "bn128":
        raise ZKVerificationError("Unsupported proof parameters.")
    # snarkjs performs point validation; this walk bounds and constrains JSON types.

    def check(value: Any, depth: int = 0) -> None:
        if depth > 3:
            raise ZKVerificationError("Invalid proof payload.")
        if isinstance(value, list):
            if len(value) > 4:
                raise ZKVerificationError("Invalid proof payload.")
            for item in value:
                check(item, depth + 1)
        elif isinstance(value, str):
            if not value.isdigit() or len(value) > 78:
                raise ZKVerificationError("Invalid proof payload.")
        else:
            raise ZKVerificationError("Invalid proof payload.")
    for key in ("pi_a", "pi_b", "pi_c"):
        check(proof[key])
    return dict(proof)


class Groth16Verifier:
    """Invoke the pinned local snarkjs verifier with strict resource boundaries."""

    def __init__(self, artifact_root: Path | None = None, timeout_seconds: float = 5.0):
        configured = artifact_root or Path(
            os.getenv("VERISLIP_ZK_ARTIFACT_ROOT", "circuits/artifacts")
        )
        self.artifact_root = configured.resolve()
        self.timeout_seconds = timeout_seconds
        self.node = os.getenv("VERISLIP_NODE_BINARY", "node")
        self.script = Path(__file__).resolve().parents[2] / "crypto" / "node" / "verify.mjs"

    def verify(self, version: str, proof: Mapping[str, Any], public_signals: Sequence[Any]) -> bool:
        if version != PROOF_VERSION:
            raise ZKVerificationError("Unsupported proof version.")
        clean_proof = _validate_proof(proof)
        clean_signals = _validate_public_signals(public_signals)
        version_dir = self.artifact_root / version
        verification_key = version_dir / "verification_key.json"
        if not verification_key.is_file():
            raise ZKConfigurationError("Proof verification is not configured.")
        if verification_key.stat().st_size > 1_000_000:
            raise ZKConfigurationError("Proof verification is not configured.")
        with tempfile.TemporaryDirectory(prefix="verislip-zk-") as temporary:
            directory = Path(temporary)
            proof_path = directory / "proof.json"
            signals_path = directory / "public.json"
            proof_path.write_text(json.dumps(clean_proof), encoding="utf-8")
            signals_path.write_text(json.dumps(clean_signals), encoding="utf-8")
            try:
                result = subprocess.run(
                    [self.node, str(self.script), str(verification_key), str(proof_path), str(signals_path)],
                    capture_output=True,
                    text=True,
                    timeout=self.timeout_seconds,
                    check=False,
                    shell=False,
                )
            except (OSError, subprocess.TimeoutExpired) as exc:
                raise ZKVerificationError("Proof verification is unavailable.") from exc
        if len(result.stdout) > 1024 or result.returncode != 0:
            raise ZKVerificationError("Proof verification failed.")
        try:
            response = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise ZKVerificationError("Proof verification failed.") from exc
        return response == {"valid": True}


class InMemoryReplayGuard:
    """Thread-safe, bounded replay guard for one-process deployments."""

    def __init__(self, ttl_seconds: int = 300, max_entries: int = 10_000):
        self.ttl_seconds = ttl_seconds
        self.max_entries = max_entries
        self._seen: dict[str, float] = {}
        self._lock = threading.Lock()

    def consume(self, version: str, public_signals: Sequence[str], now: float | None = None) -> bool:
        current = time.time() if now is None else now
        key = version + ":" + ":".join(public_signals)
        with self._lock:
            self._seen = {k: expiry for k, expiry in self._seen.items() if expiry > current}
            if key in self._seen:
                return False
            if len(self._seen) >= self.max_entries:
                oldest = min(self._seen, key=self._seen.get)  # type: ignore[arg-type]
                self._seen.pop(oldest, None)
            self._seen[key] = current + self.ttl_seconds
            return True
