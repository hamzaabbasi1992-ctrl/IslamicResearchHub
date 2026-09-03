import os, sys, glob
sys.stdout.reconfigure(encoding='utf-8')

lib_dir = r"F:\ISLAMIC RESEARCH HUB AI\library"

ext_counts = {}
sample_files = []

for root, dirs, files in os.walk(lib_dir):
    for f in files:
        ext = os.path.splitext(f)[1].lower()
        ext_counts[ext] = ext_counts.get(ext, 0) + 1
        if len(sample_files) < 20 and ext in ['.pdf', '.txt', '.bok', '.docx']:
            sample_files.append(os.path.join(root, f))

print("=" * 65)
print(" LIBRARY FILE FORMAT INVENTORY")
print("=" * 65)
for ext, count in sorted(ext_counts.items(), key=lambda x: -x[1]):
    print(f"  {ext or '[No Ext]':15s}: {count:5d} files")

print("\nSample Files:")
for sf in sample_files[:10]:
    print(f"  {sf}")
