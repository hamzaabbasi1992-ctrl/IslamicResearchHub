import os, sys, pymupdf
sys.stdout.reconfigure(encoding='utf-8')

KHUTBAT_PDF_DIR = r"F:\کتب\خطبات و مواعظ ۔"

print("=" * 90)
print(" SCANNING ALL PDF FILES IN 'F:\\کتب\\خطبات و مواعظ ۔' FOR DIGITAL TEXT AVAILABILITY")
print("=" * 90)

pdf_files = []
for root, dirs, files in os.walk(KHUTBAT_PDF_DIR):
    for f in files:
        if f.lower().endswith('.pdf'):
            pdf_files.append(os.path.join(root, f))

print(f"Total PDF Files Found: {len(pdf_files)}\n")

digital_text_pdfs = []
scanned_image_pdfs = []

for p in sorted(pdf_files):
    fname = os.path.basename(p)
    rel_dir = os.path.relpath(os.path.dirname(p), KHUTBAT_PDF_DIR)
    folder_tag = f"[{rel_dir}]" if rel_dir != "." else "[Root]"

    try:
        doc = pymupdf.open(p)
        page_count = len(doc)
        if page_count == 0:
            continue

        # Check sample pages (pages 5, 10, 15, 20 if available)
        sample_pages = [i for i in [5, 10, 15, 20, 25] if i < page_count]
        if not sample_pages:
            sample_pages = [0]

        total_text_chars = 0
        sample_text = ""
        for sp in sample_pages:
            t = doc[sp].get_text().strip()
            total_text_chars += len(t)
            if not sample_text and len(t) > 30:
                sample_text = t[:100]

        doc.close()

        # Check if text is genuine content or just website watermark (like "www.besturdubooks...")
        is_watermark_only = False
        if total_text_chars > 0 and total_text_chars < 150:
            if "besturdubooks" in sample_text.lower() or "marfat" in sample_text.lower() or "islamicbook" in sample_text.lower():
                is_watermark_only = True

        if total_text_chars > 200 and not is_watermark_only:
            digital_text_pdfs.append((p, page_count, total_text_chars, sample_text, folder_tag))
            print(f"✅ [DIGITAL TEXT]  {folder_tag:25s} {fname[:40]:40s} | {page_count:4d} pgs | Text: {sample_text[:50]}...")
        else:
            scanned_image_pdfs.append((p, page_count, folder_tag))
            print(f"📷 [SCANNED IMAGE] {folder_tag:25s} {fname[:40]:40s} | {page_count:4d} pgs | (Needs Google Vision OCR)")

    except Exception as e:
        print(f"❌ [ERROR] {folder_tag:25s} {fname[:40]:40s} | Error: {e}")

print("\n" + "=" * 90)
print(f" SUMMARY: {len(digital_text_pdfs)} Digital Text PDFs (Direct Extraction) | {len(scanned_image_pdfs)} Scanned PDFs (Need OCR)")
print("=" * 90)
