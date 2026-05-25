# Quality Engine Notes

This project uses a deterministic document-restoration pipeline. It avoids generative AI super-resolution by default because generative models can hallucinate or alter letters, digits, equations, and punctuation.

## Pipeline

1. Render PDF pages with PyMuPDF at selected DPI.
2. Classify each page as text, text+diagram, color, cover, or unknown.
3. Estimate and correct skew.
4. Clean outer scanner/book borders.
5. Flatten uneven background with median/Gaussian background estimation and divide normalization.
6. Denoise with OpenCV non-local means.
7. Increase local contrast with CLAHE.
8. Sharpen via unsharp masking.
9. For pure text pages, optionally use Sauvola adaptive binarization.
10. Repair tiny broken strokes and remove tiny speckles.
11. Save pages as lossless PNG and rebuild the PDF with original page dimensions.
12. Optionally add OCR via OCRmyPDF or Tesseract.

## Why not JPEG

JPEG creates compression halos around letters. This is bad for scanned book pages. The builder uses PNG pages inside a PDF for visual fidelity.

## When to avoid binarization

Disable binarization when pages contain:

- thin/faded letters,
- grey diagrams,
- maps/photos,
- colored annotations,
- mathematical graphs where grey antialiasing matters.

Use `Safe Grayscale Book` for those pages.
