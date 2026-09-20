const assert = require("node:assert/strict");
const test = require("node:test");

const VoiceAudit = require("../../web/js/voice_audit.js");

test("parses supported hands-free command syntax", () => {
  const result = VoiceAudit.parseCommand("Verify ComBank 15,000 reference 4821");
  assert.deepEqual(result, {
    ok: true,
    bankCode: "COMBANK",
    amount: 15000,
    reference: "4821",
    transcript: "Verify ComBank 15,000 reference 4821"
  });
});

test("rejects malformed commands with actionable errors", () => {
  assert.equal(VoiceAudit.parseCommand("").ok, false);
  assert.match(VoiceAudit.parseCommand("scan ComBank").error, /begin/);
  assert.match(VoiceAudit.parseCommand("Verify ComBank reference 4821").error, /amount/);
  assert.match(VoiceAudit.parseCommand("Verify 15000 reference 4821").error, /bank/);
});

test("supports manual fallback and voice transcript through one parser", () => {
  const commands = [];
  const controller = VoiceAudit.install({ window: {}, onCommand: command => commands.push(command) });
  controller.handleTranscript("Verify BOC 2,500 ref ABC-123");
  assert.equal(commands.length, 1);
  assert.equal(commands[0].bankCode, "BOC");
  assert.equal(commands[0].reference, "ABC-123");
});

test("voice recognition starts once and cleans up", () => {
  let starts = 0;
  let aborts = 0;
  class Recognition {
    start() { starts += 1; this.onstart(); }
    stop() { this.onend(); }
    abort() { aborts += 1; }
  }
  const controller = VoiceAudit.install({ window: { SpeechRecognition: Recognition } });
  controller.start();
  controller.start();
  controller.cleanup();
  assert.equal(starts, 1);
  assert.equal(aborts, 1);
});

test("maps verdicts to safe spoken feedback", () => {
  assert.deepEqual(VoiceAudit.verdictFeedback("AUTHENTIC"), { text: "Slip verified authentic", tone: "success" });
  assert.deepEqual(VoiceAudit.verdictFeedback("HIGH_RISK_TAMPERED"), { text: "Warning: Tampering detected", tone: "warning" });
});
