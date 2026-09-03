import sys, os, pymupdf, cv2, numpy as np
sys.stdout.reconfigure(encoding='utf-8')

from google.cloud import vision
from google.oauth2 import service_account

# Credentials
CREDS_PATH = r"F:\AI TOOLS N APPS MADE\URDU OCR GOOGLE VISION\urdu ocr google coude vision key\urdu-ocr-503414-fb3d59ab845b.json"
PDF_PATH = r"F:\کتب\خطبات و مواعظ ۔\خطباتِ فقیر ۔\خطبات فقیر 43 جلد مع فہرست.pdf"
OUTPUT_DIR = r"F:\کتب\ocr text books\خطبات فقیر"
os.makedirs(OUTPUT_DIR, exist_ok=True)

print("=" * 80)
print(" TESTING GOOGLE CLOUD VISION OCR ON خطبات فقیر")
print("=" * 80)

# Initialize Client
credentials = service_account.Credentials.from_service_account_file(CREDS_PATH)
client = vision.ImageAnnotatorClient(credentials=credentials)

# Open PDF
doc = pymupdf.open(PDF_PATH)
print(f"Total Pages in PDF: {len(doc)}")

# Test OCR on pages 15, 25, 35 (sermon content)
test_pages = [15, 25, 35]

for pno in test_pages:
    page = doc[pno]
    # Render page to high-res image (300 DPI)
    pix = page.get_pixmap(dpi=300)
    img_bytes = pix.tobytes("png")

    # Call Vision API
    image = vision.Image(content=img_bytes)
    response = client.document_text_detection(image=image)

    if response.error.message:
        print(f"❌ Vision API Error on page {pno}: {response.error.message}")
        continue

    text = response.full_text_annotation.text
    print(f"\n✅ --- PAGE {pno} OCR RESULT ({len(text)} characters) ---")
    print(text[:500])
    print("-" * 60)

doc.close()
print("\nVision OCR Test on خطبات فقیر Completed Successfully!")
