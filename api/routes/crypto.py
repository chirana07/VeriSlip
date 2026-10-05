"""Privacy-preserving audit proof verification API."""

from __future__ import annotations

import time
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from core.crypto.zk_verifier import (
    Groth16Verifier,
    InMemoryReplayGuard,
    PROOF_VERSION,
    ZKConfigurationError,
    ZKVerificationError,
    _validate_public_signals,
)

router = APIRouter(prefix="/api/v1/crypto", tags=["Cryptographic verification"])
verifier = Groth16Verifier()
replay_guard = InMemoryReplayGuard()


class ZKVerifyRequest(BaseModel):
    """Exportable snarkjs Groth16 proof envelope; contains no private witness."""

    version: str = Field(..., max_length=32)
    proof: Dict[str, Any]
    public_signals: List[Any] = Field(..., min_length=10, max_length=10)


@router.post("/zk-verify")
async def verify_zk_proof(request: ZKVerifyRequest):
    """Verify a versioned proof and consume its timestamp/nonce context once."""
    try:
        signals = _validate_public_signals(request.public_signals)
        timestamp = int(signals[7])
        if abs(int(time.time()) - timestamp) > 300:
            raise HTTPException(status_code=400, detail="Proof timestamp is outside the allowed window.")
        valid = await run_in_threadpool(
            verifier.verify, request.version, request.proof, signals
        )
        if not valid:
            raise HTTPException(status_code=422, detail="Proof is invalid.")
        if not replay_guard.consume(request.version, signals):
            raise HTTPException(status_code=409, detail="Proof context has already been used.")
        return {"valid": True, "version": PROOF_VERSION}
    except HTTPException:
        raise
    except ZKConfigurationError:
        raise HTTPException(status_code=503, detail="Proof verification is not configured.") from None
    except ZKVerificationError:
        raise HTTPException(status_code=400, detail="Proof request is invalid.") from None
