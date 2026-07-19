"""
app/nlp/pdf_parser.py — PDF to Text Extraction

Converts an uploaded PDF resume into a plain text string.
"""

import pdfplumber
import io
import re


def extract_text(file_bytes: bytes) -> str:
    """
    Extract text from a PDF's raw bytes.

    Args:
        file_bytes: Raw PDF bytes (e.g. from S3 or an upload).

    Returns:
        A single cleaned string containing text from all pages,
        or an empty string if no text could be extracted.
    """
    if not file_bytes:
        return ""

    pages_text = []

    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            # x_tolerance/y_tolerance help keep words from being
            # split or merged incorrectly on multi-column resumes
            text = page.extract_text(x_tolerance=1, y_tolerance=3)
            if text:
                pages_text.append(text)

    full_text = "\n".join(pages_text)
    return _clean_text(full_text)


def _clean_text(text: str) -> str:
    """Strip excessive whitespace/newlines while preserving line breaks."""
    if not text:
        return ""

    # Collapse runs of spaces/tabs
    text = re.sub(r"[ \t]+", " ", text)
    # Collapse 3+ newlines down to 2 (keep paragraph breaks)
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Strip trailing whitespace on each line
    text = "\n".join(line.strip() for line in text.split("\n"))

    return text.strip()

