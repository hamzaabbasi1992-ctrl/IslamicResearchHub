import sqlite3, json, sys, re
from collections import defaultdict
sys.stdout.reconfigure(encoding='utf-8')

DB_PATH = r"F:\ISLAMIC RESEARCH HUB AI\data\books.db"
conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

cur.execute("""
    SELECT ec.EventCandidateID, ec.BookID, b.Title, ec.Title, ec.ExtractedDataJson
    FROM EventCandidates ec
    JOIN Books b ON ec.BookID = b.BookID
    WHERE ec.Status = 'confirmed'
""")
rows = cur.fetchall()
conn.close()

DISQUALIFY_PATTERNS = [
    r'^ارشاد فرمایا',
    r'^فرمایا کہ',
    r'^بیان فرمایا',
    r'^لکھا ہے کہ',
    r'^آیا ہے کہ',
    r'^حدیث میں آتا ہے',
    r'^حدیث شریف میں ہے',
    r'^قرآن میں ہے',
    r'^قرآن پاک میں ہے',
    r'اللہم صل علی',
    r'لاکھ مرتبہ قسم کھا سکتا ہوں',
    r'درود شریف پڑھیں',
    r'نفل پڑھا کرو',
    r'تسبیح پڑھا کرو',
    r'مرتبہ پڑھ لیا کرو'
]

book_stats = defaultdict(lambda: {'total': 0, 'non_waqiat': 0, 'genuine': 0, 'bad_ids': []})
total_bad = 0

for ev_id, bid, btitle, title, djson in rows:
    book_stats[btitle]['total'] += 1
    
    try:
        data = json.loads(djson)
    except:
        continue
        
    matn = data.get("quoted_excerpt") or data.get("background") or ""
    title_clean = (title or "").strip()
    
    is_bad = False
    for dp in DISQUALIFY_PATTERNS:
        if re.search(dp, title_clean):
            is_bad = True
            break
            
    words = matn.split()
    if len(words) < 20 or len(matn) < 120:
        is_bad = True
        
    if is_bad:
        book_stats[btitle]['non_waqiat'] += 1
        book_stats[btitle]['bad_ids'].append(ev_id)
        total_bad += 1
    else:
        book_stats[btitle]['genuine'] += 1

print(f"Total confirmed rows: {len(rows)}")
print(f"Total non-waqiat across ALL books: {total_bad} ({(total_bad/len(rows)*100):.1f}%)")
print(f"Total genuine waqiat across ALL books: {len(rows)-total_bad} ({((len(rows)-total_bad)/len(rows)*100):.1f}%)\n")

print("TOP 25 BOOKS WITH HIGHEST DEFECT / NON-WAQIAT COUNTS:")
sorted_books = sorted(book_stats.items(), key=lambda x: x[1]['non_waqiat'], reverse=True)
for btitle, stats in sorted_books[:25]:
    if stats['non_waqiat'] > 0:
        pct = (stats['non_waqiat'] / stats['total']) * 100
        print(f"  📚 {btitle[:50]:50s} | کل: {stats['total']:4d} | مشکوک/نان-واقعات: {stats['non_waqiat']:4d} ({pct:4.1f}%) | مستند: {stats['genuine']:4d}")
