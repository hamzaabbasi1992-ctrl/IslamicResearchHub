import os, sys, glob
sys.stdout.reconfigure(encoding='utf-8')

print("=" * 85)
print(" SEARCHING FOR AITIKAF & SUNDAY BAYANAT TEXT / DOCX / TRANSCRIPTS")
print("=" * 85)

search_dirs = [
    r"E:\KHANQAH",
    r"E:\FUYUZAT E GHAFOOIA COMPLETE FILES فیوضات غفوریہ",
    r"E:\FUYUZAT GHAFOORIA NEW TYPING 2026",
    r"F:\ISLAMIC RESEARCH HUB AI",
    r"F:\کتب",
    r"F:\JUMMA BAYANAT جمعہ و عمومي بیانات",
    r"F:\AI TOOLS N APPS MADE"
]

found_text_docs = []

for sdir in search_dirs:
    if not os.path.exists(sdir): continue
    for root, dirs, files in os.walk(sdir):
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if ext in ['.docx', '.doc', '.txt', '.md', '.pdf', '.inp']:
                f_lower = f.lower()
                if any(k in f_lower for k in ["aitikaf", "atikaf", "اعتکاف", "sunday", "اتوار", "bayan", "بیان", "مجلس", "مواعظ"]):
                    p = os.path.join(root, f)
                    found_text_docs.append(p)

print(f"Total Text / Word Documents Found: {len(found_text_docs)}\n")
for p in sorted(found_text_docs)[:40]:
    print(f"  --> {p}")

if len(found_text_docs) > 40:
    print(f"\n  ... and {len(found_text_docs)-40} more documents")
print("=" * 85)
