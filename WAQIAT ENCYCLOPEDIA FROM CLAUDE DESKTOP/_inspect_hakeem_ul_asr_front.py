import os, sys, pymupdf
from google.cloud import vision
from google.oauth2 import service_account
sys.stdout.reconfigure(encoding='utf-8')

CREDS_PATH = r"F:\AI TOOLS N APPS MADE\URDU OCR GOOGLE VISION\urdu ocr google coude vision key\urdu-ocr-503414-fb3d59ab845b.json"
PDF_PATH = r"F:\کتب\خطبات و مواعظ ۔\خطبات حکیم العصر\خطبات حکیم العصر 12 جلدیں م مجید لدھیانوی.pdf"

credentials = service_account.Credentials.from_service_account_file(CREDS_PATH)
client = vision.ImageAnnotatorClient(credentials=credentials)

doc = pymupdf.open(PDF_PATH)
print(f"Total Pages: {len(doc)}")

# Check pages 1, 2, 3, 4, 5 with Google Vision OCR to see title, author, and volume mapping
for pno in [1, 2, 3, 4, 5]:
    pix = doc[pno - 1].get_pixmap(dpi=200)
    img_bytes = pix.tobytes("png")
    image = vision.Image(content=img_bytes)
    resp = client.document_text_detection(image=image)
    txt = resp.full_text_annotation.text if resp.full_text_annotation else ""
    print(f"--- PAGE {pno} OCR ---")
    lines = [l.strip() for l in txt.split('\n') if l.strip()]
    for l in lines[:15]:
        print(" ", l)
    print()

doc.close()
