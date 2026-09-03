import pymupdf, sys
sys.stdout.reconfigure(encoding='utf-8')

pdf_path = r"F:\کتب\خطبات و مواعظ ۔\اسلام اور ہماری زندگی م تقی عثمانی\اسلام اور ہماری زندگی 10 جلدیں م تقی عثمانی.pdf"
doc = pymupdf.open(pdf_path)

toc = doc.get_toc()
vol_starts = {}
for item in toc:
    lvl, title, pno = item
    for v in range(1, 11):
        target = f"VOL_{v:02d}_PG_001" if v < 10 else f"VOL_{v}_PG_001"
        target_alt = f"VOL_{v}_PG_001"
        target_alt2 = f"VOL_{v}_PG_1"
        t_upper = title.upper()
        if target in t_upper or target_alt in t_upper or target_alt2 in t_upper or f"VOL_{v}_PG_01" in t_upper:
            if v not in vol_starts:
                vol_starts[v] = pno

for v in range(1, 11):
    print(f"Vol {v}: starts at PDF page {vol_starts.get(v)}")

doc.close()
