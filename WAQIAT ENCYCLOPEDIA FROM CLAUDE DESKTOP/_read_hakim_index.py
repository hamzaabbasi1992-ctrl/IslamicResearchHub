import pymupdf, sys
sys.stdout.reconfigure(encoding='utf-8')

pdf_path = r"F:\کتب\خطبات و مواعظ ۔\خطباتِ حکیم الاسلام ۔\فهرست خطبات حكيم الاسلام.pdf"
doc = pymupdf.open(pdf_path)
print(f"Total Pages in Index PDF: {len(doc)}")
for i, page in enumerate(doc):
    print(f"\n--- INDEX PAGE {i+1} ---")
    print(page.get_text())
doc.close()
