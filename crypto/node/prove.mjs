import { readFile, writeFile } from "node:fs/promises";
import process from "node:process";
import * as snarkjs from "snarkjs";

if (process.argv.length !== 7) {
  process.stderr.write("usage: prove.mjs <wasm> <zkey> <input> <proof-out> <signals-out>\n");
  process.exit(2);
}

try {
  const input = JSON.parse(await readFile(process.argv[4], "utf8"));
  const { proof, publicSignals } = await snarkjs.groth16.fullProve(
    input, process.argv[2], process.argv[3],
  );
  await Promise.all([
    writeFile(process.argv[5], JSON.stringify(proof)),
    writeFile(process.argv[6], JSON.stringify(publicSignals)),
  ]);
  process.exit(0);
} catch {
  process.stderr.write("proof generation failed\n");
  process.exit(1);
}
