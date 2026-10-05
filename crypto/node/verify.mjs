import { readFile } from "node:fs/promises";
import process from "node:process";
import * as snarkjs from "snarkjs";

if (process.argv.length !== 5) {
  process.stderr.write("usage: verify.mjs <verification-key> <proof> <public-signals>\n");
  process.exit(2);
}

try {
  const [verificationKey, proof, publicSignals] = await Promise.all(
    process.argv.slice(2).map(async (path) => JSON.parse(await readFile(path, "utf8"))),
  );
  const valid = await snarkjs.groth16.verify(verificationKey, publicSignals, proof);
  process.stdout.write(JSON.stringify({ valid }));
  process.exit(0);
} catch {
  process.stderr.write("proof verification failed\n");
  process.exit(1);
}
