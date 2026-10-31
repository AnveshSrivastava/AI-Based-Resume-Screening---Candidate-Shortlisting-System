"""Unit tests for Phase 3: Text extraction from PDF, DOCX, and TXT files."""

import io
import docx
from reportlab.pdfgen import canvas

from src.config import SystemConfig
from src.text_extraction import extract_text_from_file


def _create_sample_pdf(text: str) -> bytes:
    """Helper to generate in-memory valid PDF bytes."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    c.drawString(100, 750, text)
    c.save()
    return buf.getvalue()


def _create_sample_docx(text: str) -> bytes:
    """Helper to generate in-memory valid DOCX bytes."""
    buf = io.BytesIO()
    doc = docx.Document()
    doc.add_paragraph(text)
    doc.save(buf)
    return buf.getvalue()


def test_extract_pdf_valid():
    sample_text = "Software Engineer Resume with Python and Docker"
    pdf_bytes = _create_sample_pdf(sample_text)
    result = extract_text_from_file(pdf_bytes, "resume.pdf")

    assert result.error is None
    assert result.page_count >= 1
    assert "Software Engineer Resume" in result.text


def test_extract_docx_valid():
    sample_text = "Experienced Full Stack Developer in React and Node.js"
    docx_bytes = _create_sample_docx(sample_text)
    result = extract_text_from_file(docx_bytes, "candidate.docx")

    assert result.error is None
    assert result.page_count == 1
    assert "Experienced Full Stack Developer" in result.text


def test_extract_txt_valid():
    txt_bytes = "Data Scientist skilled in Python, Pandas, and SQL.".encode("utf-8")
    result = extract_text_from_file(txt_bytes, "profile.txt")

    assert result.error is None
    assert "Data Scientist" in result.text


def test_extract_empty_file():
    result = extract_text_from_file(b"", "empty.pdf")
    assert result.error is not None
    assert "empty" in result.error.lower()


def test_extract_unsupported_extension():
    result = extract_text_from_file(b"some content", "image.png")
    assert result.error is not None
    assert "unsupported" in result.error.lower()


def test_extract_file_size_limit():
    config = SystemConfig(max_file_size_bytes=100)
    result = extract_text_from_file(b"x" * 500, "large.txt", config=config)
    assert result.error is not None
    assert "exceeds maximum allowed size" in result.error


def test_extract_corrupt_pdf():
    corrupt_bytes = b"%PDF-1.4 corrupt junk not a real pdf %%EOF"
    result = extract_text_from_file(corrupt_bytes, "corrupt.pdf")
    assert result.error is not None
    assert "corrupt" in result.error.lower() or "unable" in result.error.lower()


def test_scanned_pdf_warning():
    # PDF with blank/image-only page and no selectable text
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    c.showPage()  # Empty page
    c.save()
    blank_pdf = buf.getvalue()

    result = extract_text_from_file(blank_pdf, "scanned.pdf")
    assert result.is_scanned_or_unreadable is True
    assert result.warning is not None
    assert "scanned" in result.warning.lower()


def test_docx_with_table():
    buf = io.BytesIO()
    doc = docx.Document()
    doc.add_paragraph("Summary paragraph")
    table = doc.add_table(rows=1, cols=2)
    table.rows[0].cells[0].text = "Skill"
    table.rows[0].cells[1].text = "Python"
    doc.save(buf)

    result = extract_text_from_file(buf.getvalue(), "table.docx")
    assert result.error is None
    assert "Skill | Python" in result.text


def test_pdf_page_limit():
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    for _ in range(5):
        c.drawString(100, 750, "Page content")
        c.showPage()
    c.save()

    config = SystemConfig(max_page_count=2)
    result = extract_text_from_file(buf.getvalue(), "multipage.pdf", config=config)
    assert result.error is not None
    assert "page limit" in result.error.lower()


def test_corrupt_docx():
    result = extract_text_from_file(b"invalid docx zip", "corrupt.docx")
    assert result.error is not None
    assert "corrupt" in result.error.lower()


def test_empty_txt():
    result = extract_text_from_file(b"   \n  \t  ", "empty.txt")
    assert result.is_scanned_or_unreadable is True

