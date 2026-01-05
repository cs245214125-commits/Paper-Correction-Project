import os
import pdfplumber
import fitz  # PyMuPDF
from PIL import Image
import pytesseract

def extract_text(file_path):
    """
    Extracts text from PDF or image.
    - Tries pdfplumber first (for text PDFs)
    - Falls back to PyMuPDF
    - If both fail, uses OCR (pytesseract) for images / scanned PDFs
    """
    if not os.path.exists(file_path):
        return ""

    text = ""
    file_path_lower = file_path.lower()

    # ── 1. pdfplumber for text-based PDFs ─────────
    if file_path_lower.endswith(".pdf"):
        try:
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n\n"
            if text.strip():
                return text.strip()
        except Exception as e:
            print(f"pdfplumber failed: {e}")

    # ── 2. PyMuPDF fallback ─────────
    if file_path_lower.endswith(".pdf"):
        try:
            doc = fitz.open(file_path)
            for page in doc:
                text += page.get_text("text") + "\n\n"
            doc.close()
            if text.strip():
                return text.strip()
        except Exception as e:
            print(f"PyMuPDF failed: {e}")

    # ── 3. OCR for images / scanned PDFs ─────────
    try:
        img = Image.open(file_path)
        text = pytesseract.image_to_string(img)
        if text.strip():
            return text.strip()
    except Exception as e:
        print(f"OCR failed: {e}")

    # ── 4. Nothing extracted
    return (
        "┌───────────────────────────────────────────┐\n"
        "│ Could not extract text.                    │\n"
        "│ This is likely a scanned / image-based    │\n"
        "│ document. Use OCR (Tesseract / EasyOCR).  │\n"
        "└───────────────────────────────────────────┘"
    )
