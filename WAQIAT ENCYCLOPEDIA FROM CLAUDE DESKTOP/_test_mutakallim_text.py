import pymupdf, sys
sys.stdout.reconfigure(encoding='utf-8')

pdf_path = r"F:\کتب\خطبات و مواعظ ۔\خطبات متکلم اسلام 3 جلدیں گھمن.pdf"
doc = pymupdf.open(pdf_path)

print(f"Total Pages in 'خطبات متکلم اسلام': {len(doc)}")
print("\n--- SAMPLE PAGE 15 TEXT ---")
print(doc[15].get_text()[:600])

print("\n--- SAMPLE PAGE 50 TEXT ---")
print(doc[50].get_text()[:600])
doc.close()
