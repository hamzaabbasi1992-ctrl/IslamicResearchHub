import os, sys, glob, fitz, sqlite3
sys.stdout.reconfigure(encoding='utf-8')

ali_dir = r"F:\کتب\خطبات و مواعظ ۔\خطباتِ علی میاں ۔"
print("=" * 85)
print(" EXAMINING KHUTBAT ALI MIAN FILES & VOLUMES")
print("=" * 85)

pdf_files = sorted(glob.glob(os.path.join(ali_dir, "*.pdf")) + glob.glob(os.path.join(ali_dir, "**", "*.pdf"), recursive=True))
print(f"Total PDFs found: {len(pdf_files)}")

for p in pdf_files:
    fname = os.path.basename(p)
    try:
        doc = fitz.open(p)
        print(f"  📄 {fname:45s} | Pages: {len(doc):4d}")
        # check if it has text stream or image
        sample = doc[min(15, len(doc)-1)].get_text().strip()
        print(f"     Text stream length at page 15: {len(sample)} chars")
        doc.close()
    except Exception as e:
        print(f"  ❌ Error opening {fname}: {e}")

print("=" * 85)
