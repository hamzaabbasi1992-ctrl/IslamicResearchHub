import pymupdf, sys
sys.stdout.reconfigure(encoding='utf-8')

pdf_path = r"F:\کتب\خطبات و مواعظ ۔\اسلام اور ہماری زندگی م تقی عثمانی\اسلام اور ہماری زندگی 10 جلدیں م تقی عثمانی.pdf"
doc = pymupdf.open(pdf_path)

# Volumes mapping:
VOLUMES_MAP = {
    1: (3392, 1, 345, "اسلام اور ہماری زندگی جلد 1"),
    2: (3465, 346, 682, "اسلام اور ہماری زندگی جلد 2"),
    3: (3523, 683, 1051, "اسلام اور ہماری زندگی جلد 3"),
    4: (3633, 1052, 1356, "اسلام اور ہماری زندگی جلد 4"),
    5: (3744, 1357, 1701, "اسلام اور ہماری زندگی جلد 5"),
    6: (3854, 1702, 2014, "اسلام اور ہماری زندگی جلد 6"),
    7: (3961, 2015, 2367, "اسلام اور ہماری زندگی جلد 7"),
    8: (4051, 2368, 2720, "اسلام اور ہماری زندگی جلد 8"),
    9: (4146, 2721, 3017, "اسلام اور ہماری زندگی جلد 9"),
    10: (4251, 3018, 3306, "اسلام اور ہماری زندگی جلد 10")
}

print("Checking TOC page ranges in each volume...")
# In each volume, the first 15-20 pages contain TOC.
# Let's inspect bookmarks:
toc = doc.get_toc()
for v in range(1, 11):
    bid, sp, ep, vname = VOLUMES_MAP[v]
    # Check bookmarks within this volume range
    v_bmarks = [b for b in toc if sp <= b[2] <= ep and b[0] <= 2]
    # Find the bookmark corresponding to the first sermon/speech
    print(f"Volume {v} (PDF {sp}..{ep}):")
    for b in v_bmarks[:5]:
        print(f"   {b[1]} -> PDF pg {b[2]}")

doc.close()
