# Provenance and external assets

The package was independently implemented around text/span observations, matching, scale consensus and conversion contracts. An earlier private application contained a cloud-OCR scale prototype; its implementation, cloud services, business APIs, private inputs and Git history are not redistributed.

RANSAC-style consensus is an established model-fitting approach. This implementation enumerates scale hypotheses deterministically rather than claiming a new RANSAC algorithm. Linear assignment is provided by SciPy; NumPy, OpenCV, Pillow and optional Tesseract retain their own licenses. See [methods and references](docs/methods.md).

The single public `examples/demo.png` contains original code-generated geometry and actual library results. It is not copied from a real drawing or dataset. No real drawings, annotations, pretrained models or weights are included. Generated observation tests do not establish real-image OCR accuracy.
