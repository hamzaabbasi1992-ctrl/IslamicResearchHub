import sys, os, pymupdf, time
from google.cloud import vision
from google.oauth2 import service_account
sys.stdout.reconfigure(encoding='utf-8')

CREDS_PATH = r"F:\AI TOOLS N APPS MADE\URDU OCR GOOGLE VISION\urdu ocr google coude vision key\urdu-ocr-503414-fb3d59ab845b.json"
PDF_PATH = r"F:\کتب\خطبات و مواعظ ۔\خطباتِ علی میاں ۔\خطبات علی میاں 7 جلدین.pdf"

print("=" * 85)
print(" TESTING GOOGLE CLOUD VISION API WITH KHUTBAT ALI MIAN")
print("=" * 85)

if not os.path.exists(CREDS_PATH):
    print(f"❌ Credentials file not found: {CREDS_PATH}")
    sys.exit(1)

credentials = service_account.Credentials.from_service_account_file(CREDS_PATH)
client = vision.ImageAnnotatorClient(credentials=credentials)

doc = pymupdf.open(PDF_PATH)
test_page_idx = 14 # Page 15
page = doc[test_page_idx]
pix = page.get_pixmap(dpi=300)
img_bytes = pix.tobytes("png")
doc.close()

print(f"Rendered Page {test_page_idx + 1} at 300 DPI, Size: {len(img_bytes)} bytes")

start_t = time.time()
image = vision.Image(content=img_bytes)
response = client.document_text_detection(image=image)
elapsed = time.time() - start_t

text = response.full_text_annotation.text if response.full_text_annotation else ""
print(f"✅ Vision API Response in {elapsed:.2f}s | Extracted {len(text)} characters!")
print("\n--- SAMPLE EXTRACTED TEXT (FIRST 300 CHARS) ---")
print(text[:300])
print("=" * 85)
