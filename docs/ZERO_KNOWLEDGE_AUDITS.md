# Zero-knowledge slip audit verification

Issue #120 adds an optional, versioned Groth16 verification boundary for B2B
audits. It does not change receipt forensics or any deep-learning model.

## Statement proved by `slip-audit-v1`

The prover privately supplies the payment amount (integer LKR cents), merchant
identifier, customer-account hash, sender-identity hash, and the 256 bits of the
raw receipt's SHA-256 digest. The proof establishes that:

- the private amount is at least the public minimum;
- `Poseidon(merchantIdentifier)` equals the public merchant commitment;
- the two private identity hashes equal their public combined Poseidon binding;
- `SHA256(rawDocumentSha256Bytes)` equals the four public 64-bit slip-commitment
  limbs; and
- the public timestamp and nonce are bound into a versioned context commitment.

The commitment boundary is deliberately precise: `slipCommitment` is SHA-256
of the 32-byte raw-document SHA-256 digest (double SHA-256), not SHA-256 of an
arbitrary-size image inside the circuit. The existing audit/Merkle digest remains
the single SHA-256 of the raw receipt. Do not interchange the two values.

The circuit proves consistency of supplied witness values; it cannot prove that
OCR extracted the correct amount or identity from a receipt. That requires a
separately trusted extraction/attestation process.

## Development setup and use

Install Node dependencies and the official Circom 2.2.3 compiler. In Windows
Command Prompt, point `CIRCOM_BIN` at the downloaded official executable:

```cmd
cd /d D:\Project\VeriSlip
.venv\Scripts\activate
npm ci
set CIRCOM_BIN=C:\tools\circom\circom-windows-amd64.exe
npm run zk:setup
set VERISLIP_ZK_ARTIFACT_ROOT=D:\Project\VeriSlip\circuits\artifacts
python -m uvicorn api.main:app --host 127.0.0.1 --port 8000
```

`npm run zk:setup` creates disposable local artifacts. Never use its single-party
ceremony in production. A production deployment must conduct or adopt a reviewed
multi-party ceremony, retain its transcript, protect the proving key, and deploy
the version-matched `verification_key.json` beneath
`%VERISLIP_ZK_ARTIFACT_ROOT%\slip-audit-v1\`.

POST an exportable snarkjs envelope to `/api/v1/crypto/zk-verify` with `version`,
`proof`, and the ten ordered `public_signals`. Normal API-key authentication,
rate limits, correlation IDs, and structured logging remain active. Private
witness data must never be sent to this endpoint.

## Threat model and limitations

- Strict JSON shapes, scalar bounds, proof/version selection, subprocess timeout,
  output caps, argument arrays, and temporary directories limit verifier abuse.
- A five-minute timestamp window and one-time context guard limit replay in one
  process. Production replicas require a shared atomic store (for example Redis)
  and an application-specific verifier/audience binding.
- Groth16 security depends on the ceremony, BN254 assumptions, pinned tooling,
  and correct circuit review. No implementation can promise absolute soundness.
- Proof generation is intentionally offline. The API receives neither receipts
  nor witness values and therefore cannot leak them through its logs.
- Generated `.wasm`, `.r1cs`, `.zkey`, and Powers-of-Tau files are not committed.
  Artifact distribution, integrity pinning, ceremony governance, and key rotation
  remain deployment responsibilities.
