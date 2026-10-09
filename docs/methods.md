# Methods, design and evidence

A pixel coordinate becomes a physical measurement only after valid metric evidence establishes its scale. A written `1:100` print scale is not enough after an image has been resized; PlanMetric works with dimension lengths and their corresponding image spans.

## Processing

1. Parse explicit lengths and units. Area labels and room identifiers are not lengths. Bare numbers require an explicit default unit and dimension-role evidence.
2. Match text boxes to candidate dimension spans using location and orientation costs, with one-to-one assignment. Upstream OCR and span extraction are replaceable observations.
3. For each axis, enumerate scale hypotheses from matched lengths, collect consistent evidence and fit the supported set. Record residuals and every rejected observation. Separate axes expose unequal image resizing.
4. Refuse conversion when a required axis lacks supported evidence or has conflicting alternatives. Convert an area using both axis scales; one-axis calibration cannot establish area.

The engineering contribution is the combination of constrained assignment, independent evidence counting, per-axis calibration and explicit rejection states. No new foundational algorithm or peer-reviewed superiority is claimed. Failure states and observed residuals are not calibrated probabilities.

## References

- Fischler and Bolles, 1981, [Random Sample Consensus](https://www.sri.com/wp-content/uploads/2021/12/ransac-publication.pdf). The consensus principle motivates rejecting gross errors; our scalar hypothesis search is deterministic and is not a reproduction of the paper's location-determination experiments.
- SciPy, [linear_sum_assignment](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.linear_sum_assignment.html): the library solves the assignment step using its documented algorithm.
- Tesseract, [command-line usage](https://tesseract-ocr.github.io/tessdoc/Command-Line-Usage.html): the optional adapter reads local TSV observations. It does not bundle OCR models or invoke a cloud service.

A related [floor-plan-scale-engine](https://github.com/pradhankukiran/floor-plan-scale-engine) also addresses OCR-to-geometry scale estimation. It was reviewed as related work, not copied. Our release boundary and actual validation are recorded separately.
