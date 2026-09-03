import sqlite3, sys, re
sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect(r"F:\ISLAMIC RESEARCH HUB AI\data\books.db")
cur = conn.cursor()

def is_toc_page(text):
    if not text: return True
    if "فہرست مضامین" in text or "تفصیلی فہرست" in text or "مفصل فہرست" in text or "اجمالی فہرست" in text:
        return True
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    if not lines: return True
    page_num_lines = sum(1 for l in lines if re.search(r'[\d۰-۹١-٩]{1,4}\s*$', l))
    if len(lines) > 6 and (page_num_lines / len(lines)) > 0.35:
        return True
    return False

cur.execute("SELECT PageNo, Content FROM Pages WHERE BookID=3392 AND LENGTH(Content) > 200 ORDER BY PageNo")
rows = cur.fetchall()

print("Testing TOC Detection on Volume 1 Pages:")
for pno, c in rows[:30]:
    is_toc = is_toc_page(c)
    first_l = c.split('\n')[0].strip() if c else ""
    print(f"  Page {pno:3d} (Len: {len(c):4d}): is_toc={str(is_toc):5s} | First line: {first_l[:55]}")

conn.close()
