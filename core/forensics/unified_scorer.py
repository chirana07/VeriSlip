"""
Unified Forensic Scorer & Multi-Layer Ensemble for VeriSlip.
Aggregates Layer 1 (Structural), Layer 2 (Classical ELA/DCT), and Layer 3 (Noise Forensics)
into a unified tamper risk score, localized bounding boxes, and actionable seller recommendations.
"""

import os
import json
from typing import Dict, Any, List, Optional
from PIL import Image
import numpy as np

from core.forensics.anti_spoof import analyze_screen_recapture
from core.forensics.layer1_structural import Layer1StructuralValidator
from core.forensics.layer1_semantic import Layer1SemanticValidator
from core.forensics.layer2_classical import Layer2ClassicalForensics
from core.forensics.layer2_occlusion import Layer2OcclusionDetector
from core.forensics.layer3_noise import Layer3NoiseForensics
from core.forensics.font_kerning import CharacterAlignmentValidator
from core.forensics.xai_gradcam import Layer4GradCAM
from core.ml.ensemble_model import Layer4DeepEnsemble
from core.ml.vlm_semantic_reasoner import LightweightVisionLanguageReasoner
from core.forensics.ocr_extractor import ReceiptFieldExtractor
from core.forensics.utils import normalize_dimensions, pil_to_base64

def merge_bounding_boxes(boxes: List[Dict[str, Any]], iou_thresh: float = 0.3) -> List[Dict[str, Any]]:
    """Merge overlapping bounding boxes from multiple forensic layers using Non-Maximum Suppression (NMS)."""
    if not boxes:
        return []

    # Sort boxes by confidence
    boxes = sorted(boxes, key=lambda b: b.get("confidence", 0.5), reverse=True)
    merged = []

    def iou(b1, b2):
        x1, y1, w1, h1 = b1
        x2, y2, w2, h2 = b2
        xi1 = max(x1, x2)
        yi1 = max(y1, y2)
        xi2 = min(x1 + w1, x2 + w2)
        yi2 = min(y1 + h1, y2 + h2)
        inter_area = max(0, xi2 - xi1) * max(0, yi2 - yi1)
        b1_area = w1 * h1
        b2_area = w2 * h2
        union_area = b1_area + b2_area - inter_area
        return inter_area / max(union_area, 1e-5)

    while boxes:
        current = boxes.pop(0)
        merged.append(current)
        boxes = [b for b in boxes if iou(current["box"], b["box"]) < iou_thresh]

    return merged

class VeriSlipForensicEngine:
    """Master engine orchestrating all detection layers."""

    def __init__(self):
        self.layer1 = Layer1StructuralValidator()
        self.layer1_semantic = Layer1SemanticValidator()
        self.layer2 = Layer2ClassicalForensics()
        self.layer2_occlusion = Layer2OcclusionDetector()
        self.layer3 = Layer3NoiseForensics()
        self.layer4 = Layer4DeepEnsemble()
        self.vlm_reasoner = LightweightVisionLanguageReasoner()
        self.xai_gradcam = Layer4GradCAM(self.layer4.model)
        self.font_validator = CharacterAlignmentValidator()
        self.field_extractor = ReceiptFieldExtractor()
        self.calibration_path = os.environ.get("VERISLIP_CALIBRATION_PATH", "weights/calibration_profile.json")
        self.calibration = None
        self._load_calibration()

    def _load_calibration(self):
        """Load empirical real-world calibration profile if present."""
        if self.calibration_path and os.path.exists(self.calibration_path):
            try:
                with open(self.calibration_path, "r") as f:
                    self.calibration = json.load(f)
                print(f"[VeriSlip Engine] Loaded real-world calibration profile from {self.calibration_path}")
            except Exception as e:
                print(f"[VeriSlip Engine] Warning: Could not load calibration profile: {e}")

    def analyze(
        self,
        pil_image: Image.Image,
        bank_code: Optional[str] = None,
        reference_no: Optional[str] = None,
        include_heatmaps: bool = True
    ) -> Dict[str, Any]:
        """
        Execute multi-layer forensic analysis on payment slip image.
        """
        # Resize if oversized for efficient, responsive inference and guarantee RGB mode
        orig_info = getattr(pil_image, "info", {}).copy()
        normalized_img = normalize_dimensions(pil_image, max_dim=1400).convert("RGB")
        normalized_img.info = orig_info

        # Run layers 1, 2, and 3 + Font Alignment Validator
        l1_res = self.layer1.evaluate(normalized_img, bank_code=bank_code, reference_no=reference_no)
        l2_res = self.layer2.evaluate(normalized_img)
        screen_spoof_res = analyze_screen_recapture(normalized_img)
        l3_res = self.layer3.evaluate(normalized_img)
        font_res = self.font_validator.evaluate(normalized_img)

        # Run Layer 1.5 Semantic Financial Validator & Layer 2.5 Occlusion Detector
        ocr_tokens = self.field_extractor.extract_ocr_tokens(normalized_img)
        l1_sem_res = self.layer1_semantic.evaluate(ocr_tokens, bank_code=bank_code)
        l2_occ_res = self.layer2_occlusion.evaluate(normalized_img)

        # Run Layer 4 Deep Learning Ensemble and lightweight VLM semantic reasoning
        diff_gray = l2_res.get("diff_gray", np.zeros((normalized_img.height, normalized_img.width), dtype=np.float32))
        residual = l3_res.get("residual", np.zeros((normalized_img.height, normalized_img.width), dtype=np.float32))
        l4_res = self.layer4.evaluate(normalized_img, diff_gray, residual)
        vlm_context = {
            "bank_code": bank_code,
            "reference_no": reference_no,
            "branch_code": "",
            "account_prefix": "",
        }
        vlm_res = self.vlm_reasoner.evaluate(
            normalized_img,
            ocr_tokens,
            bank_code=bank_code,
            reference_no=reference_no,
            slip_context=vlm_context,
        )

        xai_payload = {}
        if include_heatmaps:
            forensic_tensor = self.layer4.prepare_forensic_tensor(diff_gray, residual, (normalized_img.height, normalized_img.width), pil_image=normalized_img)
            xai_payload = self.xai_gradcam.generate(normalized_img, forensic_input=forensic_tensor)

        # Multi-modal fusion weights (dynamically tuned if calibration profile is active)
        if self.calibration and "tuned_weights" in self.calibration:
            tw = self.calibration["tuned_weights"]
            w1 = tw.get("w1_structural", 0.20)
            w2 = tw.get("w2_classical", 0.25)
            w3 = tw.get("w3_noise", 0.25)
            w4 = tw.get("w4_ensemble", 0.30)
            w5 = tw.get("w5_vlm", 0.10)
        else:
            w1, w2, w3, w4, w5 = 0.18, 0.225, 0.225, 0.27, 0.10

        screen_spoof_weight = 0.15 if screen_spoof_res["is_screen_recapture"] else 0.0
        weighted_risk = (
            w1 * l1_res["anomaly_score"] +
            w2 * l2_res["anomaly_score"] +
            w3 * l3_res["anomaly_score"] +
            w4 * l4_res["anomaly_score"] +
            w5 * vlm_res["anomaly_score"] +
            screen_spoof_weight * screen_spoof_res["screen_spoof_confidence"]
        )

        # Non-Diluting Max-Pooled Fusion:
        # Decisive anomalies override linear dilution, preventing missed tampering
        l4_corroborated = (
            len(l4_res.get("detected_regions", [])) > 0 or
            l1_res["anomaly_score"] > 0.35 or
            l2_res.get("is_anomalous", False) or
            l3_res.get("is_anomalous", False) or
            font_res.get("is_anomalous", False) or
            l1_sem_res["is_anomalous"] or
            vlm_res["is_anomalous"]
        )
        l2_occ_corroborated = (
            l1_sem_res["is_anomalous"] or
            l1_res["metadata_analysis"]["is_suspicious"] or
            l2_res.get("is_anomalous", False) or
            l3_res.get("is_anomalous", False) or
            l4_res["anomaly_score"] > 0.70 or
            font_res.get("is_anomalous", False) or
            vlm_res["is_anomalous"]
        )
        peak_signals = [
            weighted_risk,
            l1_sem_res["anomaly_score"] if l1_sem_res["is_anomalous"] else 0.0,
            l2_occ_res["anomaly_score"] * 0.95 if (l2_occ_res["is_anomalous"] and l2_occ_corroborated) else 0.0,
            l2_res["anomaly_score"] * 0.90 if l2_res.get("is_anomalous", False) else 0.0,
            l3_res["anomaly_score"] * 0.90 if l3_res.get("is_anomalous", False) else 0.0,
            l4_res["anomaly_score"] * 0.92 if (l4_res["anomaly_score"] > 0.70 and l4_corroborated) else 0.0,
            font_res["anomaly_score"] * 0.85 if (font_res.get("is_anomalous", False) and font_res["anomaly_score"] > 0.65) else 0.0,
            vlm_res["anomaly_score"] * 0.95 if (vlm_res["is_anomalous"] and vlm_res["anomaly_score"] >= 0.45) else 0.0,
        ]
        composite_risk = max(peak_signals)

        # Boost risk if editing software was definitively identified in file metadata
        if l1_res["metadata_analysis"]["is_suspicious"]:
            composite_risk = max(composite_risk, 0.75)

        # Decisive Semantic override (Mathematical & Temporal paradoxes are impossible in authentic receipts)
        if l1_sem_res["is_anomalous"]:
            composite_risk = max(composite_risk, l1_sem_res["anomaly_score"])

        # Corroborated Occlusion override
        if l2_occ_res["is_anomalous"] and l2_occ_corroborated:
            composite_risk = max(composite_risk, l2_occ_res["anomaly_score"])

        if vlm_res["is_anomalous"] and vlm_res["anomaly_score"] >= 0.45:
            composite_risk = max(composite_risk, vlm_res["anomaly_score"])

        # Collect candidate bounding boxes from all layers
        candidate_boxes = []

        # Layer 1.5 Semantic regions
        for box in l1_sem_res.get("detected_regions", []):
            candidate_boxes.append(box)

        # Layer 2.5 Occlusion patches
        for box in l2_occ_res.get("detected_regions", []):
            candidate_boxes.append(box)

        if l2_res.get("is_anomalous", False):
            for box in l2_res.get("detected_regions", []):
                candidate_boxes.append(box)

        if l3_res.get("is_anomalous", False):
            for outlier in l3_res.get("outlier_blocks", []):
                candidate_boxes.append({
                    "box": outlier["box"],
                    "confidence": round(min(0.90, outlier["z_score"] * 0.15) * l3_res["anomaly_score"], 2),
                    "label": "Noise Residual Break"
                })

        for box in l4_res.get("detected_regions", []):
            candidate_boxes.append(box)

        for box in vlm_res.get("detected_regions", []):
            candidate_boxes.append(box)

        if font_res.get("is_anomalous", False):
            for box in font_res.get("detected_regions", []):
                candidate_boxes.append(box)

        final_boxes = merge_bounding_boxes(candidate_boxes)

        # Corroborated tamper box elevation:
        # Avoid false positives from isolated phantom boxes by requiring multi-layer corroboration
        if final_boxes:
            top_box_conf = max(b.get("confidence", 0.5) for b in final_boxes)
            has_corroborating_evidence = (
                l2_res.get("is_anomalous", False) or
                l2_res["anomaly_score"] > 0.32 or
                l3_res.get("is_anomalous", False) or
                l3_res["anomaly_score"] > 0.35 or
                l4_res["anomaly_score"] > 0.65 or
                l1_sem_res["is_anomalous"] or
                l1_res["metadata_analysis"]["is_suspicious"] or
                (vlm_res["is_anomalous"] and vlm_res["anomaly_score"] >= 0.45)
            )
            if top_box_conf > 0.70 and has_corroborating_evidence:
                composite_risk = max(composite_risk, 0.55 + 0.35 * top_box_conf)
            elif top_box_conf > 0.85 and (l2_res.get("is_anomalous", False) or l3_res.get("is_anomalous", False)):
                composite_risk = max(composite_risk, 0.60)

        # Calibrated risk percentage (0 to 100%)
        risk_percentage = round(min(100.0, max(0.0, composite_risk * 100.0)), 1)

        # Determine calibrated thresholds
        auth_ceiling = 25.0
        susp_ceiling = 55.0
        if self.calibration and "thresholds" in self.calibration:
            auth_ceiling = self.calibration["thresholds"].get("authentic_max_risk", 25.0)
            susp_ceiling = self.calibration["thresholds"].get("suspicious_max_risk", 55.0)

        # Determine verdict category
        if risk_percentage <= auth_ceiling:
            verdict = "AUTHENTIC"
            verdict_color = "#10B981"  # Emerald Green
            recommendation = "Low tamper risk. Payment slip appears genuine. Safe to release goods."
        elif risk_percentage <= susp_ceiling:
            verdict = "SUSPICIOUS"
            verdict_color = "#F59E0B"  # Amber Yellow
            recommendation = "Moderate anomalies detected. Recommend checking bank balance before dispatching."
        else:
            verdict = "HIGH_RISK_TAMPERED"
            verdict_color = "#EF4444"  # Red
            recommendation = "High probability of digital tampering. DO NOT ship goods on this slip alone."

        # Collect all findings
        all_findings = []
        all_findings.extend(l1_sem_res.get("findings", []))
        all_findings.extend(l2_occ_res.get("findings", []))
        all_findings.extend(l1_res.get("findings", []))
        all_findings.extend(l2_res.get("findings", []))
        all_findings.extend(l3_res.get("findings", []))
        all_findings.extend(font_res.get("findings", []))
        all_findings.extend(l4_res.get("findings", []))
        all_findings.extend(vlm_res.get("findings", []))

        return {
            "verdict": verdict,
            "verdict_color": verdict_color,
            "tamper_risk_percentage": risk_percentage,
            "confidence_score": round(abs(risk_percentage - 50.0) / 50.0, 2),
            "calibration_profile": "Active (Empirical Real-World Profile)" if self.calibration else "Default Calibrated Prior",
            "recommendation": recommendation,
            "flagged_regions": final_boxes[:5],
            "layer_breakdowns": {
                "layer1_structural": {
                    "score": l1_res["anomaly_score"],
                    "is_anomalous": l1_res["is_anomalous"],
                    "findings": l1_res["findings"],
                    "metadata": l1_res["metadata_analysis"],
                    "layout": l1_res["layout_analysis"]
                },
                "layer1_semantic": {
                    "score": l1_sem_res["anomaly_score"],
                    "is_anomalous": l1_sem_res["is_anomalous"],
                    "findings": l1_sem_res["findings"]
                },
                "layer2_classical": {
                    "score": l2_res["anomaly_score"],
                    "is_anomalous": l2_res["is_anomalous"],
                    "ela_variance": l2_res["ela_variance"],
                    "findings": l2_res["findings"],
                    "double_compression": l2_res["double_compression_analysis"],
                    "screen_spoof": l2_res.get("screen_spoof_analysis", screen_spoof_res)
                },
                "layer2_occlusion": {
                    "score": l2_occ_res["anomaly_score"],
                    "is_anomalous": l2_occ_res["is_anomalous"],
                    "findings": l2_occ_res["findings"]
                },
                "layer3_noise": {
                    "score": l3_res["anomaly_score"],
                    "is_anomalous": l3_res["is_anomalous"],
                    "mean_noise_variance": l3_res["mean_noise_variance"],
                    "findings": l3_res["findings"]
                },
                "layer4_ensemble": {
                    "score": l4_res["anomaly_score"],
                    "is_anomalous": l4_res["is_anomalous"],
                    "tamper_probability": l4_res.get("tamper_probability", 0.0),
                    "engine": l4_res.get("engine", "Deep Learning"),
                    "findings": l4_res.get("findings", [])
                },
                "layer4_vlm_reasoning": {
                    "score": vlm_res["anomaly_score"],
                    "is_anomalous": vlm_res["is_anomalous"],
                    "confidence": vlm_res.get("confidence", 0.0),
                    "findings": vlm_res.get("findings", []),
                    "structured_output": vlm_res.get("structured_output", {})
                }
            },
            "forensic_maps": {
                "original_b64": pil_to_base64(normalized_img, format="JPEG"),
                "ela_heatmap_base64": l2_res.get("heatmap_base64"),
                "noise_heatmap_base64": l3_res.get("noise_heatmap_base64"),
                "gradcam_heatmap_base64": xai_payload.get("heatmap_base64"),
                "gradcam_overlay_base64": xai_payload.get("overlay_base64"),
                "counterfactual_base64": xai_payload.get("counterfactual_base64"),
            } if include_heatmaps else {},
            "findings_summary": all_findings,
            "xai_gradcam": {
                "bbox": xai_payload.get("bbox"),
                "iou": xai_payload.get("iou"),
                "heatmap_base64": xai_payload.get("heatmap_base64"),
                "counterfactual_base64": xai_payload.get("counterfactual_base64"),
            } if include_heatmaps else {},
        }
