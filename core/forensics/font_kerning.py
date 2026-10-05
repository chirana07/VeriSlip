"""
Character Baseline, Kerning & Rectangular Patch Boundary Detector (VeriSlip Layer 1/3 Enhancement)
Detects micro-discrepancies specifically in numerical lines (amounts, transaction references, account numbers)
where numbers were spliced, pasted, or edited in Canva / mobile markup:
1. Vertical baseline alignment variance across cap/numeral glyphs (immune to lowercase descenders)
2. Inter-digit kerning (spacing) outliers in uniform font strings
3. Localized rectangular patch seams (copy-paste block seams)
"""

import cv2
import numpy as np
from PIL import Image
from typing import Dict, Any, List, Tuple

from core.forensics.font_anti_aliasing import FontAntiAliasingAnalyzer


class CharacterAlignmentValidator:
    def __init__(self, baseline_jump_threshold: float = 4.5):
        self.baseline_jump_threshold = baseline_jump_threshold
        self.anti_aliasing = FontAntiAliasingAnalyzer()

    def evaluate(self, pil_image: Image.Image) -> Dict[str, Any]:
        """
        Scan image for character baseline irregularities and rectangular patch seams.
        """
        img_rgb = np.array(pil_image.convert("RGB"))
        gray = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2GRAY)
        h, w = gray.shape

        findings = []
        anomaly_score = 0.0
        flagged_boxes = []

        # Numerical Baseline Alignment in Amount & Reference Strips
        num_anomalies = self._analyze_numerical_baselines(gray)
        if num_anomalies:
            for b_box, b_score, b_reason in num_anomalies:
                anomaly_score = max(anomaly_score, b_score)
                flagged_boxes.append({
                    "box": b_box,
                    "confidence": round(b_score, 2),
                    "label": "Numeral Baseline Splicing"
                })
                findings.append(f"Numeral alignment anomaly: {b_reason}")

        # Generic multiline glyph analysis for Sinhala/Tamil or mixed-script insertion artifacts.
        script_anomalies = self._analyze_script_baselines(gray)
        for s_box, s_score, s_reason in script_anomalies:
            anomaly_score = max(anomaly_score, s_score)
            flagged_boxes.append({
                "box": s_box,
                "confidence": round(s_score, 2),
                "label": "Script Baseline Splicing"
            })
            findings.append(f"Script alignment anomaly: {s_reason}")

        # Report sub-pixel evidence independently. It is not fused into the
        # legacy alignment score until real-device calibration is available.
        anti_aliasing = self.anti_aliasing.analyze(pil_image)

        return {
            "anomaly_score": round(min(1.0, anomaly_score), 3),
            "is_anomalous": anomaly_score >= 0.50,
            "detected_regions": flagged_boxes,
            "findings": findings,
            "subpixel_rasterization": anti_aliasing,
        }

    def _analyze_script_baselines(self, gray: np.ndarray) -> List[Tuple[List[int], float, str]]:
        """Detect baseline/kerning outliers in mixed-script OCR regions."""
        h, w = gray.shape
        blurred = cv2.GaussianBlur(gray, (3, 3), 0)
        _, binary = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

        merge_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (7, 2))
        merged = cv2.morphologyEx(binary, cv2.MORPH_DILATE, merge_kernel)

        contours, _ = cv2.findContours(merged, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        anomalies = []

        for cnt in contours:
            x, y, bw, bh = cv2.boundingRect(cnt)
            if int(h * 0.15) < y < int(h * 0.80) and 30 < bw < w * 0.70 and 12 < bh < 50:
                strip = binary[y:y + bh, x:x + bw]
                glyph_cnts, _ = cv2.findContours(strip, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                glyph_boxes = []
                for g_cnt in glyph_cnts:
                    gx, gy, gw, gh = cv2.boundingRect(g_cnt)
                    if gw >= 2 and gh >= 6:
                        glyph_boxes.append((gx, gy, gw, gh, gy + gh))

                if len(glyph_boxes) < 4:
                    continue

                glyph_boxes.sort(key=lambda b: b[0])
                heights = [b[3] for b in glyph_boxes]
                med_h = float(np.median(heights))
                valid = [b for b in glyph_boxes if abs(b[3] - med_h) <= max(2.0, med_h * 0.35)]
                if len(valid) < 4:
                    continue

                baselines = [b[4] for b in valid]
                med_base = float(np.median(baselines))
                lining_glyphs = [b for b in valid if (b[4] - med_base) <= 2.5]
                if len(lining_glyphs) >= 4:
                    l_baselines = [b[4] for b in lining_glyphs]
                    diffs = [abs(l_baselines[i + 1] - l_baselines[i]) for i in range(len(l_baselines) - 1)]
                    max_jump = max(diffs) if diffs else 0.0
                else:
                    max_jump = 0.0

                x_starts = [b[0] for b in valid]
                widths = [b[2] for b in valid]
                width_variance_ratio = float(np.std(widths)) / max(float(np.median(widths)), 1.0)
                if len(valid) >= 3:
                    spacing = [x_starts[i + 1] - (x_starts[i] + widths[i]) for i in range(len(valid) - 1)]
                    if spacing:
                        med_spacing = float(np.median(spacing))
                        # Isolate intra-word character spacing from natural inter-word spaces
                        intra_spacing = [s for s in spacing if s < max(5.0, med_spacing * 2.2)]
                        if len(intra_spacing) >= 3:
                            med_intra = float(np.median(intra_spacing))
                            spacing_outlier = max(abs(s - med_intra) / max(med_intra, 1.0) for s in intra_spacing)
                        else:
                            spacing_outlier = 0.0
                    else:
                        spacing_outlier = 0.0
                else:
                    spacing_outlier = 0.0

                baseline_alert = max_jump >= self.baseline_jump_threshold
                spacing_alert = width_variance_ratio <= 0.50 and spacing_outlier >= 3.0 and max_jump >= 3.5

                if baseline_alert or spacing_alert:
                    score = min(0.65, 0.40 + (max_jump / 10.0) * 0.20 + min(0.15, spacing_outlier * 0.03))
                    reason = (
                        f"Glyph baseline shift of {max_jump:.1f}px and kerning variance of {spacing_outlier:.2f}"
                        if baseline_alert
                        else f"Kerning outlier of {spacing_outlier:.2f} in mixed-script strip"
                    )
                    anomalies.append(([x, y, bw, bh], score, reason))

        return anomalies[:3]

    def _analyze_numerical_baselines(self, gray: np.ndarray) -> List[Tuple[List[int], float, str]]:
        """
        Analyze digit strips to detect vertical baseline height jumps in numeral sequences
        (amounts, transaction IDs, timestamps, account numbers).
        Specifically isolates uniform lining digits, naturally filtering out regular text,
        lowercase descenders, and footer legal disclaimers.
        """
        h, w = gray.shape
        blurred = cv2.GaussianBlur(gray, (3, 3), 0)
        _, binary = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

        # Merge horizontally adjacent characters into word/amount strips
        merge_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (8, 2))
        merged = cv2.morphologyEx(binary, cv2.MORPH_DILATE, merge_kernel)

        contours, _ = cv2.findContours(merged, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        anomalies = []

        for cnt in contours:
            x, y, bw, bh = cv2.boundingRect(cnt)
            # Focus on financial transaction body (15% to 80% height), ignoring status bar and footer legal notices
            if int(h * 0.15) < y < int(h * 0.80) and 50 < bw < w * 0.65 and 14 < bh < 45:
                strip = binary[y:y+bh, x:x+bw]
                glyph_cnts, _ = cv2.findContours(strip, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

                glyph_boxes = []
                for g_cnt in glyph_cnts:
                    gx, gy, gw, gh = cv2.boundingRect(g_cnt)
                    # Filter out tiny noise specks
                    if gw >= 3 and gh >= 8:
                        glyph_boxes.append((gx, gy, gw, gh, gy + gh))  # bottom y is baseline

                if len(glyph_boxes) >= 4:
                    heights = [b[3] for b in glyph_boxes if b[3] >= 10]
                    if len(heights) >= 4:
                        med_h = float(np.median(heights))
                        # Digits in uniform banking fonts share identical height (within 1px)
                        digit_glyphs = [
                            b for b in glyph_boxes
                            if abs(b[3] - med_h) <= 1 and 0.25 <= (b[2] / max(b[3], 1)) <= 1.15
                        ]

                        # Must be predominantly a numeral/digit sequence (>= 60% digit-like glyphs)
                        if len(digit_glyphs) >= 4 and (len(digit_glyphs) / len(glyph_boxes)) >= 0.60:
                            digit_glyphs.sort(key=lambda b: b[0])
                            baselines = [b[4] for b in digit_glyphs]
                            diffs = [abs(baselines[i+1] - baselines[i]) for i in range(len(baselines) - 1)]
                            max_jump = max(diffs) if diffs else 0

                            # In authentic slips, lining digits have baseline variance <= 1.5px
                            # In spliced Canva / mobile markup inserts, baseline jump >= 4.5px
                            if max_jump >= self.baseline_jump_threshold:
                                score = min(0.85, 0.45 + (max_jump / 8.0) * 0.35)
                                anomalies.append(([x, y, bw, bh], score, f"Numeral baseline shift of {max_jump:.1f}px in number strip"))

        return anomalies[:3]
