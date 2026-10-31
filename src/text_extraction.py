"""In-memory text extraction module supporting PDF, DOCX, and TXT files.

Processes documents entirely in memory without writing to disk.
Enforces file size and page count limits, handles corrupt, encrypted, or empty files gracefully,
and triggers an optional OCR fallback or scanned/unreadable warning when text extraction yields nothing.
"""

from __future__ import annotations

import io
import logging
from dataclasses import dataclass
from typing import Optional, Tuple

import docx
import pdfplumber

from src.config import SystemConfig


logger = logging.getLogger(__name__)


@dataclass
class ExtractionResult:
    """Encapsulates the result of text extraction from an in-memory document."""

    filename: str
    text: str
    page_count: int
    is_scanned_or_unreadable: bool = False
    warning: Optional[str] = None
    error: Optional[str] = None


def extract_text_from_file(
    file_bytes: bytes,
    filename: str,
    config: Optional[SystemConfig] = None,
) -> ExtractionResult:
    """Extract text from an in-memory file buffer (PDF, DOCX, or TXT).

    Args:
        file_bytes: Raw bytes of the document.
        filename: Original filename (used for extension detection and reporting).
        config: System limits and feature flags (size, pages, OCR).

    Returns:
        ExtractionResult containing extracted text, page count, and status flags.
    """
    cfg = config or SystemConfig()
    lower_name = filename.lower().strip()

    # File size validation
    if len(file_bytes) == 0:
        return ExtractionResult(
            filename=filename,
            text="",
            page_count=0,
            error="File is empty (0 bytes).",
        )

    if len(file_bytes) > cfg.max_file_size_bytes:
        size_mb = len(file_bytes) / (1024 * 1024)
        limit_mb = cfg.max_file_size_bytes / (1024 * 1024)
        return ExtractionResult(
            filename=filename,
            text="",
            page_count=0,
            error=f"File exceeds maximum allowed size ({size_mb:.1f} MB > {limit_mb:.1f} MB).",
        )

    # Route based on extension
    if lower_name.endswith(".pdf"):
        return _extract_pdf(file_bytes, filename, cfg)
    elif lower_name.endswith(".docx"):
        return _extract_docx(file_bytes, filename, cfg)
    elif lower_name.endswith(".txt"):
        return _extract_txt(file_bytes, filename, cfg)
    else:
        return ExtractionResult(
            filename=filename,
            text="",
            page_count=0,
            error=f"Unsupported file format '{filename.split('.')[-1]}'. Only PDF, DOCX, and TXT are supported.",
        )


def _extract_pdf(file_bytes: bytes, filename: str, cfg: SystemConfig) -> ExtractionResult:
    """Extract text from PDF bytes using pdfplumber with OCR fallback."""
    extracted_pages: list[str] = []
    stream = io.BytesIO(file_bytes)

    try:
        with pdfplumber.open(stream) as pdf:
            page_count = len(pdf.pages)
            if page_count == 0:
                return ExtractionResult(
                    filename=filename,
                    text="",
                    page_count=0,
                    error="PDF document contains zero pages.",
                )

            if page_count > cfg.max_page_count:
                return ExtractionResult(
                    filename=filename,
                    text="",
                    page_count=page_count,
                    error=f"PDF document exceeds page limit ({page_count} > {cfg.max_page_count} pages).",
                )

            for idx, page in enumerate(pdf.pages):
                page_text = page.extract_text() or ""
                extracted_pages.append(page_text.strip())

    except Exception as err:
        logger.warning("Failed or corrupt/encrypted PDF '%s': %s", filename, err)
        return ExtractionResult(
            filename=filename,
            text="",
            page_count=0,
            error=f"Corrupt or unreadable PDF file: {str(err)}",
        )

    full_text = "\n\n".join(extracted_pages).strip()

    # Check for empty or scanned PDF
    if not full_text or len(full_text) < 25:
        # Check if OCR is enabled and dependencies are available
        if cfg.enable_ocr:
            ocr_text, ocr_err = _attempt_ocr(file_bytes)
            if ocr_text:
                return ExtractionResult(
                    filename=filename,
                    text=ocr_text,
                    page_count=len(extracted_pages),
                    is_scanned_or_unreadable=False,
                    warning="Text extracted via OCR fallback from image/scanned document.",
                )
            logger.info("OCR failed or produced no text: %s", ocr_err)

        return ExtractionResult(
            filename=filename,
            text="",
            page_count=len(extracted_pages),
            is_scanned_or_unreadable=True,
            warning="Scanned or image-only PDF: no selectable text found.",
        )

    return ExtractionResult(
        filename=filename,
        text=full_text,
        page_count=len(extracted_pages),
    )


def _extract_docx(file_bytes: bytes, filename: str, cfg: SystemConfig) -> ExtractionResult:
    """Extract text from DOCX bytes using python-docx."""
    stream = io.BytesIO(file_bytes)
    try:
        doc = docx.Document(stream)
        paragraphs: list[str] = [p.text for p in doc.paragraphs if p.text.strip()]

        # Also extract table text
        for table in doc.tables:
            for row in table.rows:
                row_text = " | ".join(cell.text.strip() for cell in row.cells if cell.text.strip())
                if row_text:
                    paragraphs.append(row_text)

        full_text = "\n".join(paragraphs).strip()
        if not full_text:
            return ExtractionResult(
                filename=filename,
                text="",
                page_count=1,
                is_scanned_or_unreadable=True,
                warning="DOCX document contains no readable text content.",
            )

        return ExtractionResult(
            filename=filename,
            text=full_text,
            page_count=1,
        )

    except Exception as err:
        logger.warning("Failed to parse DOCX '%s': %s", filename, err)
        return ExtractionResult(
            filename=filename,
            text="",
            page_count=0,
            error=f"Corrupt or invalid DOCX document: {str(err)}",
        )


def _extract_txt(file_bytes: bytes, filename: str, cfg: SystemConfig) -> ExtractionResult:
    """Extract text from raw TXT bytes using standard encodings."""
    text = ""
    for enc in ("utf-8", "utf-8-sig", "latin-1", "cp1252"):
        try:
            text = file_bytes.decode(enc)
            break
        except UnicodeDecodeError:
            continue

    text = text.strip()
    if not text:
        return ExtractionResult(
            filename=filename,
            text="",
            page_count=1,
            is_scanned_or_unreadable=True,
            warning="TXT file contains no text.",
        )

    return ExtractionResult(
        filename=filename,
        text=text,
        page_count=1,
    )


def _attempt_ocr(file_bytes: bytes) -> Tuple[str, Optional[str]]:
    """Attempt OCR using pdf2image and pytesseract if installed."""
    try:
        import pdf2image
        import pytesseract

        images = pdf2image.convert_from_bytes(file_bytes)
        ocr_pages = [pytesseract.image_to_string(img) for img in images]
        full_text = "\n\n".join(ocr_pages).strip()
        return full_text, None
    except ImportError:
        return "", "pytesseract or pdf2image is not installed."
    except Exception as err:
        return "", f"OCR processing failed: {str(err)}"
