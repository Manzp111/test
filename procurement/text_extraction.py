import os
import sys
import django
from procurement.document_processing import extract_text_from_any_pdf, parse_with_ai
from django.core.files.uploadedfile import SimpleUploadedFile



# Add the current directory (backend/) to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Set the correct settings module: settings_package.settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'procured_payment.settings')

django.setup()



def test_extraction():
    # Path to sample.pdf in your procurement app
    pdf_path = os.path.join('procurement', 'sample.pdf')
    
    if not os.path.exists(pdf_path):
        print(f" ERROR: {pdf_path} not found!")
        print("Make sure sample.pdf is in the procurement folder")
        return

    with open(pdf_path, 'rb') as f:
        mock_file = SimpleUploadedFile('sample.pdf', f.read(), content_type='application/pdf')
        
        print("Extracting text from PDF...")
        text = extract_text_from_any_pdf(mock_file)
        print(f" Extracted {len(text)} characters")
        print("First 200 characters:")
        print(repr(text[:200]))

        if not text.strip():
            print(" WARNING: No text extracted! PDF may be scanned image.")
            return

        print("\n Parsing with OpenAI...")
        try:
            data = parse_with_ai(text)
            print("SUCCESS! Extracted ")
            print(data)
        except Exception as e:
            print(f" FAILED: {e}")

if __name__ == "__main__":
    test_extraction()