(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.VeriSlipVoiceAudit = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  const BANK_ALIASES = [
    [/\b(?:combank|commercial bank)\b/i, "COMBANK"],
    [/\bsampath(?: bank)?\b/i, "SAMPATH"],
    [/\b(?:boc|bank of ceylon)\b/i, "BOC"],
    [/\b(?:hnb|hatton national bank)\b/i, "HNB"],
    [/\bpeople'?s bank\b/i, "PEOPLES"],
    [/\bdfcc(?: bank)?\b/i, "DFCC"],
    [/\bseylan(?: bank)?\b/i, "SEYLAN"],
    [/\b(?:ntb|frimi|nations trust)\b/i, "NTB_FRIMI"]
  ];

  function parseCommand(rawCommand) {
    const command = String(rawCommand || "").trim();
    if (!command) return { ok: false, error: "Say or enter a verification command." };
    if (!/^verify\b/i.test(command)) {
      return { ok: false, error: "Commands must begin with “Verify”." };
    }

    const bankMatch = BANK_ALIASES.find(([pattern]) => pattern.test(command));
    const referenceMatch = command.match(/\b(?:reference|ref)\s+([a-z0-9-]{3,64})\b/i);
    const beforeReference = command.split(/\b(?:reference|ref)\b/i)[0];
    const amountCandidates = [...beforeReference.matchAll(/\b(?:lkr\s*)?([0-9][0-9,]*(?:\.\d{1,2})?)\b/gi)];
    const amountText = amountCandidates.length ? amountCandidates[amountCandidates.length - 1][1] : null;
    const amount = amountText ? Number(amountText.replaceAll(",", "")) : null;

    if (!bankMatch) return { ok: false, error: "Name a supported bank in the command." };
    if (!Number.isFinite(amount) || amount <= 0) {
      return { ok: false, error: "Include a positive transaction amount." };
    }
    if (!referenceMatch) return { ok: false, error: "Include “reference” followed by its number." };

    return {
      ok: true,
      bankCode: bankMatch[1],
      amount,
      reference: referenceMatch[1].toUpperCase(),
      transcript: command
    };
  }

  function verdictFeedback(verdict) {
    if (verdict === "AUTHENTIC") {
      return { text: "Slip verified authentic", tone: "success" };
    }
    return { text: "Warning: Tampering detected", tone: "warning" };
  }

  function install(options) {
    const win = options.window;
    const Recognition = win.SpeechRecognition || win.webkitSpeechRecognition;
    let recognition = null;
    let listening = false;

    function setListening(value) {
      listening = value;
      options.onListeningChange?.(value);
    }

    function handleTranscript(transcript) {
      const parsed = parseCommand(transcript);
      options.onStatus?.(parsed.ok ? `Heard: ${parsed.transcript}` : parsed.error, !parsed.ok);
      if (parsed.ok) options.onCommand(parsed);
      return parsed;
    }

    function start() {
      if (listening) return;
      if (!Recognition) {
        options.onStatus?.("Voice recognition is unavailable; use the command field.", true);
        return;
      }
      recognition = new Recognition();
      recognition.lang = options.language || "en-LK";
      recognition.interimResults = false;
      recognition.maxAlternatives = 1;
      recognition.onstart = () => setListening(true);
      recognition.onend = () => setListening(false);
      recognition.onerror = () => {
        setListening(false);
        options.onStatus?.("Voice recognition stopped. Use manual command entry if needed.", true);
      };
      recognition.onresult = event => handleTranscript(event.results[0][0].transcript);
      recognition.start();
    }

    function stop() {
      if (recognition && listening) recognition.stop();
    }

    function announce(verdict) {
      const feedback = verdictFeedback(verdict);
      if (win.speechSynthesis && win.SpeechSynthesisUtterance) {
        win.speechSynthesis.cancel();
        const utterance = new win.SpeechSynthesisUtterance(feedback.text);
        utterance.lang = options.language || "en-LK";
        win.speechSynthesis.speak(utterance);
      }
      try {
        const AudioContext = win.AudioContext || win.webkitAudioContext;
        if (AudioContext) {
          const context = new AudioContext();
          const oscillator = context.createOscillator();
          const gain = context.createGain();
          oscillator.frequency.value = feedback.tone === "success" ? 880 : 220;
          gain.gain.value = 0.04;
          oscillator.connect(gain);
          gain.connect(context.destination);
          oscillator.start();
          oscillator.stop(context.currentTime + 0.12);
          oscillator.onended = () => context.close();
        }
      } catch (_error) {
        // Speech remains available when browsers block programmatic audio.
      }
      return feedback;
    }

    return { start, stop, handleTranscript, announce, cleanup: () => recognition?.abort() };
  }

  return { install, parseCommand, verdictFeedback };
});
