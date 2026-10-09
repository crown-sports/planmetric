"""Local OCR and conservative orthogonal marked-line detection adapters."""

from __future__ import annotations

import csv
import io
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from .domain import DimensionSpan, DimensionText, Point


class AdapterError(RuntimeError):
    """A local dependency or input failed; no cloud fallback is performed."""


@dataclass(frozen=True)
class TesseractOCR:
    executable: str = "tesseract"
    language: str = "eng"
    page_segmentation: int = 11
    timeout_seconds: float = 30

    def recognize(self, image_path: Path) -> tuple[DimensionText, ...]:
        executable = shutil.which(self.executable)
        if executable is None:
            raise AdapterError(
                "Tesseract executable unavailable. Install it locally or provide "
                "external OCR observations; PlanMetric does not download OCR models."
            )
        if self.page_segmentation not in (3, 6, 11, 12):
            raise ValueError("Supported Tesseract page segmentation modes are 3, 6, 11 and 12")
        if not np.isfinite(self.timeout_seconds) or self.timeout_seconds <= 0:
            raise ValueError("OCR timeout must be positive and finite")
        path = Path(image_path).resolve()
        if not path.is_file():
            raise AdapterError(f"Image does not exist: {image_path}")
        command = [
            executable,
            str(path),
            "stdout",
            "-l",
            self.language,
            "--psm",
            str(self.page_segmentation),
            "tsv",
        ]
        try:
            completed = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=self.timeout_seconds,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise AdapterError(f"Local Tesseract failed: {exc}") from exc
        if completed.returncode:
            raise AdapterError(f"Local Tesseract failed: {completed.stderr.strip()}")
        return self.parse_tsv(completed.stdout)

    @staticmethod
    def parse_tsv(content: str) -> tuple[DimensionText, ...]:
        """Join nearby tokens on the same OCR line, preserving units and room prefixes."""
        groups: dict[tuple[str, ...], list[dict]] = {}
        required = {
            "level",
            "page_num",
            "block_num",
            "par_num",
            "line_num",
            "left",
            "top",
            "width",
            "height",
            "conf",
            "text",
        }
        reader = csv.DictReader(io.StringIO(content), delimiter="\t")
        if not required.issubset(reader.fieldnames or []):
            raise AdapterError("Tesseract returned an invalid TSV header")
        for row in reader:
            if row["level"] != "5" or not row["text"].strip():
                continue
            try:
                x, y, w, h = (float(row[name]) for name in ("left", "top", "width", "height"))
                confidence = float(row["conf"]) / 100
                if (
                    not np.isfinite([x, y, w, h, confidence]).all()
                    or w <= 0
                    or h <= 0
                    or not 0 <= confidence <= 1
                ):
                    raise ValueError
            except (TypeError, ValueError) as exc:
                raise AdapterError("Tesseract returned an invalid word observation") from exc
            key = tuple(row[name] for name in ("page_num", "block_num", "par_num", "line_num"))
            groups.setdefault(key, []).append(
                {"text": row["text"].strip(), "box": (x, y, x + w, y + h), "confidence": confidence}
            )
        result: list[DimensionText] = []
        for key in sorted(groups):
            words = sorted(groups[key], key=lambda word: word["box"][0])
            runs: list[list[dict]] = []
            for word in words:
                if runs:
                    previous = runs[-1][-1]
                    gap = word["box"][0] - previous["box"][2]
                    height = max(
                        word["box"][3] - word["box"][1], previous["box"][3] - previous["box"][1]
                    )
                    if gap <= max(8, 0.8 * height):
                        runs[-1].append(word)
                        continue
                runs.append([word])
            for index, run in enumerate(runs):
                identifier = "ocr-" + "-".join(key) + f"-{index}"
                box = (
                    min(word["box"][0] for word in run),
                    min(word["box"][1] for word in run),
                    max(word["box"][2] for word in run),
                    max(word["box"][3] for word in run),
                )
                result.append(
                    DimensionText(
                        identifier,
                        " ".join(word["text"] for word in run),
                        box,
                        confidence=min(word["confidence"] for word in run),
                        role="unknown",
                    )
                )
        return tuple(result)


@dataclass(frozen=True)
class OrthogonalTickDetector:
    """Find thin continuous lines with perpendicular endpoint marks on both sides.

    Supports upright orthogonal drawings with tick/cross endpoints. Arrow-only,
    curved, broken, perspective-distorted or rotated dimension lines need an
    external detector. Its pixel thresholds are explicit and resolution-dependent.
    """

    min_length: int = 60
    max_line_width: int = 3
    dark_threshold: int = 160
    tick_min_extent: int = 5
    tick_max_extent: int = 10
    endpoint_tolerance: int = 2

    def detect(self, image_path: Path) -> tuple[DimensionSpan, ...]:
        gray = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
        if gray is None:
            raise AdapterError(f"Cannot read image: {image_path}")
        return self.detect_array(gray)

    def detect_array(self, gray: np.ndarray) -> tuple[DimensionSpan, ...]:
        if (
            self.min_length < 3
            or self.max_line_width < 1
            or not 0 <= self.dark_threshold <= 255
            or self.tick_min_extent < 1
            or self.tick_max_extent < self.tick_min_extent
            or self.endpoint_tolerance < 0
        ):
            raise ValueError("Invalid marked-line detector settings")
        if gray.dtype != np.uint8 or gray.ndim != 2:
            raise ValueError("Detector input must be a uint8 grayscale image")
        ink = (gray <= self.dark_threshold).astype(np.uint8)
        found: list[tuple[str, Point, Point]] = []
        for axis, kernel in (("x", (self.min_length, 1)), ("y", (1, self.min_length))):
            opened = cv2.morphologyEx(
                ink, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, kernel)
            )
            contours, _ = cv2.findContours(opened, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for contour in contours:
                x, y, width, height = cv2.boundingRect(contour)
                if axis == "x":
                    if height > self.max_line_width:
                        continue
                    p1, p2 = (
                        Point(x, y + (height - 1) / 2),
                        Point(x + width - 1, y + (height - 1) / 2),
                    )
                else:
                    if width > self.max_line_width:
                        continue
                    p1, p2 = (
                        Point(x + (width - 1) / 2, y),
                        Point(x + (width - 1) / 2, y + height - 1),
                    )
                if self._marked(ink, p1, axis) and self._marked(ink, p2, axis):
                    p1 = self._refine_endpoint(ink, p1, axis)
                    p2 = self._refine_endpoint(ink, p2, axis)
                    found.append((axis, p1, p2))
        found.sort(
            key=lambda candidate: (
                candidate[0],
                candidate[1].x,
                candidate[1].y,
                candidate[2].x,
                candidate[2].y,
            )
        )
        return tuple(
            DimensionSpan(f"detected-{axis}-{index:04d}", p1, p2)
            for index, (axis, p1, p2) in enumerate(found)
        )

    def _refine_endpoint(self, ink: np.ndarray, point: Point, axis: str) -> Point:
        # Morphological bounding boxes include stroke thickness and an even-kernel
        # anchor offset. Measure the center of the perpendicular tick itself.
        x, y = int(round(point.x)), int(round(point.y))
        height, width = ink.shape
        scores: list[tuple[int, int]] = []
        for offset in range(-self.endpoint_tolerance - 2, self.endpoint_tolerance + 3):
            score = 0
            for sign in (-1, 1):
                for extent in range(self.tick_min_extent, self.tick_max_extent + 1):
                    px, py = (
                        (x + offset, y + sign * extent)
                        if axis == "x"
                        else (x + sign * extent, y + offset)
                    )
                    if 0 <= px < width and 0 <= py < height:
                        score += int(ink[py, px])
            scores.append((offset, score))
        maximum = max(score for _, score in scores)
        positions = [offset for offset, score in scores if score == maximum]
        center = float(np.mean(positions))
        return Point(x + center, point.y) if axis == "x" else Point(point.x, y + center)

    def _marked(self, ink: np.ndarray, point: Point, axis: str) -> bool:
        x, y = int(round(point.x)), int(round(point.y))
        height, width = ink.shape
        for sign in (-1, 1):
            pixels = []
            for extent in range(self.tick_min_extent, self.tick_max_extent + 1):
                for offset in range(-self.endpoint_tolerance, self.endpoint_tolerance + 1):
                    px, py = (
                        (x + offset, y + sign * extent)
                        if axis == "x"
                        else (x + sign * extent, y + offset)
                    )
                    if 0 <= px < width and 0 <= py < height:
                        pixels.append(ink[py, px])
            if not pixels or not any(pixels):
                return False
        return True
