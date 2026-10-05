"""Screen recapture and Moiré anti-spoofing analysis.

This detector targets the common attack in which a fraudster displays a forged
slip on a phone, tablet, or laptop screen and re-photographs it. The spectral
signature of a screen recapture is a strong high-frequency Moiré pattern that
manifests as elevated energy in a ring-like region of the 2D FFT magnitude
spectrum.
"""

from __future__ import annotations

from typing import Any, Dict, Union

import cv2
import numpy as np
from PIL import Image

ImageLike = Union[Image.Image, np.ndarray]


def _to_grayscale(image_like: ImageLike) -> np.ndarray:
    """Convert PIL or OpenCV-style input to single-channel float grayscale."""
    if isinstance(image_like, Image.Image):
        rgb = image_like.convert("RGB")
        arr = np.asarray(rgb)
        return cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY).astype(np.float32)

    arr = np.asarray(image_like)
    if arr.ndim == 2:
        return arr.astype(np.float32)
    if arr.ndim == 3:
        if arr.shape[2] == 4:
            arr = arr[:, :, :3]
        if arr.shape[2] == 3:
            # PIL images are RGB while OpenCV arrays are BGR. If channel means are
            # dominated by blue, assume BGR; otherwise assume RGB.
            if np.mean(arr[:, :, 2]) > np.mean(arr[:, :, 0]):
                return cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY).astype(np.float32)
            return cv2.cvtColor(arr, cv2.COLOR_BGR2GRAY).astype(np.float32)
    raise TypeError("Unsupported image type for anti-spoof analysis")


class ScreenMoireDetector:
    """Detect display recapture / screen spoofing using FFT spectral peaks."""

    def __init__(
        self,
        min_ring_ratio: float = 0.50,
        min_peak_ratio: float = 120.0,
        min_angular_entropy: float = 0.20,
    ) -> None:
        self.min_ring_ratio = min_ring_ratio
        self.min_peak_ratio = min_peak_ratio
        self.min_angular_entropy = min_angular_entropy

    def _fft_signature(self, gray: np.ndarray) -> Dict[str, float]:
        if gray.size < 64:
            return {
                "moire_energy_ratio": 0.0,
                "spectral_peak_ratio": 0.0,
                "angular_entropy": 0.0,
            }

        centered = gray.astype(np.float32) - np.mean(gray)
        fft = np.fft.fftshift(np.fft.fft2(centered))
        magnitude = np.abs(fft)
        magnitude = magnitude / (np.max(magnitude) + 1e-9)

        h, w = magnitude.shape
        cy, cx = h // 2, w // 2
        yy, xx = np.indices((h, w))
        dist = np.hypot(yy - cy, xx - cx)
        max_radius = max(10.0, min(cy, cx))
        ring_mask = (dist >= 0.08 * max_radius) & (dist <= 0.45 * max_radius)

        if not np.any(ring_mask):
            return {
                "moire_energy_ratio": 0.0,
                "spectral_peak_ratio": 0.0,
                "angular_entropy": 0.0,
            }

        ring_mag = magnitude[ring_mask]
        total_energy = float(np.sum(magnitude ** 2))
        ring_energy = float(np.sum(ring_mag ** 2))
        moire_energy_ratio = ring_energy / (total_energy + 1e-9)

        peak_score = 0.0
        if ring_mag.size:
            peak_score = float(np.max(ring_mag) / (np.median(ring_mag) + 1e-9))

        angles = np.arctan2(yy[ring_mask] - cy, xx[ring_mask] - cx)
        weights = np.square(ring_mag)
        if weights.size > 1:
            hist_bins = np.linspace(-np.pi, np.pi, 18, endpoint=False)
            hist, _ = np.histogram(angles, bins=hist_bins, weights=weights)
            hist = hist[hist > 0]
            if hist.size > 0:
                probs = hist / (np.sum(hist) + 1e-9)
                entropy = -np.sum(probs * np.log(probs + 1e-9))
                angular_entropy = float(entropy / (np.log(hist.size) + 1e-9))
            else:
                angular_entropy = 0.0
        else:
            angular_entropy = 0.0

        return {
            "moire_energy_ratio": float(moire_energy_ratio),
            "spectral_peak_ratio": float(peak_score),
            "angular_entropy": float(angular_entropy),
        }

    def analyze(self, image_like: ImageLike) -> Dict[str, Any]:
        """Return screen recapture detection diagnostics."""
        gray = _to_grayscale(image_like)
        spectral = self._fft_signature(gray)
        moire_ratio = spectral["moire_energy_ratio"]
        peak_ratio = spectral["spectral_peak_ratio"]
        angular_entropy = spectral["angular_entropy"]

        # Screen recapture moiré exhibits a broad ring of periodic interference peaks.
        # Plain screenshots / paper scans have low high-frequency ring energy and a
        # more localized spectral distribution.
        confidence = (
            0.50 * np.clip((moire_ratio - 0.30) / 0.40, 0.0, 1.0)
            + 0.35 * np.clip((peak_ratio - 75.0) / 200.0, 0.0, 1.0)
            + 0.15 * np.clip((angular_entropy - self.min_angular_entropy) / 0.6, 0.0, 1.0)
        )
        confidence = float(np.clip(confidence, 0.0, 1.0))

        is_screen_recapture = bool(
            moire_ratio >= self.min_ring_ratio
            and peak_ratio >= self.min_peak_ratio
            and angular_entropy >= self.min_angular_entropy
        )

        if not is_screen_recapture and confidence > 0.75:
            is_screen_recapture = True

        return {
            "is_screen_recapture": is_screen_recapture,
            "screen_spoof_confidence": round(confidence, 4),
            "moire_energy_ratio": round(moire_ratio, 6),
            "spectral_peak_ratio": round(peak_ratio, 4),
            "angular_entropy": round(angular_entropy, 4),
            "thresholds": {
                "min_ring_ratio": self.min_ring_ratio,
                "min_peak_ratio": self.min_peak_ratio,
                "min_angular_entropy": self.min_angular_entropy,
            },
            "notes": (
                ["Strong Moiré spectral signature consistent with a phone/tablet screen recapture."]
                if is_screen_recapture else ["No strong screen-recapture moiré signature detected."]
            ),
        }

    def evaluate(self, image_like: ImageLike) -> Dict[str, Any]:
        """Compatibility alias for the wider forensic pipeline."""
        return self.analyze(image_like)


def analyze_screen_recapture(image_like: ImageLike) -> Dict[str, Any]:
    """Module-level convenience wrapper for screen spoof detection."""
    return ScreenMoireDetector().analyze(image_like)


def detect_screen_recapture(image_like: ImageLike) -> Dict[str, Any]:
    """Alias used by callers expecting a detect_* function."""
    return analyze_screen_recapture(image_like)


def detect_screen_spoofing(image_like: ImageLike) -> Dict[str, Any]:
    """Alias used by callers expecting spoofing terminology."""
    return analyze_screen_recapture(image_like)


def analyze_moire_pattern(image_like: ImageLike) -> Dict[str, Any]:
    """Alias emphasizing the spectral moiré analysis."""
    return analyze_screen_recapture(image_like)


__all__ = [
    "ImageLike",
    "ScreenMoireDetector",
    "analyze_screen_recapture",
    "detect_screen_recapture",
    "detect_screen_spoofing",
    "analyze_moire_pattern",
]
