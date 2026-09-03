import sqlite3, json, sys, re
from collections import defaultdict
sys.stdout.reconfigure(encoding='utf-8')

DB_PATH = r"F:\ISLAMIC RESEARCH HUB AI\data\books.db"
conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

print("=" * 85)
print(" COMPREHENSIVE AUDIT OF ALL 34,000+ WAQIAT ACROSS ENTIRE LIBRARY")
print("=" * 85)

cur.execute("""
    SELECT ec.EventCandidateID, ec.BookID, b.Title, ec.Title, ec.ExtractedDataJson
    FROM EventCandidates ec
    JOIN Books b ON ec.BookID = b.BookID
    WHERE ec.Status = 'confirmed'
""")
rows = cur.fetchall()
conn.close()

print(f"Total Confirmed Records in Library Database: {len(rows)}\n")

# Disqualification patterns for non-story quotes / wazaif / sayings
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

book_stats = defaultdict(lambda: {'total': 0, 'non_waqiat': 0, 'genuine': 0, 'samples_bad': []})
total_non_waqiat = 0
total_genuine = 0

for ev_id, bid, btitle, title, djson in rows:
    book_stats[btitle]['total'] += 1
    
    try:
        data = json.loads(djson)
    except:
        continue
        
    matn = data.get("quoted_excerpt") or data.get("background") or ""
    title_clean = (title or "").strip()
    
    # Check if bad non-waqia quote
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
        total_non_waqiat += 1
        if len(book_stats[btitle]['samples_bad']) < 3:
            book_stats[btitle]['samples_bad'].append((title_clean, matn[:100]))
    else:
        book_stats[btitle]['genuine'] += 1
        total_genuine += 1

print(f"📊 SUMMARY:")
print(f"  • Total Library Records: {len(rows)}")
print(f"  • Genuine Narrative Waqiat: {total_genuine} ({(total_genuine/len(rows)*100):.1f}%)")
print(f"  • Non-Waqiat / Generic Quotes Found: {total_non_waqiat} ({(total_non_waqiat/len(rows)*100):.1f}%)\n")

# Show books with highest non-waqiat counts
print("=" * 85)
print(" BOOKS WITH NON-WAQIAT QUOTES (SORTED BY DEFECT COUNT):")
print("=" * 85)

sorted_books = sorted(book_stats.items(), key=lambda x: x[1]['non_waqiat'], reverse=True)

for btitle, stats in sorted_books:
    if stats['non_waqiat'] > 0:
        pct = (stats['non_waqiat'] / stats['total']) * 100
        print(f"\n📚 {btitle[:50]:50s} | کل: {stats['total']:4d} | مشکوک/نان-واقعات: {stats['non_waqiat']:4d} ({pct:4.1f}%) | مستند: {stats['genuine']:4d}")
        for stitle, smatn in stats['samples_bad']:
            print(f"    ❌ [{stitle[:60]}] -> {smatn[:75]}...")

print("\n" + "=" * 85)
