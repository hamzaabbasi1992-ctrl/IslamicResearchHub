import pymupdf, sys
from google.cloud import vision
from google.oauth2 import service_account
sys.stdout.reconfigure(encoding='utf-8')

CREDS_PATH = r"F:\AI TOOLS N APPS MADE\URDU OCR GOOGLE VISION\urdu ocr google coude vision key\urdu-ocr-503414-fb3d59ab845b.json"
PDF_PATH = r"F:\کتب\خطبات و مواعظ ۔\خطبات حکیم العصر\خطبات حکیم العصر 12 جلدیں م مجید لدھیانوی.pdf"

credentials = service_account.Credentials.from_service_account_file(CREDS_PATH)
client = vision.ImageAnnotatorClient(credentials=credentials)

doc = pymupdf.open(PDF_PATH)

# Test pages 57, 58, 59 (where birth and childhood of Holy Prophet ﷺ are narrated)
for p in [57, 58]:
    pix = doc[p - 1].get_pixmap(dpi=250)
    image = vision.Image(content=pix.tobytes("png"))
    resp = client.document_text_detection(image=image)
    txt = resp.full_text_annotation.text if resp.full_text_annotation else ""
    print(f"=== PAGE {p} OCR ===")
    print(txt[:700])
    print()

doc.close()
