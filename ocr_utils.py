import os
import pdfplumber
import fitz  # PyMuPDF
from PIL import Image
from google import genai

# ── Gemini Configuration ────────────────────────────────
# Get your API key from https://aistudio.google.com/
GEMINI_API_KEY = "YOUR_GEMINI_API_KEY"
client = genai.Client(api_key="")

def extract_with_gemini(image_list):
    """
    Sends processed images to Gemini for OCR extraction.
    """
    prompt = "Extract all text from these images exactly as it appears. Maintain layout and tables if present."
    
    # We can send multiple pages at once to Gemini
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=[prompt, *image_list]
    )
    return response.text

# ── Main extraction function ────────────────────────────
def extract_text(file_path):
    if not os.path.exists(file_path):
        return "⚠️ File not found."

    text = ""
    file_ext = file_path.lower()

    # ── 1. Try Native PDF Text Extraction (Fast & Free)
    if file_ext.endswith(".pdf"):
        try:
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    extracted = page.extract_text()
                    if extracted:
                        text += extracted + "\n"
            
            # If we found substantial text, return it
            if len(text.strip()) > 50: 
                return text.strip()
        except Exception as e:
            print(f"Native extraction failed: {e}")

    # ── 2. Use Gemini AI for Scanned PDFs and Images
    try:
        images_to_process = []

        if file_ext.endswith(".pdf"):
            doc = fitz.open(file_path)
            for page in doc:
                # Render page to image for Gemini
                pix = page.get_pixmap(dpi=300)
                img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
                images_to_process.append(img)
            doc.close()
        else:
            # It's a direct image file
            img = Image.open(file_path)
            images_to_process.append(img)

        if images_to_process:
            # Gemini handles the "fixing" and "cleaning" automatically
            final_text = extract_with_gemini(images_to_process)
            return final_text

    except Exception as e:
        return f"⚠️ Gemini OCR failed: {e}"

    return "⚠️ Text extraction failed."
