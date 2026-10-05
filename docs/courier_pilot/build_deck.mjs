import fs from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { Presentation, PresentationFile } from "@oai/artifact-tool";

const workspaceDir = process.cwd();
const { SKILL_DIR, TMP_DIR, FINAL_PPTX, RUNTIME_PYTHON } = process.env;
if (![SKILL_DIR, TMP_DIR, FINAL_PPTX, RUNTIME_PYTHON].every((value) => path.isAbsolute(value ?? ""))) {
  throw new Error("SKILL_DIR, TMP_DIR, FINAL_PPTX, and RUNTIME_PYTHON must be absolute");
}
const utils = await import(pathToFileURL(path.join(SKILL_DIR, "container_tools/artifact_tool_utils.mjs")).href);
const family = utils.resolvePresentationFont();
const deck = Presentation.create({ slideSize: { width: 1280, height: 720 } });
const navy = "#102A43";
const blue = "#1F6FEB";
const ink = "#243B53";
const muted = "#526D82";
const pale = "#F1F6FA";

function textbox(slide, text, left, top, width, height, options = {}) {
  const box = slide.shapes.add({
    geometry: "textbox",
    position: { left, top, width, height },
    fill: options.fill ?? "none",
    line: { fill: "none", width: 0 },
  });
  box.text = text;
  box.text.style = {
    typeface: family,
    fontSize: options.size ?? 22,
    bold: options.bold ?? false,
    color: options.color ?? ink,
    autoFit: "shrinkText",
    verticalAlignment: options.verticalAlignment ?? "top",
  };
  return box;
}

function baseSlide(title, kicker) {
  const slide = deck.slides.add();
  slide.background.fill = "#FFFFFF";
  textbox(slide, kicker, 70, 40, 1140, 28, { size: 14, bold: true, color: blue });
  textbox(slide, title, 70, 72, 1140, 72, { size: 34, bold: true, color: navy });
  textbox(slide, "VeriSlip courier pilot discussion draft", 70, 674, 900, 20, { size: 11, color: muted });
  return slide;
}

let slide = deck.slides.add();
slide.background.fill = navy;
textbox(slide, "VeriSlip courier payment-proof screening", 80, 150, 1040, 150, { size: 48, bold: true, color: "#FFFFFF" });
textbox(slide, "Pilot proposal for Sri Lankan courier operators", 80, 315, 900, 48, { size: 25, color: "#D9EAF7" });
textbox(slide, "Discussion draft. No partnership, deployment, pricing, or measured ROI is implied", 80, 560, 1080, 60, { size: 17, color: "#B8D4E8" });

slide = baseSlide("The handover decision", "OPERATING CONTEXT");
textbox(slide, "A rider may receive a bank-transfer screenshot while waiting at the delivery point. The operator needs a consistent instruction without treating an image score as proof that funds settled.", 70, 170, 1120, 110, { size: 28, color: navy });
textbox(slide, "VeriSlip screens the proof and returns a compact rider action. Bank-app confirmation and cashier escalation remain authoritative.", 70, 340, 1020, 100, { size: 23, bold: true, color: blue, fill: pale });
textbox(slide, "Pilot question: can the screening step improve intervention quality without creating unsafe handovers or unacceptable operational delay?", 70, 500, 1120, 70, { size: 21, color: ink });

slide = baseSlide("Current courier API", "IMPLEMENTED CAPABILITY");
textbox(slide, "POST /api/v1/courier/verify", 70, 165, 540, 46, { size: 27, bold: true, color: blue });
textbox(slide, "Request\nwaybill_id\nexpected_cod_amount\nslip_base64 (JPEG or PNG)\ntarget_bank (optional)", 70, 235, 470, 270, { size: 22, color: ink });
textbox(slide, "Response\ncan_handover_package\nrider_action and cashier alert\nrisk level and percentage\namount comparison and timestamp", 650, 235, 500, 270, { size: 22, color: ink });
textbox(slide, "Shared image sanitization, API-key authentication, tiered rate limits, structured logs, and correlation IDs apply.", 70, 560, 1080, 54, { size: 18, bold: true, color: navy, fill: pale });

slide = baseSlide("Proposed request flow", "PILOT WORKFLOW");
textbox(slide, "1  Rider captures or selects the payment proof", 90, 180, 1080, 46, { size: 24, bold: true, color: navy });
textbox(slide, "2  Courier app submits the waybill, expected amount, and sanitized image payload", 90, 260, 1080, 62, { size: 24, bold: true, color: navy });
textbox(slide, "3  VeriSlip returns handover, block, or cashier escalation guidance", 90, 355, 1080, 46, { size: 24, bold: true, color: navy });
textbox(slide, "4  Operator policy and independent payment confirmation determine the final action", 90, 435, 1080, 62, { size: 24, bold: true, color: navy });
textbox(slide, "Start in shadow mode before assisted decisions.", 90, 560, 850, 45, { size: 22, bold: true, color: blue });

slide = baseSlide("Limited pilot design", "SCOPE AND CONTROL");
textbox(slide, "Operator-defined scope", 70, 170, 430, 42, { size: 25, bold: true, color: navy });
textbox(slide, "One depot or route group\nNamed rider cohort\nAgreed duration and transaction cap\nSupported banks and support hours", 70, 230, 470, 235, { size: 21 });
textbox(slide, "Safety gates", 650, 170, 430, 42, { size: 25, bold: true, color: navy });
textbox(slide, "Shadow review before assisted use\nCashier escalation for blocked or inconclusive cases\nOutage fallback to existing policy\nPre-agreed pause and termination rules", 650, 230, 500, 260, { size: 21 });
textbox(slide, "The operator approves thresholds before observing pilot outcomes.", 70, 555, 1080, 45, { size: 20, bold: true, color: blue, fill: pale });

slide = baseSlide("Measurement plan", "EVIDENCE");
textbox(slide, "Operational", 70, 175, 300, 38, { size: 24, bold: true, color: navy });
textbox(slide, "Eligible requests\nCompleted screens\nLatency and technical failures\nRider completion rate", 70, 230, 340, 190, { size: 21 });
textbox(slide, "Safety", 470, 175, 300, 38, { size: 24, bold: true, color: navy });
textbox(slide, "Escalation rate\nAmount mismatches\nConfirmed false positives\nConfirmed false negatives", 470, 230, 340, 190, { size: 21 });
textbox(slide, "Business", 870, 175, 300, 38, { size: 24, bold: true, color: navy });
textbox(slide, "Confirmed fraud attempts\nAverage affected order value\nIntervention effectiveness\nPilot and operating costs", 870, 230, 340, 190, { size: 21 });
textbox(slide, "Keep unconfirmed outcomes separate. Do not convert screening scores into claimed savings.", 70, 530, 1080, 60, { size: 21, bold: true, color: blue, fill: pale });

slide = baseSlide("Transparent ROI scenario", "OPERATOR-SUPPLIED ASSUMPTIONS");
textbox(slide, "Estimated avoided loss (LKR)", 70, 175, 520, 48, { size: 29, bold: true, color: navy });
textbox(slide, "eligible transactions\n× confirmed fraud-attempt rate\n× average fraudulent order value (LKR)\n× measured intervention effectiveness", 70, 250, 600, 240, { size: 27, color: blue });
textbox(slide, "Run low, expected, and high cases. Keep inputs visible. Subtract implementation and operating costs separately for net benefit.", 735, 235, 430, 220, { size: 23, color: ink, fill: pale });
textbox(slide, "No market rates, pricing, savings, or operator performance figures are asserted in this deck.", 70, 550, 1090, 48, { size: 19, bold: true, color: navy });

slide = baseSlide("Security and deployment boundary", "PRODUCTION READINESS");
textbox(slide, "Existing controls", 70, 170, 420, 42, { size: 25, bold: true, color: navy });
textbox(slide, "Content-based JPEG/PNG validation\nBounded image size and dimensions\nSanitized in-memory processing\nAPI keys, rate limits, request IDs\nSecret-safe structured logging", 70, 230, 500, 260, { size: 21 });
textbox(slide, "Operator decisions before production", 650, 170, 500, 42, { size: 25, bold: true, color: navy });
textbox(slide, "Data-controller roles and retention\nScoped keys and rotation\nMonitoring and incident ownership\nLoad and resilience testing\nReviewed service and data agreements", 650, 230, 520, 260, { size: 21 });
textbox(slide, "Raw receipts and credentials must never enter analytics, support tickets, or pilot reports.", 70, 555, 1080, 48, { size: 20, bold: true, color: blue, fill: pale });

slide = baseSlide("Pilot decision checklist", "NEXT DISCUSSION");
textbox(slide, "Use case and baseline data", 70, 175, 480, 40, { size: 24, bold: true, color: navy });
textbox(slide, "Confirm the payment flow, eligible orders, current handover policy, baseline volumes, and independently confirmed fraud outcomes.", 100, 230, 460, 145, { size: 21 });
textbox(slide, "Technical and operational owners", 650, 175, 500, 40, { size: 24, bold: true, color: navy });
textbox(slide, "Name API, security, cashier escalation, rider support, and incident owners. Agree availability and fallback procedures.", 670, 230, 470, 145, { size: 21 });
textbox(slide, "Approval gates", 70, 430, 360, 40, { size: 24, bold: true, color: navy });
textbox(slide, "Approve scope, measurable thresholds, retention, stop rules, and written commercial terms before launch.", 70, 485, 980, 90, { size: 22, color: blue, fill: pale });

for (const current of deck.slides.items) {
  current.speakerNotes.textFrame.setText("Source: VeriSlip repository implementation and courier pilot proposal. Any ROI values must come from operator-supplied, validated assumptions. No partnership or measured outcome is claimed.");
}

await fs.mkdir(TMP_DIR, { recursive: true });
await fs.mkdir(path.dirname(FINAL_PPTX), { recursive: true });
const staging = path.join(workspaceDir, ".deck-build");
await fs.mkdir(staging, { recursive: true });
const candidatePath = path.join(staging, "courier-pilot-candidate.pptx");
await (await PresentationFile.exportPptx(deck)).save(candidatePath);
const result = await utils.finalizePresentation({
  explicitTotalSlideCount: 9,
  requiredNativeTableOwnerSlides: [],
  requiredNativeChartOwnerSlides: [],
  workspaceDir,
  candidatePath,
  finalPath: FINAL_PPTX,
  pythonExecutable: RUNTIME_PYTHON,
  integrityValidatorPath: path.join(SKILL_DIR, "container_tools/inspect_presentation_package_integrity.py"),
  layoutValidatorPath: path.join(SKILL_DIR, "container_tools/inspect_presentation_layout_geometry.py"),
  layoutArgs: ["--expected-slide-size-emu", "12192000,6858000", "--validate-heading-fit"],
  fontPolicy: { basis: "design", families: [family] },
  verifyArtifactToolImport: true,
  receiptPath: path.join(staging, "courier-pilot.validation.json"),
});
console.log(result.finalPath);
