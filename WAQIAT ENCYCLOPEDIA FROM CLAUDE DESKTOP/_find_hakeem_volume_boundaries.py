import pymupdf, sys, os
from google.cloud import vision
from google.oauth2 import service_account
sys.stdout.reconfigure(encoding='utf-8')

CREDS_PATH = r"F:\AI TOOLS N APPS MADE\URDU OCR GOOGLE VISION\urdu ocr google coude vision key\urdu-ocr-503414-fb3d59ab845b.json"
PDF_PATH = r"F:\کتب\خطبات و مواعظ ۔\خطبات حکیم العصر\خطبات حکیم العصر 12 جلدیں م مجید لدھیانوی.pdf"

credentials = service_account.Credentials.from_service_account_file(CREDS_PATH)
client = vision.ImageAnnotatorClient(credentials=credentials)

doc = pymupdf.open(PDF_PATH)
total_pages = len(doc)
print(f"Total pages: {total_pages}")

# Let's check candidate start pages around intervals of 300-380 pages
candidate_ranges = [
    (1, "جلد اول"),
    (300, 360, "جلد دوم"),
    (650, 720, "جلد سوم"),
    (980, 1060, "جلد چہارم"),
    (1300, 1400, "جلد پنجم"),
    (1650, 1750, "جلد ششم"),
    (2000, 2100, "جلد ہفتم"),
    (2350, 2450, "جلد ہشتم"),
    (2700, 2800, "جلد نہم"),
    (3050, 3180, "جلد دہم"),
    (3400, 3550, "جلد یازدہم"),
    (3800, 3950, "جلد دوازدہم")
]

print("Scanning for Volume Title Pages across 4,227 pages...")

# We can check bookmarks in PyMuPDF first! Does the PDF have a table of contents / outlines?
toc = doc.get_toc()
print(f"PyMuPDF Outlines / Bookmarks count: {len(toc)}")
if toc:
    for item in toc[:25]:
        print("  Bookmark:", item)

doc.close()
