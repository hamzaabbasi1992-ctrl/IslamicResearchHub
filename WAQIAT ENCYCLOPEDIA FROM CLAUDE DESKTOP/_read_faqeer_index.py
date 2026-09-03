import pymupdf, sys
sys.stdout.reconfigure(encoding='utf-8')

index_pdf = r"F:\کتب\خطبات و مواعظ ۔\خطباتِ فقیر ۔\خطبات فقیر مع فہرست 43 جلدیں مکمل مع فہرست.pdf"
doc = pymupdf.open(index_pdf)
print(f"Total Pages in Index PDF: {len(doc)}")
for i, page in enumerate(doc):
    print(f"\n--- INDEX PAGE {i+1} ---")
    print(page.get_text())
doc.close()
