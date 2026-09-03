import pymupdf, sys
from google.cloud import vision
from google.oauth2 import service_account
sys.stdout.reconfigure(encoding='utf-8')

CREDS_PATH = r"F:\AI TOOLS N APPS MADE\URDU OCR GOOGLE VISION\urdu ocr google coude vision key\urdu-ocr-503414-fb3d59ab845b.json"
PDF_PATH = r"F:\کتب\خطبات و مواعظ ۔\اسلام اور ہماری زندگی م تقی عثمانی\اسلام اور ہماری زندگی 10 جلدیں م تقی عثمانی.pdf"

credentials = service_account.Credentials.from_service_account_file(CREDS_PATH)
client = vision.ImageAnnotatorClient(credentials=credentials)

doc = pymupdf.open(PDF_PATH)

# Test PDF page 25 (Vol 1 page 25)
pix = doc[24].get_pixmap(dpi=250)
img = vision.Image(content=pix.tobytes("png"))
resp = client.document_text_detection(image=img)
txt = resp.full_text_annotation.text if resp.full_text_annotation else ""

print("=== OCR SAMPLE: ISLAM AUR HAMARI ZINDAGI VOL 1 (PAGE 25) ===")
print(txt[:750])
doc.close()
