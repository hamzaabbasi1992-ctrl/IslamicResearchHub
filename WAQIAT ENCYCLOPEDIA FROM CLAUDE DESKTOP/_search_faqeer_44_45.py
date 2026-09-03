import os, sys, glob
sys.stdout.reconfigure(encoding='utf-8')

print("=" * 80)
print(" SEARCHING FOR KHUTBAT-E-FAQEER VOLUMES 44 & 45 ACROSS DIRECTORIES")
print("=" * 80)

search_roots = [
    r"F:\کتب",
    r"F:\ISLAMIC RESEARCH HUB AI",
    r"F:\AI TOOLS N APPS MADE",
    r"D:",
    r"E:"
]

found_files = []

for root_dir in search_roots:
    if not os.path.exists(root_dir): continue
    print(f"Searching in: {root_dir} ...")
    for r, dirs, files in os.walk(root_dir):
        for f in files:
            f_lower = f.lower()
            if "فقیر" in f or "faqeer" in f_lower or "faqueer" in f_lower:
                if any(x in f for x in ["44", "45", "۴۴", "۴۵", "والیس", "پینتالیس"]):
                    full_p = os.path.join(r, f)
                    found_files.append(full_p)
                    print(f"  FOUND: {full_p}")

print("\n" + "=" * 80)
print(f" Total potential Vol 44/45 matches found: {len(found_files)}")
for p in found_files:
    print(f"  --> {p}")
print("=" * 80)
