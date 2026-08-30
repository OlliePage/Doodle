from __future__ import annotations


def render_pdf_preview(pdf_bytes: bytes, dpi: int = 120) -> bytes:
    try:
        import fitz
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("PyMuPDF is required for PDF previews.") from exc

    document = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        page = document.load_page(0)
        scale = max(0.5, dpi / 72.0)
        pixmap = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
        return pixmap.tobytes("png")
    finally:
        document.close()
