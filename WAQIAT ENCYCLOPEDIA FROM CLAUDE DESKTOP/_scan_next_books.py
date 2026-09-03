import os, sys, glob, fitz, sqlite3
sys.stdout.reconfigure(encoding='utf-8')

khutbat_dir = r"F:\کتب\خطبات و مواعظ ۔"
print("=" * 85)
print(" SCANNING AVAILABLE KHUTBAT & MAWAIZ SERIES IN F:\\کتب\\خطبات و مواعظ ۔")
print("=" * 85)

subdirs = [os.path.join(khutbat_dir, d) for d in os.listdir(khutbat_dir) if os.path.isdir(os.path.join(khutbat_dir, d))]

for sd in sorted(subdirs):
    bname = os.path.basename(sd)
    pdf_files = glob.glob(os.path.join(sd, "**", "*.pdf"), recursive=True)
    if not pdf_files:
        pdf_files = glob.glob(os.path.join(sd, "*.pdf"))
    
    total_pages = 0
    has_text_stream = False
    sample_text = ""
    
    for pdf_p in pdf_files:
        try:
            doc = fitz.open(pdf_p)
            total_pages += len(doc)
            if len(doc) > 5 and not has_text_stream:
                txt = doc[min(10, len(doc)-1)].get_text()
                if len(txt.strip()) > 100:
                    has_text_stream = True
                    sample_text = txt.strip()[:60]
            doc.close()
        except Exception as e:
            pass
            
    mode = "⚡ DIGITAL TEXT (Direct Ingestion)" if has_text_stream else "📷 SCANNED IMAGE (Needs Vision OCR)"
    print(f"📚 {bname:45s} | {len(pdf_files):2d} PDFs | {total_pages:5d} pgs | {mode}")

print("=" * 85)
