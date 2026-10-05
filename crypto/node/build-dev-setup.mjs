import { randomBytes } from "node:crypto";
import { cp, mkdir, rm } from "node:fs/promises";
import { spawnSync } from "node:child_process";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import process from "node:process";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
const build = resolve(root, "circuits/build");
const artifacts = resolve(root, "circuits/artifacts/slip-audit-v1");
const snarkjs = resolve(root, "node_modules/snarkjs/build/cli.cjs");
const circom = process.env.CIRCOM_BIN || "circom";

function run(command, args) {
  const result = spawnSync(command, args, { cwd: root, encoding: "utf8" });
  if (result.status !== 0) {
    process.stderr.write(result.stderr || "ZK setup command failed.\n");
    process.exit(result.status || 1);
  }
}

await rm(build, { recursive: true, force: true });
await rm(artifacts, { recursive: true, force: true });
await mkdir(build, { recursive: true });
await mkdir(artifacts, { recursive: true });
run(circom, ["circuits/slip_verifier.circom", "--r1cs", "--wasm", "--sym", "-o", build]);
run(process.execPath, [snarkjs, "powersoftau", "new", "bn128", "16", `${build}/pot16_0000.ptau`]);
run(process.execPath, [snarkjs, "powersoftau", "contribute", `${build}/pot16_0000.ptau`, `${build}/pot16_0001.ptau`, "--name=VeriSlip ephemeral development setup", `-e=${randomBytes(32).toString("hex")}`]);
run(process.execPath, [snarkjs, "powersoftau", "prepare", "phase2", `${build}/pot16_0001.ptau`, `${build}/pot16_final.ptau`]);
run(process.execPath, [snarkjs, "groth16", "setup", `${build}/slip_verifier.r1cs`, `${build}/pot16_final.ptau`, `${build}/slip_verifier_0000.zkey`]);
run(process.execPath, [snarkjs, "zkey", "contribute", `${build}/slip_verifier_0000.zkey`, `${artifacts}/proving_key.zkey`, "--name=VeriSlip ephemeral development setup", `-e=${randomBytes(32).toString("hex")}`]);
run(process.execPath, [snarkjs, "zkey", "export", "verificationkey", `${artifacts}/proving_key.zkey`, `${artifacts}/verification_key.json`]);
await cp(`${build}/slip_verifier_js/slip_verifier.wasm`, `${artifacts}/slip_verifier.wasm`);
process.stdout.write(`Development-only artifacts created in ${artifacts}\n`);
