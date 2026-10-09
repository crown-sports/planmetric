"""Parse complete dimension labels, without guessing units or editing OCR digits."""

from __future__ import annotations

import re
import unicodedata

_NUMBER = r"(?:\d+(?:\.\d+)?|\.\d+)"
_METRIC = re.compile(rf"^({_NUMBER})\s*(mm|cm|m|毫米|厘米|米)\.?$", re.IGNORECASE)
_SINGLE_IMPERIAL = re.compile(rf"^({_NUMBER})\s*(in|inch|inches|ft|foot|feet|['\"])$", re.I)
_FEET_INCHES = re.compile(
    rf"^({_NUMBER})\s*(?:ft|feet|foot|')\s*(?:-\s*)?({_NUMBER})\s*(?:in|inch|inches|\")$",
    re.I,
)
_BARE = re.compile(rf"^{_NUMBER}$")
_FACTORS = {
    "mm": 1.0,
    "毫米": 1.0,
    "cm": 10.0,
    "厘米": 10.0,
    "m": 1000.0,
    "米": 1000.0,
    "in": 25.4,
    "ft": 304.8,
}


class DimensionParseError(ValueError):
    """A label is not an unambiguous positive length."""


def parse_dimension(
    text: str, *, default_unit: str | None = None, allow_unitless: bool = False
) -> float:
    """Return millimeters. Bare numbers require a caller-declared dimension role and unit."""
    label = text.replace("′", "'").replace("’", "'").replace("″", '"')
    label = unicodedata.normalize("NFKC", label).strip()
    metric = _METRIC.fullmatch(label)
    combined = _FEET_INCHES.fullmatch(label)
    imperial = _SINGLE_IMPERIAL.fullmatch(label)
    if metric:
        value = float(metric.group(1)) * _FACTORS[metric.group(2).lower()]
    elif combined:
        inches = float(combined.group(2))
        if inches >= 12:
            raise DimensionParseError("inches_part_out_of_range")
        value = float(combined.group(1)) * 304.8 + inches * 25.4
    elif imperial:
        unit = imperial.group(2).lower()
        factor = 25.4 if unit in ('"', "in", "inch", "inches") else 304.8
        value = float(imperial.group(1)) * factor
    elif _BARE.fullmatch(label):
        if not allow_unitless:
            raise DimensionParseError("unitless_text_requires_dimension_role")
        if default_unit not in _FACTORS:
            raise DimensionParseError("unitless_dimension_requires_default_unit")
        value = float(label) * _FACTORS[default_unit]
    else:
        raise DimensionParseError("not_a_length_label")
    if not 0 < value < float("inf"):
        raise DimensionParseError("dimension_must_be_positive_and_finite")
    return value
