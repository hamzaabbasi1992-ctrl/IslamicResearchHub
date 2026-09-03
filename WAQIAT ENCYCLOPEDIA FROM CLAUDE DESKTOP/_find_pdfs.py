import os, sys
sys.stdout.reconfigure(encoding='utf-8')

root_dir = r"F:\ISLAMIC RESEARCH HUB AI"
pdf_folders = {}

for root, dirs, files in os.walk(root_dir):
    # Skip git / venv
    if '.git' in root or '.venv' in root or '__pycache__' in root:
        continue
    pdf_count = sum(1 for f in files if f.lower().endswith('.pdf'))
    if pdf_count > 0:
        pdf_folders[root] = pdf_count

print("=" * 75)
print(f" PDF FOLDERS FOUND IN PROJECT ({len(pdf_folders)} folders)")
print("=" * 75)
for folder, count in pdf_folders.items():
    print(f"  {folder}: {count} PDFs")

if not pdf_folders:
    print("No PDFs found inside F:\\ISLAMIC RESEARCH HUB AI folder.")
