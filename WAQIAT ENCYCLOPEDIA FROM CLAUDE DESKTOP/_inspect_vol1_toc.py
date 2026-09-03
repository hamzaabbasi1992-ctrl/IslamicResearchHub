import pymupdf, sys, os
from google.cloud import vision
from google.oauth2 import service_account
sys.stdout.reconfigure(encoding='utf-8')

CREDS_PATH = r"F:\AI TOOLS N APPS MADE\URDU OCR GOOGLE VISION\urdu ocr google coude vision key\urdu-ocr-503414-fb3d59ab845b.json"
PDF_PATH = r"F:\کتب\خطبات و مواعظ ۔\خطبات حکیم العصر\خطبات حکیم العصر 12 جلدیں م مجید لدھیانوی.pdf"

doc = pymupdf.open(PDF_PATH)
total_p = len(doc)
print(f"Total pages in PDF: {total_p}")

# Let's inspect pages 6 to 15 to check the Table of Contents of Volume 1
credentials = service_account.Credentials.from_service_account_file(CREDS_PATH)
client = vision.ImageAnnotatorClient(credentials=credentials)

for p in [6, 7, 8, 9, 10]:
    pix = doc[p - 1].get_pixmap(dpi=150)
    image = vision.Image(content=pix.tobytes("png"))
    resp = client.document_text_detection(image=image)
    txt = resp.full_text_annotation.text if resp.full_text_annotation else ""
    print(f"--- PAGE {p} ---")
    lines = [l.strip() for l in txt.split('\n') if l.strip()]
    for l in lines[:10]:
        print(" ", l)
    print()

doc.close()
