# Changelog

## Unreleased

- Refuse calibration and detection outputs that would overwrite supplied observations or images, including hard links and symlinks.

## 0.2.0 — 2026-10-22
- Include the required `.gitignore` in source distributions and verify the unpacked archive in CI.
- Add `measure` for WallGraph polylines and PlanRegions pixel areas, with original-grid validation, independent axis calibration, full evidence and source digests.

## 0.1.0 — 2026-10-09

Initial experimental release. Independent geometry and evidence processing, local CLI and generated demonstration. See the README and validation protocol for supported inputs and limits.
