import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import test from "node:test";
import { buildPoseidon } from "circomlibjs";

const artifacts = resolve("circuits/artifacts/slip-audit-v1");
const wasm = join(artifacts, "slip_verifier.wasm");
const zkey = join(artifacts, "proving_key.zkey");
const verificationKey = join(artifacts, "verification_key.json");
const poseidon = await buildPoseidon();
const field = poseidon.F;
const poseidonValue = (values) => field.toObject(poseidon(values)).toString();

function witness(amount = 12500n, minimum = 10000n) {
  const digest = createHash("sha256").update("synthetic-receipt-fixture").digest();
  const commitment = createHash("sha256").update(digest).digest();
  const slipCommitment = Array.from({ length: 4 }, (_, i) => commitment.readBigUInt64BE(i * 8).toString());
  const merchantIdentifier = 123456789n;
  const customerAccountHash = 987654321n;
  const senderIdentityHash = 192837465n;
  const merchantCommitment = poseidonValue([merchantIdentifier]);
  const identityBinding = poseidonValue([customerAccountHash, senderIdentityHash]);
  const verificationTimestamp = 2000000000n;
  const auditNonce = 112233445566n;
  const contextCommitment = poseidonValue([
    ...slipCommitment, minimum, merchantCommitment, identityBinding,
    verificationTimestamp, auditNonce, 1n,
  ]);
  const documentDigestBits = Array.from(digest).flatMap((byte) =>
    Array.from({ length: 8 }, (_, bit) => ((byte >> (7 - bit)) & 1).toString()),
  );
  return {
    documentDigestBits, amountCents: amount.toString(),
    merchantIdentifier: merchantIdentifier.toString(),
    customerAccountHash: customerAccountHash.toString(),
    senderIdentityHash: senderIdentityHash.toString(), slipCommitment,
    minimumAmountCents: minimum.toString(), merchantCommitment, identityBinding,
    verificationTimestamp: verificationTimestamp.toString(),
    auditNonce: auditNonce.toString(), contextCommitment,
  };
}

test("real Groth16 proof verifies and altered public signals fail", async () => {
  const directory = await mkdtemp(join(tmpdir(), "verislip-zk-test-"));
  const input = join(directory, "input.json");
  const proof = join(directory, "proof.json");
  const signals = join(directory, "signals.json");
  await writeFile(input, JSON.stringify(witness()));
  const prove = spawnSync(process.execPath, ["crypto/node/prove.mjs", wasm, zkey, input, proof, signals]);
  assert.equal(prove.status, 0);
  const valid = spawnSync(process.execPath, ["crypto/node/verify.mjs", verificationKey, proof, signals]);
  assert.deepEqual(JSON.parse(valid.stdout.toString()), { valid: true });
  const publicSignals = JSON.parse(await readFile(signals, "utf8"));
  for (const index of [0, 4, 5]) {
    const altered = [...publicSignals];
    altered[index] = (BigInt(altered[index]) + 1n).toString();
    await writeFile(signals, JSON.stringify(altered));
    const invalid = spawnSync(process.execPath, ["crypto/node/verify.mjs", verificationKey, proof, signals]);
    assert.deepEqual(JSON.parse(invalid.stdout.toString()), { valid: false });
  }
  const tamperedProof = JSON.parse(await readFile(proof, "utf8"));
  tamperedProof.pi_a[0] = (BigInt(tamperedProof.pi_a[0]) + 1n).toString();
  await writeFile(proof, JSON.stringify(tamperedProof));
  await writeFile(signals, JSON.stringify(publicSignals));
  const tampered = spawnSync(process.execPath, ["crypto/node/verify.mjs", verificationKey, proof, signals]);
  assert.notDeepEqual(tampered.stdout.toString(), '{"valid":true}');
  await rm(directory, { recursive: true, force: true });
});

test("amount below the public minimum cannot produce a proof", async () => {
  const directory = await mkdtemp(join(tmpdir(), "verislip-zk-test-"));
  const input = join(directory, "input.json");
  await writeFile(input, JSON.stringify(witness(9999n)));
  const result = spawnSync(process.execPath, ["crypto/node/prove.mjs", wasm, zkey, input, join(directory, "proof.json"), join(directory, "signals.json")]);
  assert.notEqual(result.status, 0);
  assert.equal(result.stderr.toString().endsWith("proof generation failed\n"), true);
  await rm(directory, { recursive: true, force: true });
});
