import sqlite3, json, sys, re, os
sys.stdout.reconfigure(encoding='utf-8')

DB_PATH = r"F:\ISLAMIC RESEARCH HUB AI\data\books.db"
conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# Comprehensive triggers
ALL_TRIGGERS = [
    'ایک مرتبہ', 'ایک دفعہ', 'ایک بار', 'ایک بزرگ', 'ایک شخص',
    'ایک بادشاہ', 'ایک صاحب', 'منقول ہے کہ', 'روایت ہے کہ',
    'حکایت ہے کہ', 'واقعہ ہے کہ', 'واقعہ یہ ہے کہ', 'کا واقعہ',
    'خواب میں دیکھا', 'فرمایا کہ', 'ارشاد فرمایا', 'بیان فرمایا',
    'لکھا ہے کہ', 'آیا ہے کہ', 'انہوں نے کہا', 'پیش آیا',
    'ذکر ہے کہ', 'نقل ہے کہ', 'مروی ہے کہ', 'کہا جاتا ہے کہ',
    'ایک مولوی', 'ایک عالم', 'ایک ولی', 'ایک درویش', 'ایک فقیر',
    'ایک طالب علم', 'ایک نوجوان', 'ایک خاتون', 'ایک آدمی',
    'ایک مرید', 'ایک حکیم', 'ایک تاجر', 'ایک مریض', 'ایک مسافر',
    'ایک واقعہ', 'یہ واقعہ', 'اس واقعہ', 'ایک قصہ', 'قصہ یہ ہے',
    'کسی نے عرض', 'حاضرین میں سے', 'بیربل نے'
]

combined_pattern = re.compile("|".join(ALL_TRIGGERS), re.UNICODE)

EXCLUDED_BOOK_IDS = {545}  # Fazail Amal - user directive
EXCLUDED_TITLE_KEYWORDS = ['فضائل اعمال', 'fazail']

print("=" * 85)
print(" FULL LIBRARY WAQIAT COVERAGE AUDIT & INVENTORY")
print("=" * 85)

# Total confirmed
total_confirmed = cur.execute("SELECT COUNT(*) FROM EventCandidates WHERE Status='confirmed'").fetchone()[0]
print(f"Current Total Confirmed Waqiat in Database: {total_confirmed}\n")

# Query all books with pages in DB
books = cur.execute("""
    SELECT b.BookID, b.Title, b.Author,
           COUNT(DISTINCT p.PageNo) as cpages,
           COUNT(DISTINCT ec.EventCandidateID) as confirmed
    FROM Books b
    JOIN Pages p ON b.BookID=p.BookID AND LENGTH(p.Content) > 50
    LEFT JOIN EventCandidates ec ON b.BookID=ec.BookID AND ec.Status='confirmed'
    GROUP BY b.BookID, b.Title, b.Author
    HAVING cpages > 5
    ORDER BY (CAST(confirmed AS FLOAT)/cpages) ASC, cpages DESC
""").fetchall()

print(f"Total Books with Content in Library: {len(books)}\n")

low_coverage = []
good_coverage = []
empty_or_excluded = []

for bid, title, author, cpages, conf in books:
    # Exclude check
    if bid in EXCLUDED_BOOK_IDS or any(kw.lower() in title.lower() for kw in EXCLUDED_TITLE_KEYWORDS):
        empty_or_excluded.append((bid, title, cpages, conf, "EXCLUDED"))
        continue

    cov = (conf / cpages * 100) if cpages else 0

    if cov < 40:
        low_coverage.append((bid, title, author or '', cpages, conf, cov))
    else:
        good_coverage.append((bid, title, author or '', cpages, conf, cov))

print(f"--- 1. HIGH-YIELD CANDIDATES FOR DEEP EXTRACTION ({len(low_coverage)} Books with < 40% coverage) ---")
print(f"{'BookID':>7} | {'Confirmed':>9} | {'Pages':>7} | {'Coverage%':>9} | Title & Author")
print("-" * 85)
for bid, title, author, cpages, conf, cov in low_coverage:
    print(f"{bid:>7} | {conf:>9} | {cpages:>7} | {cov:>8.1f}% | {title[:45]} ({author[:25]})")

print(f"\n--- 2. WELL-COVERED BOOKS ({len(good_coverage)} Books with >= 40% coverage) ---")
print(f"{'BookID':>7} | {'Confirmed':>9} | {'Pages':>7} | {'Coverage%':>9} | Title")
print("-" * 85)
for bid, title, author, cpages, conf, cov in good_coverage[:25]:
    print(f"{bid:>7} | {conf:>9} | {cpages:>7} | {cov:>8.1f}% | {title[:55]}")
if len(good_coverage) > 25:
    print(f"... and {len(good_coverage) - 25} more books with solid coverage.")

conn.close()
