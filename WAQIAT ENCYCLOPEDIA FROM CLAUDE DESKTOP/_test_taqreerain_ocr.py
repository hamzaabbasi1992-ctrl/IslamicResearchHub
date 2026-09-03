import pymupdf, sys
from google.cloud import vision
from google.oauth2 import service_account
sys.stdout.reconfigure(encoding='utf-8')

CREDS_PATH = r"F:\AI TOOLS N APPS MADE\google vision ocr api keys\urdu-ocr-503414-fb3d59ab845b.json"
PDF_PATH = r"F:\کتب\خطبات و مواعظ ۔\اصلاحی تقریریں ۔\اصلاحی تقریریں مع فہرست 9 جلدیں م رفیع عثمانی.pdf"

credentials = service_account.Credentials.from_service_account_file(CREDS_PATH)
client = vision.ImageAnnotatorClient(credentials=credentials)

doc = pymupdf.open(PDF_PATH)

# Test PDF page 50 (Volume 2)
pix = doc[49].get_pixmap(dpi=250)
img = vision.Image(content=pix.tobytes("png"))
resp = client.document_text_detection(image=img)
txt = resp.full_text_annotation.text if resp.full_text_annotation else ""

print("=== OCR SAMPLE: ISLAHI TAQREERAIN (PAGE 50) ===")
print(txt[:750])
doc.close()
