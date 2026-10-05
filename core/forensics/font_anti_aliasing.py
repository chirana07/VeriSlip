"""Sub-pixel glyph rasterization consistency analysis.

The detector is deliberately model-free. It profiles connected glyphs using
their 90/10 edge transition width and RGB color-fringe ratio, then compares
each glyph with the robust median rasterization profile of the document.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

import cv2
import numpy as np
from PIL import Image


@dataclass(frozen=True)
class GlyphRasterizationConfig:
    """Thresholds for robust per-document render-engine comparison."""

    outlier_z_threshold: float = 3.0
    min_glyph_height: int = 8
    min_glyphs: int = 6
    min_transition_delta: float = 0.35
    min_fringe_delta: float = 0.035


class FontAntiAliasingAnalyzer:
    """Detect glyphs whose anti-aliasing differs from surrounding text."""

    def __init__(self, config: GlyphRasterizationConfig | None = None) -> None:
        self.config = config or GlyphRasterizationConfig()

    @staticmethod
    def _robust_z(values: np.ndarray, floor: float) -> np.ndarray:
        median = float(np.median(values))
        mad = float(np.median(np.abs(values - median)))
        scale = max(1.4826 * mad, floor)
        return np.abs(values - median) / scale

    def _glyph_profiles(self, rgb: np.ndarray) -> List[Dict[str, Any]]:
        gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
        binary = (gray < 245).astype(np.uint8)
        count, _, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
        profiles: List[Dict[str, Any]] = []

        for index in range(1, count):
            x, y, width, height, area = (int(value) for value in stats[index])
            if height < self.config.min_glyph_height or width < 2 or area < 12:
                continue
            if width > rgb.shape[1] * 0.25 or height > rgb.shape[0] * 0.20:
                continue

            pad = 2
            x0, y0 = max(0, x - pad), max(0, y - pad)
            x1, y1 = min(rgb.shape[1], x + width + pad), min(
                rgb.shape[0], y + height + pad
            )
            glyph_rgb = rgb[y0:y1, x0:x1].astype(np.float32)
            glyph_gray = gray[y0:y1, x0:x1]
            edge = cv2.Canny(glyph_gray, 40, 120) > 0
            edge_band = cv2.dilate(edge.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0
            if int(edge_band.sum()) < 8:
                continue

            # Pixels between the 10% and 90% luminance levels form the PSF
            # transition band. Dividing by edge length expresses width in px.
            transition = (glyph_gray > 26) & (glyph_gray < 230) & edge_band
            edge_length = max(float(edge.sum()), 1.0)
            transition_width = 1.0 + float(transition.sum()) / edge_length

            red, green, blue = (glyph_rgb[:, :, channel] for channel in range(3))
            fringe_map = np.abs(red - blue) / (green + 1.0)
            fringe_mask = transition if np.any(transition) else edge_band
            fringe_ratio = float(np.median(fringe_map[fringe_mask]))
            profiles.append(
                {
                    "box": [x, y, width, height],
                    "transition_width": transition_width,
                    "fringe_ratio": fringe_ratio,
                }
            )
        return profiles

    def analyze(self, image: Image.Image | np.ndarray) -> Dict[str, Any]:
        """Compare glyph PSF/fringe profiles and localize >3σ outliers."""

        if isinstance(image, Image.Image):
            rgb = np.asarray(image.convert("RGB"), dtype=np.uint8)
        else:
            rgb = np.asarray(image, dtype=np.uint8)
            if rgb.ndim == 2:
                rgb = cv2.cvtColor(rgb, cv2.COLOR_GRAY2RGB)
            elif rgb.ndim != 3 or rgb.shape[2] not in (3, 4):
                raise ValueError(
                    "font anti-aliasing analysis requires a grayscale, RGB, or RGBA image"
                )
            elif rgb.shape[2] == 4:
                rgb = cv2.cvtColor(rgb, cv2.COLOR_RGBA2RGB)

        profiles = self._glyph_profiles(rgb)
        if len(profiles) < self.config.min_glyphs:
            return self._result(profiles, [], "insufficient_glyphs")

        widths = np.asarray([profile["transition_width"] for profile in profiles])
        fringes = np.asarray([profile["fringe_ratio"] for profile in profiles])
        width_z = self._robust_z(
            widths, self.config.min_transition_delta / self.config.outlier_z_threshold
        )
        fringe_z = self._robust_z(
            fringes, self.config.min_fringe_delta / self.config.outlier_z_threshold
        )
        width_median = float(np.median(widths))
        fringe_median = float(np.median(fringes))

        outliers: List[Dict[str, Any]] = []
        for profile, wz, fz in zip(profiles, width_z, fringe_z):
            width_delta = abs(profile["transition_width"] - width_median)
            fringe_delta = abs(profile["fringe_ratio"] - fringe_median)
            width_outlier = (
                wz > self.config.outlier_z_threshold
                and width_delta >= self.config.min_transition_delta
            )
            fringe_outlier = (
                fz > self.config.outlier_z_threshold
                and fringe_delta >= self.config.min_fringe_delta
            )
            if not (width_outlier or fringe_outlier):
                continue
            confidence = min(0.99, 0.5 + 0.08 * max(float(wz), float(fz)))
            outliers.append(
                {
                    **profile,
                    "transition_z_score": round(float(wz), 3),
                    "fringe_z_score": round(float(fz), 3),
                    "confidence": round(confidence, 3),
                    "label": "Alien glyph rasterization profile",
                }
            )

        return self._result(profiles, outliers, "analyzed")

    def _result(
        self,
        profiles: List[Dict[str, Any]],
        outliers: List[Dict[str, Any]],
        status: str,
    ) -> Dict[str, Any]:
        ratio = len(outliers) / max(len(profiles), 1)
        score = min(
            1.0,
            ratio * 3.0
            + max((item["confidence"] for item in outliers), default=0.0) * 0.35,
        )
        return {
            "status": status,
            "is_anomalous": bool(outliers),
            "anomaly_score": round(score, 3),
            "glyphs_analyzed": len(profiles),
            "outlier_count": len(outliers),
            "median_transition_width": (
                round(float(np.median([p["transition_width"] for p in profiles])), 4)
                if profiles
                else 0.0
            ),
            "median_fringe_ratio": (
                round(float(np.median([p["fringe_ratio"] for p in profiles])), 5)
                if profiles
                else 0.0
            ),
            "detected_regions": outliers,
            "findings": (
                [
                    f"{len(outliers)} glyph(s) diverge from the document rasterization profile."
                ]
                if outliers
                else []
            ),
        }


def analyze_font_anti_aliasing(image: Image.Image | np.ndarray) -> Dict[str, Any]:
    """Analyze sub-pixel glyph boundary consistency with default thresholds."""

    return FontAntiAliasingAnalyzer().analyze(image)
