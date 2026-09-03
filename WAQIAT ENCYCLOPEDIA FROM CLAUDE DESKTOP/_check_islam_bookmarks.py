import pymupdf, sys
sys.stdout.reconfigure(encoding='utf-8')

pdf_path = r"F:\کتب\خطبات و مواعظ ۔\اسلام اور ہماری زندگی م تقی عثمانی\اسلام اور ہماری زندگی 10 جلدیں م تقی عثمانی.pdf"
doc = pymupdf.open(pdf_path)
print(f"Total pages in PDF: {len(doc)}")

toc = doc.get_toc()
print(f"Total Outlines / Bookmarks: {len(toc)}")
for item in toc:
    lvl, title, pno = item
    if lvl == 1 or 'جلد' in title or 'ISLAM' in title.upper() or 'VOL' in title.upper():
        print(f"  Bookmark [Lvl {lvl}]: {title:40s} -> Page {pno}")

doc.close()
