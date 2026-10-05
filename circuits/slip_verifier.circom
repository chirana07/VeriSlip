pragma circom 2.1.6;

include "../node_modules/circomlib/circuits/bitify.circom";
include "../node_modules/circomlib/circuits/comparators.circom";
include "../node_modules/circomlib/circuits/poseidon.circom";
include "../node_modules/circomlib/circuits/sha256/sha256.circom";

// slip-audit-v1 proves an amount threshold and merchant binding while keeping
// the amount, merchant identifier, and raw-document SHA-256 digest private.
// slipCommitment is SHA256(rawDocumentSha256Bytes), split into four 64-bit limbs.
template SlipVerifierV1() {
    signal input documentDigestBits[256];
    signal input amountCents;
    signal input merchantIdentifier;
    signal input customerAccountHash;
    signal input senderIdentityHash;

    signal input slipCommitment[4];
    signal input minimumAmountCents;
    signal input merchantCommitment;
    signal input identityBinding;
    signal input verificationTimestamp;
    signal input auditNonce;
    signal input contextCommitment;

    component amountRange = Num2Bits(64);
    amountRange.in <== amountCents;
    component minimumRange = Num2Bits(64);
    minimumRange.in <== minimumAmountCents;
    component belowMinimum = LessThan(64);
    belowMinimum.in[0] <== amountCents;
    belowMinimum.in[1] <== minimumAmountCents;
    belowMinimum.out === 0;

    component merchantRange = Num2Bits(248);
    merchantRange.in <== merchantIdentifier;
    component merchantHash = Poseidon(1);
    merchantHash.inputs[0] <== merchantIdentifier;
    merchantHash.out === merchantCommitment;

    component customerRange = Num2Bits(248);
    customerRange.in <== customerAccountHash;
    component senderRange = Num2Bits(248);
    senderRange.in <== senderIdentityHash;
    component identityHash = Poseidon(2);
    identityHash.inputs[0] <== customerAccountHash;
    identityHash.inputs[1] <== senderIdentityHash;
    identityHash.out === identityBinding;

    component digestHash = Sha256(256);
    component digestBit[256];
    for (var i = 0; i < 256; i++) {
        digestBit[i] = Num2Bits(1);
        digestBit[i].in <== documentDigestBits[i];
        digestHash.in[i] <== documentDigestBits[i];
    }
    component limb[4];
    for (var part = 0; part < 4; part++) {
        limb[part] = Bits2Num(64);
        for (var bit = 0; bit < 64; bit++) {
            // SHA output is big-endian; Bits2Num consumes little-endian bits.
            limb[part].in[bit] <== digestHash.out[part * 64 + 63 - bit];
        }
        limb[part].out === slipCommitment[part];
    }

    component timestampRange = Num2Bits(64);
    timestampRange.in <== verificationTimestamp;
    component nonceRange = Num2Bits(128);
    nonceRange.in <== auditNonce;

    component contextHash = Poseidon(10);
    for (var j = 0; j < 4; j++) contextHash.inputs[j] <== slipCommitment[j];
    contextHash.inputs[4] <== minimumAmountCents;
    contextHash.inputs[5] <== merchantCommitment;
    contextHash.inputs[6] <== identityBinding;
    contextHash.inputs[7] <== verificationTimestamp;
    contextHash.inputs[8] <== auditNonce;
    contextHash.inputs[9] <== 1;
    contextHash.out === contextCommitment;
}

component main {public [slipCommitment, minimumAmountCents, merchantCommitment, identityBinding, verificationTimestamp, auditNonce, contextCommitment]} = SlipVerifierV1();
