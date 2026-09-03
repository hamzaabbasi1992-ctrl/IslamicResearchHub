import pymupdf, sys, os, re
sys.stdout.reconfigure(encoding='utf-8')

pdf_path = r"F:\کتب\خطبات و مواعظ ۔\خطبات قاسمی\خطبات قاسمی 6 جلدیں مع فہرست م ضیاء القاسمی.pdf"
doc = pymupdf.open(pdf_path)

# Look at TOC pages in Vol 1 (pages 5 to 20)
print("=" * 85)
print(" EXAMINING TITLES & SUBJECTS OF KHUTBAT QASMI")
print("=" * 85)

conn_str = ""
for pno in range(4, 18):
    conn_str += doc[pno].get_text() + "\n"

# Clean
lines = [l.strip() for l in conn_str.split('\n') if len(l.strip()) > 3]
print(f"Sample Sermon Titles / Topics in Volume 1 ({len(lines)} items found):")
for l in lines[:30]:
    print(f"  • {l}")

doc.close()
