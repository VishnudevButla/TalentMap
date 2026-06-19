"""
app/nlp/pdf_parser.py — PDF to Text Extraction

Converts an uploaded PDF resume into a plain text string.

Why we need this:
- ML/NLP models work on text, not binary PDF bytes
- All downstream steps (preprocess, NER, embeddings) depend on this output

Libraries to choose from:
- pdfplumber  → best for text-heavy PDFs, good layout awareness (recommended)
- PyMuPDF     → faster, handles more PDF types
- pypdf       → pure Python, simpler but less accurate on complex layouts

Function:
  extract_text(file_bytes: bytes) → str
  - Takes raw PDF bytes (as received from S3 or the upload)
  - Returns a single string of extracted text
  - Handles multi-page PDFs (concatenates all pages)
  - Should strip excessive whitespace/newlines after extraction

Example output:
  "John Doe | john@email.com | LinkedIn: ...
   Skills: Python, Machine Learning, SQL ...
   Experience: Software Engineer at XYZ Corp (2021–2023) ..."
"""

# import pdfplumber
# import io

# def extract_text(file_bytes: bytes) -> str:
#     # Wrap bytes in a file-like object so pdfplumber can read it
#     # Open with pdfplumber
#     # Loop through each page and extract text
#     # Join all pages into a single string
#     # Return cleaned text
#     pass
