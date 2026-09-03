import pymupdf, sys, os
sys.stdout.reconfigure(encoding='utf-8')

pdf_path = r"F:\کتب\خطبات و مواعظ ۔\خطباتِ علی میاں ۔\خطبات علی میاں 7 جلدین.pdf"
doc = pymupdf.open(pdf_path)
print(f"Total Pages in Khutbat Ali Mian: {len(doc)}")

# Check PDF bookmarks / TOC
toc = doc.get_toc()
print(f"Total TOC Bookmarks found: {len(toc)}")
if toc:
    print("--- TOC ENTRIES ---")
    for item in toc[:40]:
        lvl, title, pageno = item
        print(f"  Level {lvl} | Page {pageno:4d} | {title}")

doc.close()
