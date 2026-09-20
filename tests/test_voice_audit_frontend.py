"""Static integration checks for the voice-guided forensic cockpit."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_voice_controls_are_accessible_and_documented():
    html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
    assert 'id="btn-voice-listen" aria-pressed="false"' in html
    assert 'id="voice-command-input"' in html
    assert 'id="voice-status" class="voice-status" role="status" aria-live="polite"' in html
    assert "Verify [bank] [amount] reference [number]" in html
    assert '/static/js/voice_audit.js' in html


def test_app_reuses_the_existing_scan_path_and_announces_results():
    javascript = (ROOT / "web" / "js" / "app.js").read_text(encoding="utf-8")
    assert "function applyVoiceCommand(command)" in javascript
    assert "runScan();" in javascript
    assert "voiceAudit.announce(results.verdict);" in javascript
    assert 'window.addEventListener("pagehide", voiceAudit.cleanup' in javascript
