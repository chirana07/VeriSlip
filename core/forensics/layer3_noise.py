"""
Layer 3 Forensics: Noise Residual and Spatial Inconsistency Analysis.
- High-pass spatial noise extraction (Median Filter Residual)
- Block-wise local noise variance mapping
- Discontinuity detection for spliced text / erased rectangles / clone-stamped patches
- PRNU-like sensor noise fingerprinting using a light Haar wavelet residual.
"""

from typing import Dict, Any, List, Tuple, Optional
import numpy as np
from PIL import Image
import cv2

from core.forensics.utils import pil_to_cv2, cv2_to_base64

SRM_KERNELS: Dict[str, np.ndarray] = {
    "srm_1st_horizontal": np.array([[0, 0, 0], [-1, 1, 0], [0, 0, 0]], dtype=np.float32),
    "srm_1st_vertical": np.array([[0, -1, 0], [0, 1, 0], [0, 0, 0]], dtype=np.float32),
    "srm_2nd_horizontal": np.array([[0, 0, 0], [-1, 2, -1], [0, 0, 0]], dtype=np.float32),
    "srm_2nd_vertical": np.array([[0, -1, 0], [0, 2, 0], [0, -1, 0]], dtype=np.float32),
    "srm_edge_3x3": np.array([[-1, 2, -1], [2, -4, 2], [-1, 2, -1]], dtype=np.float32) / 4.0,
    "srm_square_3x3": np.array([[-1, -1, -1], [-1, 8, -1], [-1, -1, -1]], dtype=np.float32) / 8.0,
    "srm_edge_5x5": np.array([
        [-1,  2,  -2,  2, -1],
        [ 2, -6,   8, -6,  2],
        [-2,  8, -12,  8, -2],
        [ 2, -6,   8, -6,  2],
        [-1,  2,  -2,  2, -1]
    ], dtype=np.float32) / 12.0,
}


class Layer3NoiseForensics:
    """Evaluates noise residual variance and spatial consistency across patches."""

    def __init__(self, block_size: int = 32, median_ksize: int = 3):
        self.block_size = block_size
        self.median_ksize = median_ksize

    @staticmethod
    def _haar_wavelet_levels(gray: np.ndarray, max_levels: int = 2) -> List[np.ndarray]:
        """Return the finest-detail Haar wavelet bands from the grayscale image."""
        current = gray.astype(np.float32)
        bands: List[np.ndarray] = []
        for _ in range(max_levels):
            if current.shape[0] < 2 or current.shape[1] < 2:
                break
            a = current[0::2, 0::2]
            b = current[0::2, 1::2]
            c = current[1::2, 0::2]
            d = current[1::2, 1::2]
            if a.shape != b.shape or a.shape != c.shape or a.shape != d.shape:
                break

            ll = (a + b + c + d) / 4.0
            lh = (a + b - c - d) / 4.0
            hl = (a - b + c - d) / 4.0
            hh = (a - b - c + d) / 4.0
            bands.append(np.abs(lh) + np.abs(hl) + np.abs(hh))
            current = ll
        return bands

    def extract_dwt_noise_residual(self, gray: np.ndarray, levels: int = 2) -> np.ndarray:
        """Estimate a PRNU-like wavelet residual by summing high-frequency Haar components."""
        if gray.ndim != 2:
            gray = cv2.cvtColor(gray, cv2.COLOR_BGR2GRAY) if gray.ndim == 3 else gray
        bands = self._haar_wavelet_levels(gray, max_levels=levels)
        if not bands:
            return np.zeros_like(gray, dtype=np.float32)

        residual = np.zeros_like(gray, dtype=np.float32)
        for band in bands:
            if residual.shape != band.shape:
                band = cv2.resize(band, (residual.shape[1], residual.shape[0]), interpolation=cv2.INTER_LINEAR)
            residual += band
        return residual / max(len(bands), 1)

    def extract_wavelet_noise_residual(self, gray: np.ndarray, levels: int = 2) -> np.ndarray:
        """Compatibility alias for DWT-based sensor-noise extraction."""
        return self.extract_dwt_noise_residual(gray, levels=levels)

    def estimate_prnu_fingerprint(self, gray: np.ndarray, levels: int = 2) -> np.ndarray:
        """Return a normalized PRNU fingerprint candidate learned from the DWT noise residual."""
        if gray.ndim != 2:
            gray = cv2.cvtColor(gray, cv2.COLOR_BGR2GRAY) if gray.ndim == 3 else gray
        residual = self.extract_dwt_noise_residual(gray, levels=levels).astype(np.float32)
        residual = residual - float(np.mean(residual))
        sigma = float(np.std(residual))
        if sigma < 1e-6:
            return np.zeros_like(residual, dtype=np.float32)
        return residual / sigma

    def estimate_sensor_pattern_noise(self, gray: np.ndarray, levels: int = 2) -> np.ndarray:
        """Compatibility alias for PRNU-style sensor-fingerprint estimation."""
        return self.estimate_prnu_fingerprint(gray, levels=levels)

    def compute_prnu_similarity(
        self,
        gray: np.ndarray,
        reference_profile: Optional[np.ndarray] = None,
        levels: int = 2,
    ) -> Dict[str, Any]:
        """Measure how strongly the image resembles a sensor-noise fingerprint profile."""
        if gray.ndim != 2:
            gray = cv2.cvtColor(gray, cv2.COLOR_BGR2GRAY) if gray.ndim == 3 else gray

        fingerprint = self.estimate_prnu_fingerprint(gray, levels=levels)
        signal_energy = float(np.mean(np.abs(fingerprint)))

        if reference_profile is not None:
            ref = np.asarray(reference_profile, dtype=np.float32)
            ref = ref - float(np.mean(ref))
            ref_std = float(np.std(ref))
            if ref_std < 1e-6:
                cross_correlation = 0.0
            else:
                ref = ref / ref_std
                corr = np.mean(fingerprint * ref)
                cross_correlation = float(np.clip(corr, -1.0, 1.0))
        else:
            cross_correlation = 0.0
            neighbor_scores = []
            for y in range(0, max(1, fingerprint.shape[0] - 8), 8):
                for x in range(0, max(1, fingerprint.shape[1] - 8), 8):
                    block = fingerprint[y:y + 8, x:x + 8]
                    nx = min(fingerprint.shape[1] - 8, x + 8)
                    neighbor = fingerprint[y:y + 8, nx:nx + 8]
                    if block.size == 0 or neighbor.size == 0 or block.shape != neighbor.shape:
                        continue
                    denom = np.linalg.norm(block) * np.linalg.norm(neighbor) + 1e-6
                    neighbor_scores.append(float(np.mean(block * neighbor) / denom))
            if neighbor_scores:
                cross_correlation = float(np.mean(np.abs(neighbor_scores)))

        sensor_like = bool(signal_energy > 0.12 and cross_correlation >= 0.008)
        return {
            "cross_correlation": round(float(cross_correlation), 4),
            "fingerprint_strength": round(float(signal_energy), 4),
            "sensor_like": sensor_like,
            "fingerprint": fingerprint,
        }

    def measure_prnu_cross_correlation(
        self,
        gray: np.ndarray,
        reference_profile: Optional[np.ndarray] = None,
        levels: int = 2,
    ) -> Dict[str, Any]:
        """Compatibility alias reflecting the common PRNU cross-correlation terminology."""
        return self.compute_prnu_similarity(gray, reference_profile=reference_profile, levels=levels)

    def compute_prnu_profile(
        self,
        gray: np.ndarray,
        reference_profile: Optional[np.ndarray] = None,
        levels: int = 2,
    ) -> Dict[str, Any]:
        """Compatibility alias for a PRNU fingerprint summary."""
        return self.compute_prnu_similarity(gray, reference_profile=reference_profile, levels=levels)

    def extract_srm_residuals(
        self,
        gray: np.ndarray,
        kernel_names: Optional[List[str]] = None
    ) -> Dict[str, np.ndarray]:
        """
        Apply standard 3x3 and 5x5 Spatial Rich Models (SRM) high-pass filtering kernels
        to extract subtle, directional noise residuals across the canvas.
        """
        selected = kernel_names or list(SRM_KERNELS.keys())
        gray_f = gray.astype(np.float32)
        residuals = {}
        for name in selected:
            if name in SRM_KERNELS:
                kernel = SRM_KERNELS[name]
                filtered = cv2.filter2D(gray_f, cv2.CV_32F, kernel)
                residuals[name] = np.abs(filtered)
        return residuals

    def compute_srm_summary(self, gray: np.ndarray) -> Dict[str, Any]:
        """
        Compute summary statistics (variance, mean energy) across all SRM residual streams.
        """
        residuals = self.extract_srm_residuals(gray)
        metrics = {}
        variances = []
        for name, res in residuals.items():
            var = float(np.var(res))
            mean = float(np.mean(res))
            metrics[name] = {
                "variance": round(var, 4),
                "mean_energy": round(mean, 4),
            }
            variances.append(var)

        avg_srm_var = float(np.mean(variances)) if variances else 0.0
        return {
            "srm_metrics": metrics,
            "average_srm_variance": round(avg_srm_var, 4),
            "kernels_evaluated": len(metrics)
        }

    def extract_noise_residual(self, gray: np.ndarray) -> np.ndarray:
        """
        Extract high-frequency noise residual by subtracting median-filtered estimate.
        residual = |gray - median_blur(gray)|
        """
        denoised = cv2.medianBlur(gray, self.median_ksize)
        residual = cv2.absdiff(gray, denoised).astype(np.float32)
        return residual

    def compute_local_variance_map(self, gray: np.ndarray, residual: np.ndarray) -> Tuple[np.ndarray, List[Dict[str, Any]]]:
        """
        Divide residual into grid blocks and compute variance for each block,
        weighting flat and text regions to prevent natural typography edges from being flagged.
        """
        h, w = residual.shape
        bs = self.block_size
        grid_h = h // bs
        grid_w = w // bs

        # Edge mask to identify natural text/icon UI components
        edges = cv2.Canny(gray, 60, 160)

        var_map = np.zeros((grid_h, grid_w), dtype=np.float32)
        edge_density_map = np.zeros((grid_h, grid_w), dtype=np.float32)

        for gy in range(grid_h):
            for gx in range(grid_w):
                patch_res = residual[gy * bs:(gy + 1) * bs, gx * bs:(gx + 1) * bs]
                patch_edge = edges[gy * bs:(gy + 1) * bs, gx * bs:(gx + 1) * bs]
                var_map[gy, gx] = np.var(patch_res)
                edge_density_map[gy, gx] = np.sum(patch_edge > 0)

        # Flat background blocks must have ZERO detected edges
        flat_mask = edge_density_map == 0
        outlier_blocks = []

        if np.sum(flat_mask) > 10:
            flat_variances = var_map[flat_mask]
            mean_flat_var = float(np.mean(flat_variances))
            std_flat_var = float(np.std(flat_variances))

            # Detect flat blocks that have abnormal noise (e.g. brush marks or noisy paste patches)
            if std_flat_var > 0.05:
                flat_z = (var_map - mean_flat_var) / (std_flat_var + 1e-4)
                # Flag flat blocks with high noise
                outlier_indices = np.argwhere((flat_z > 3.5) & flat_mask)
                for gy, gx in outlier_indices:
                    x = int(gx * bs)
                    y = int(gy * bs)
                    outlier_blocks.append({
                        "box": [x, y, bs, bs],
                        "z_score": round(float(flat_z[gy, gx]), 2),
                        "variance": round(float(var_map[gy, gx]), 2)
                    })

        # Filter out 1D UI divider lines or hairline borders:
        # A true tamper patch is a localized 2D cluster; a 1D row spanning >= 40% grid width with low variance is a UI divider rule
        if outlier_blocks:
            row_counts: Dict[int, int] = {}
            col_counts: Dict[int, int] = {}
            for o in outlier_blocks:
                gy = o["box"][1] // bs
                gx = o["box"][0] // bs
                row_counts[gy] = row_counts.get(gy, 0) + 1
                col_counts[gx] = col_counts.get(gx, 0) + 1

            filtered_outliers = []
            for o in outlier_blocks:
                gy = o["box"][1] // bs
                gx = o["box"][0] // bs
                is_divider_row = row_counts.get(gy, 0) >= 6 and (row_counts[gy] / max(grid_w, 1)) >= 0.40 and o["variance"] < 10.0
                is_divider_col = col_counts.get(gx, 0) >= 6 and (col_counts[gx] / max(grid_h, 1)) >= 0.40 and o["variance"] < 10.0
                if not (is_divider_row or is_divider_col):
                    filtered_outliers.append(o)
            outlier_blocks = filtered_outliers

        return var_map, outlier_blocks

    def generate_noise_heatmap(self, residual: np.ndarray) -> np.ndarray:
        """Create colored visual representation of noise residual."""
        scaled = np.clip(residual * 8.0, 0, 255).astype(np.uint8)
        colored = cv2.applyColorMap(scaled, cv2.COLORMAP_VIRIDIS)
        return colored

    def evaluate(self, pil_image: Image.Image) -> Dict[str, Any]:
        """
        Run full Layer 3 noise consistency evaluation.
        """
        cv2_img = pil_to_cv2(pil_image)
        gray = cv2.cvtColor(cv2_img, cv2.COLOR_BGR2GRAY)

        residual = self.extract_noise_residual(gray)
        dwt_residual = self.extract_dwt_noise_residual(gray)
        prnu_analysis = self.compute_prnu_similarity(gray)
        var_map, outliers = self.compute_local_variance_map(gray, residual)
        noise_heatmap = self.generate_noise_heatmap(residual)

        mean_var = float(np.mean(var_map))

        # Anomaly scoring:
        # In an untouched digital receipt, flat areas have virtually zero noise residual variance.
        # A tiny statistical tail (1-2 blocks) can randomly hit 3.5 Z-score.
        # Tampered receipts where text was erased or clone-stamped create a cluster of outlier blocks.
        excess_outliers = max(0, len(outliers) - 3)
        outlier_ratio = excess_outliers / max(var_map.size, 1)
        score = min(1.0, outlier_ratio * 50.0)
        if not prnu_analysis["sensor_like"]:
            score = min(1.0, score + 0.15)
        score = round(score, 3)

        notes = []
        if len(outliers) > 0:
            notes.append(f"Detected {len(outliers)} localized blocks with noise residual discontinuities in flat regions.")
        if not prnu_analysis["sensor_like"]:
            notes.append("Noise fingerprint does not exhibit the expected PRNU-like sensor structure.")
        if score > 0.4:
            notes.append("High spatial noise inconsistency detected across text/background boundary.")

        srm_summary = self.compute_srm_summary(gray)

        return {
            "layer_name": "Layer 3: Noise Residual & Spatial Consistency",
            "anomaly_score": score,
            "is_anomalous": score >= 0.35,
            "mean_noise_variance": round(mean_var, 3),
            "outlier_blocks": outliers[:8],
            "noise_heatmap_base64": cv2_to_base64(noise_heatmap),
            "srm_analysis": srm_summary,
            "prnu_analysis": {
                "cross_correlation": prnu_analysis["cross_correlation"],
                "fingerprint_strength": prnu_analysis["fingerprint_strength"],
                "sensor_like": prnu_analysis["sensor_like"],
            },
            "dwt_noise_residual": dwt_residual,
            "residual": residual,
            "findings": notes
        }
