import pymupdf, sys
sys.stdout.reconfigure(encoding='utf-8')

pdf_path = r"F:\کتب\خطبات و مواعظ ۔\اصلاحی تقریریں ۔\اصلاحی تقریریں مع فہرست 9 جلدیں م رفیع عثمانی.pdf"
doc = pymupdf.open(pdf_path)

toc = doc.get_toc()
print(f"Total pages: {len(doc)}")
print("Finding Volume Start Points in Bookmarks:")

vol_starts = {}
for lvl, title, pno in toc:
    for v in range(1, 10):
        if f"VOL_{v}" in title.upper() or f"VOL_0{v}" in title.upper():
            if v not in vol_starts:
                vol_starts[v] = (title, pno)

for v in range(1, 10):
    info = vol_starts.get(v)
    if info:
        print(f"  Vol {v}: {info[0]} -> PDF Page {info[1]}")
    else:
        print(f"  Vol {v}: NOT FOUND")

doc.close()
