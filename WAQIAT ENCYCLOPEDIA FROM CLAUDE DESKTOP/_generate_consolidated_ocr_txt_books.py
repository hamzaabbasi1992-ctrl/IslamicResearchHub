import os, sys
sys.stdout.reconfigure(encoding='utf-8')

OCR_BASE = r"F:\کتب\ocr text books"

books_info = [
    {
        "dir": "خطبات قاسمی",
        "title": "خطباتِ قاسمی",
        "author": "مولانا ضیاء القاسمؒ",
        "volumes": [
            ("جلد 1", 1, 492),
            ("جلد 2", 493, 1042),
            ("جلد 3", 1043, 1448),
            ("جلد 4", 1449, 1840),
            ("جلد 5", 1841, 2114),
            ("جلد 6", 2115, 2195),
        ]
    },
    {
        "dir": "خطبات علی میاں",
        "title": "خطباتِ علی میاںؒ",
        "author": "مولانا سید ابوالحسن علی ندویؒ",
        "volumes": [
            ("جلد 1", 1, 510),
            ("جلد 2", 511, 878),
            ("جلد 3", 879, 1262),
            ("جلد 4", 1263, 1698),
            ("جلد 5", 1699, 2124),
            ("جلد 6", 2125, 2552),
            ("جلد 7", 2553, 2975),
        ]
    },
    {
        "dir": "خطبات حکیم العصر",
        "title": "خطباتِ حکیم العصر",
        "author": "مولانا عبد المجید لدھیانوی مدظلہ",
        "volumes": [
            ("جلد 1", 1, 380),
            ("جلد 2", 381, 759),
            ("جلد 3", 760, 1144),
            ("جلد 4", 1145, 1444),
            ("جلد 5", 1445, 1793),
            ("جلد 6", 1794, 2167),
            ("جلد 7", 2168, 2521),
            ("جلد 8", 2522, 2807),
            ("جلد 9", 2808, 3153),
            ("جلد 10", 3154, 3466),
            ("جلد 11", 3467, 3823),
            ("جلد 12", 3824, 4227),
        ]
    }
]

print("=" * 85)
print(" GENERATING CONSOLIDATED COMPLETE BOOK TXT FILES FROM OCR PAGES")
print("=" * 85)

for b in books_info:
    book_folder = os.path.join(OCR_BASE, b["dir"])
    pages_dir = os.path.join(book_folder, "pages")
    if not os.path.exists(pages_dir): continue

    print(f"\n📚 Processing Book: {b['title']} ({b['author']})...")
    master_txt_path = os.path.join(book_folder, f"{b['title']} (مکمل کتا ب).txt")
    
    with open(master_txt_path, "w", encoding="utf-8") as master_f:
        master_f.write(f"=== {b['title']} — {b['author']} ===\n")
        master_f.write(f"مکمل متون برآمد شدہ از گوگل کلاؤڈ وژن OCR\n\n")

        for vname, sp, ep in b["volumes"]:
            vol_txt_path = os.path.join(book_folder, f"{b['title']} - {vname}.txt")
            with open(vol_txt_path, "w", encoding="utf-8") as vol_f:
                vol_f.write(f"═══ {b['title']} — {vname} (صفحات {sp} تا {ep}) ═══\n\n")
                master_f.write(f"\n\n{'='*60}\n═══ {b['title']} — {vname} ═══\n{'='*60}\n\n")

                for p in range(sp, ep + 1):
                    pfile = os.path.join(pages_dir, f"page_{p:04d}.txt")
                    content = ""
                    if os.path.exists(pfile):
                        with open(pfile, "r", encoding="utf-8") as pf:
                            content = pf.read().strip()
                    
                    page_header = f"\n\n--- [صفحہ نمبر: {p}] ---\n"
                    vol_f.write(page_header + content)
                    master_f.write(page_header + content)

            print(f"   ✅ Saved: {os.path.basename(vol_txt_path)}")

    master_size_mb = os.path.getsize(master_txt_path) / (1024 * 1024)
    print(f"   🏆 Saved Master File: {os.path.basename(master_txt_path)} ({master_size_mb:.2f} MB)")

print("\n" + "=" * 85)
print(" ALL CONSOLIDATED TXT FILES SAVED SUCCESSFULLY!")
print("=" * 85)
