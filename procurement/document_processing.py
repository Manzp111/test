import io
import os
from pdf2image import convert_from_bytes
import pytesseract
import pdfplumber
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def extract_text_from_any_pdf(pdf_file):
    """
    Smart extraction: handles both text-based and scanned PDFs
    """
    pdf_file.seek(0)
    content = pdf_file.read()
    
    # METHOD 1: Try text extraction first)
    try:
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            text = "\n".join(page.extract_text() or "" for page in pdf.pages)
            if len(text.strip()) >= 100:  # Good confidence it's text-based
                print(" Using text extraction (pdfplumber)")
                return text
    except Exception as e:
        print(f"Text extraction failed: {e}")
    
    # METHOD 2: try OCR on images
    try:
        print(" Falling back to OCR (scanned PDF detected)")
        images = convert_from_bytes(content)
        ocr_text = ""
        for i, img in enumerate(images):
            print(f"   Processing page {i+1} with OCR...")
            ocr_text += pytesseract.image_to_string(img) + "\n"
        
        if len(ocr_text.strip()) >= 50:
            return ocr_text
        else:
            raise ValueError("OCR produced insufficient text")
            
    except Exception as e:
        print(f"OCR failed: {e}")
        raise ValueError(
            "Could not extract text from document. "
            "Please ensure PDF contains readable text or clear images."
        )

def parse_with_ai(text):
    """Send extracted text to OpenAI for structured parsing"""
    prompt = f"""
    Extract structured data from this proforma invoice. Return ONLY valid JSON:
    {{
        "vendor_name": "string",
        "vendor_address": "string",
        "items": [
            {{"name": "string", "price": number, "quantity": integer}}
        ],
        "total_amount": number,
        "payment_terms": "string"
    }}
    Text: {text[:4000]}
    """
    
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0
    )
    
    result = response.choices[0].message.content.strip()
    if result.startswith("```json"):
        result = result[7:-3]
    
    import json
    return json.loads(result)