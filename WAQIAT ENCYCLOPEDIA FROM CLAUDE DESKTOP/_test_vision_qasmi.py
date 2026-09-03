import sys, os, pymupdf, time
from google.cloud import vision
from google.oauth2 import service_account
sys.stdout.reconfigure(encoding='utf-8')

CREDS_PATH = r"F:\AI TOOLS N APPS MADE\URDU OCR GOOGLE VISION\urdu ocr google coude vision key\urdu-ocr-503414-fb3d59ab845b.json"
PDF_PATH = r"F:\کتب\خطبات و مواعظ ۔\خطبات قاسمی\خطبات قاسمی 6 جلدیں مع فہرست م ضیاء القاسمی.pdf"

print("=" * 85)
print(" TESTING GOOGLE CLOUD VISION API OCR ON KHUTBAT QASMI PAGE 27")
print("=" * 85)

credentials = service_account.Credentials.from_service_account_file(CREDS_PATH)
client = vision.ImageAnnotatorClient(credentials=credentials)

doc = pymupdf.open(PDF_PATH)
page = doc[26] # Page 27 (0-indexed 26)
pix = page.get_pixmap(dpi=300)
img_bytes = pix.tobytes("png")
doc.close()

start_t = time.time()
image = vision.Image(content=img_bytes)
response = client.document_text_detection(image=image)
elapsed = time.time() - start_t

text = response.full_text_annotation.text if response.full_text_annotation else ""
print(f"✅ Vision API Response in {elapsed:.2f}s | Extracted {len(text)} characters of pure Unicode Urdu!\n")
print("--- RAW PYMUPDF EXTRACT (SCRAMBLED) ---")
doc = pymupdf.open(PDF_PATH)
print(doc[26].get_text()[:180].replace('\n', ' '))
doc.close()

print("\n--- GOOGLE VISION OCR EXTRACT (CLEAN UNICODE URDU) ---")
print(text[:400])
print("=" * 85)
