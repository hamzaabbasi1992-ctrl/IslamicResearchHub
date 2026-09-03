# GEMINI TASK BRIEF — واقعات انسائیکلوپیڈیا Full Coverage Audit

## YOUR ROLE
You are continuing the **واقعات انسائیکلوپیڈیا (Waqiat Encyclopedia)** project. Your job is to systematically audit every Islamic book in the library database, find ALL missed narrative incidents (واقعات / قصص / حکایات), extract them, deduplicate, and sync.

You have full terminal/file access to the workspace at:
**`F:\ISLAMIC RESEARCH HUB AI\`**

---

## CRITICAL RULES — READ BEFORE DOING ANYTHING

1. **NEVER extract from `فضائل اعمال` (Fazail Amal)** — user explicitly excluded this book series.
2. **ZERO DUPLICATES** — All scripts have built-in dedup. Do NOT insert manually.
3. **Do NOT delete any existing records** — only ADD new ones.
4. **All actions must be on `Status='confirmed'` records only** in `EventCandidates` table.
5. **DB path**: `F:\ISLAMIC RESEARCH HUB AI\data\books.db`
6. **Source path**: `F:\ISLAMIC RESEARCH HUB AI\src`

---

## STEP 0 — CHECK CURRENT STATE FIRST

Run this to see where we are:

```powershell
cd "F:\ISLAMIC RESEARCH HUB AI"
python -c "
import sqlite3, sys
sys.stdout.reconfigure(encoding='utf-8')
conn = sqlite3.connect(r'F:\ISLAMIC RESEARCH HUB AI\data\books.db')
cur = conn.cursor()
total = cur.execute(\"SELECT COUNT(*) FROM EventCandidates WHERE Status='confirmed'\").fetchone()[0]
print(f'TOTAL CONFIRMED WAQIAT: {total}')
books_with_content = cur.execute('''
    SELECT COUNT(DISTINCT b.BookID) FROM Books b
    JOIN Pages p ON b.BookID=p.BookID
    WHERE LENGTH(p.Content) > 100
''').fetchone()[0]
print(f'BOOKS WITH CONTENT: {books_with_content}')
conn.close()
"
```

Expected output at time of this brief: **~26,000+ confirmed waqiat** (still growing).

---

## STEP 1 — RUN COVERAGE GAP ANALYSIS

This script scans EVERY book and finds pages with narrative content but no extraction yet:

```powershell
cd "F:\ISLAMIC RESEARCH HUB AI"
python _coverage_gap_analysis.py
```

**What to look for in output:**
- Books with `Coverage%` below **40%** — these need immediate extraction
- `Missed-only` column > 0 — pages with triggers our regex missed

---

## STEP 2 — RUN PASS 2 EXTRACTION (if not already done)

```powershell
cd "F:\ISLAMIC RESEARCH HUB AI"
python _deep_extract_pass2.py
```

This extracts from **ملفوظات حکیم الامت** (30 volumes, BookIDs 72–106) using the extended trigger set. Expected to add **~2,500–3,600 more waqiat**.

---

## STEP 3 — FULL COMPREHENSIVE AUDIT SCAN (ALL BOOKS)

This is the **master audit script** — it scans EVERY book in the database with content:

```powershell
cd "F:\ISLAMIC RESEARCH HUB AI"
python _full_library_coverage_scan.py
```

If `_full_library_coverage_scan.py` does not exist, CREATE it with this code:

```python
import sqlite3, json, sys, re
sys.stdout.reconfigure(encoding='utf-8')

DB_PATH = r"F:\ISLAMIC RESEARCH HUB AI\data\books.db"
conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

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
    'کسی نے عرض', 'حاضرین میں سے', 'بیربل نے', 'پیش آیا'
]

# EXCLUDED BOOKS
EXCLUDED_BOOK_IDS = {545}  # Fazail Amal - user directive
EXCLUDED_TITLE_KEYWORDS = ['فضائل اعمال', 'fazail']

print("=" * 75)
print(" FULL LIBRARY COVERAGE SCAN")
print("=" * 75)
print(f"{'BookID':>8} | {'Confirmed':>10} | {'Content Pgs':>11} | {'Coverage%':>10} | {'Unextracted+Trigger':>20} | Title")
print("-" * 100)

books = cur.execute("""
    SELECT b.BookID, b.Title,
           COUNT(DISTINCT p.PageNo) as cpages,
           COUNT(DISTINCT ec.EventCandidateID) as confirmed
    FROM Books b
    JOIN Pages p ON b.BookID=p.BookID AND LENGTH(p.Content) > 100
    LEFT JOIN EventCandidates ec ON b.BookID=ec.BookID AND ec.Status='confirmed'
    GROUP BY b.BookID, b.Title
    HAVING cpages > 10
    ORDER BY (CAST(confirmed AS FLOAT)/cpages) ASC
""").fetchall()

needs_work = []
for bid, title, cpages, conf in books:
    # Skip excluded
    if bid in EXCLUDED_BOOK_IDS: continue
    if any(kw.lower() in title.lower() for kw in EXCLUDED_TITLE_KEYWORDS): continue

    extracted_pgs = set(r[0] for r in cur.execute(
        "SELECT DISTINCT ChunkStartPage FROM EventCandidates WHERE BookID=? AND Status='confirmed'", (bid,)
    ).fetchall())

    pages = cur.execute(
        "SELECT PageNo, Content FROM Pages WHERE BookID=? AND LENGTH(Content)>100", (bid,)
    ).fetchall()

    trigger_pages = 0
    for pno, content in pages:
        if pno in extracted_pgs: continue
        c = re.sub(r'<[^>]+>', ' ', content or '')
        if any(t in c for t in ALL_TRIGGERS):
            trigger_pages += 1

    cov = (conf/cpages*100) if cpages else 0
    flag = " *** NEEDS WORK" if trigger_pages > 20 else ""
    print(f"{bid:>8} | {conf:>10} | {cpages:>11} | {cov:>9.1f}% | {trigger_pages:>20} | {title[:50]}{flag}")

    if trigger_pages > 20:
        needs_work.append({'bid': bid, 'title': title, 'conf': conf,
                           'cpages': cpages, 'trigger_pages': trigger_pages, 'cov': cov})

conn.close()

print("\n")
print("=" * 75)
print(f" BOOKS NEEDING EXTRACTION ({len(needs_work)} total):")
print("=" * 75)
for b in sorted(needs_work, key=lambda x: -x['trigger_pages']):
    print(f"  BookID {b['bid']:5d} | {b['trigger_pages']:4d} unextracted trigger pages | {b['cov']:.0f}% coverage | {b['title'][:55]}")
```

---

## STEP 4 — EXTRACT FROM ANY SPECIFIC BOOK

For any book that needs work, use this command pattern:

```python
# Create this as _extract_single_book.py and run:
# python _extract_single_book.py <BookID> "<Key Figure Name>" "<Subject>"

import sqlite3, json, sys, re
sys.path.insert(0, r"F:\ISLAMIC RESEARCH HUB AI\src")
sys.stdout.reconfigure(encoding='utf-8')

from islamic_research_hub.application.event_extraction import ExtractedEvent
from islamic_research_hub.infrastructure.persistence.event_candidate_repository import EventCandidateRepository
from islamic_research_hub.infrastructure.persistence.taxonomy_repository import TaxonomyRepository
from islamic_research_hub.infrastructure.persistence.event_candidate_taxonomy_repository import EventCandidateTaxonomyRepository

DB_PATH = r"F:\ISLAMIC RESEARCH HUB AI\data\books.db"
URDU_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
urdu_num = lambda n: str(n).translate(URDU_DIGITS)
clean = lambda s: re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', s or '')).strip()

ALL_TRIGGERS = re.compile(
    r"(ایک مرتبہ|ایک دفعہ|ایک بار|ایک بزرگ|ایک شخص|ایک بادشاہ|ایک صاحب"
    r"|منقول ہے کہ|روایت ہے کہ|حکایت ہے کہ|واقعہ ہے کہ|واقعہ یہ ہے کہ"
    r"|خواب میں دیکھا|فرمایا کہ|ارشاد فرمایا|بیان فرمایا|لکھا ہے کہ"
    r"|آیا ہے کہ|انہوں نے کہا|پیش آیا|ذکر ہے کہ|نقل ہے کہ|مروی ہے کہ"
    r"|ایک مولوی|ایک عالم|ایک ولی|ایک درویش|ایک فقیر|ایک طالب علم"
    r"|ایک نوجوان|ایک خاتون|ایک آدمی|ایک مرید|ایک حکیم|ایک تاجر"
    r"|ایک مریض|ایک مسافر|ایک واقعہ|یہ واقعہ|اس واقعہ|ایک قصہ|قصہ یہ ہے"
    r"|کسی نے عرض|کہا جاتا ہے کہ|حاضرین میں سے)\s+[^۔\n]{5,60}",
    re.UNICODE
)

b_id = int(sys.argv[1])
key_fig = sys.argv[2] if len(sys.argv) > 2 else ""
subject = sys.argv[3] if len(sys.argv) > 3 else "واقعات و حکایات"

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()
b_title = cur.execute("SELECT Title FROM Books WHERE BookID=?", (b_id,)).fetchone()[0]
print(f"Extracting from: {b_title}")

existing = []
for sp, dj in cur.execute("SELECT ChunkStartPage, ExtractedDataJson FROM EventCandidates WHERE BookID=? AND Status='confirmed'", (b_id,)).fetchall():
    d = json.loads(dj) if dj else {}
    existing.append({'page': sp, 'excerpt': d.get('quoted_excerpt', '') or d.get('background', '')})

extracted_pgs = {r['page'] for r in existing}
pages = dict(cur.execute("SELECT PageNo, Content FROM Pages WHERE BookID=? ORDER BY PageNo", (b_id,)).fetchall())

event_repo = EventCandidateRepository(DB_PATH)
taxo_repo  = TaxonomyRepository(DB_PATH)
tag_repo   = EventCandidateTaxonomyRepository(DB_PATH)

added = 0
new_stories = []

for pno in sorted(pages):
    c = clean(pages[pno])
    if len(c) < 120: continue
    for m in ALL_TRIGGERS.finditer(c):
        trigger = m.group(0).strip()
        idx = m.start()
        span = c[idx: idx+900]
        if len(span) < 500 and (pno+1) in pages:
            span += " " + clean(pages[pno+1])[:400]
        parts = re.split(r'([۔！؟])', span)
        span = "".join(parts[:8]).strip() if len(parts) > 4 else span
        if len(span) < 130: continue

        is_dup = any(
            abs(ex['page']-pno)<=1 and (span[:45] in ex['excerpt'] or span[50:95] in ex['excerpt'])
            for ex in existing
        )
        if not is_dup:
            is_dup = any(abs(ns['page']-pno)<=1 and span[:40] in ns['span'] for ns in new_stories)

        if not is_dup:
            title = re.sub(r'^[\d۱-۹\(\)\*\-\s٭…_]+', '', trigger).strip()
            if len(title) >= 8:
                new_stories.append({'page': pno, 'title': title[:90], 'span': span})
                break

for s in new_stories:
    ev = ExtractedEvent(
        title=s['title'], alternate_names=[], subject=subject,
        date_hijri=None, date_gregorian=None, location=None,
        background=s['span'], summary=s['title'],
        key_figures=[key_fig] if key_fig else [], quoted_excerpt=s['span'],
        citation=f"{b_title}، صفحہ {urdu_num(s['page'])}"
    )
    nid = event_repo.add_candidate(b_id, s['page'], s['page'], ev)
    event_repo.confirm(nid)
    terms = [taxo_repo.get_or_create_term("subject", subject, "ur")]
    if key_fig: terms.append(taxo_repo.get_or_create_term("personality", key_fig, "ur"))
    tag_repo.tag_candidate(nid, terms)
    added += 1

conn.close()
print(f"DONE: +{added} net-new waqiat added to BookID {b_id}")
```

**Example usage:**
```powershell
python _extract_single_book.py 82 "مولانا اشرف علی تھانویؒ" "ملفوظات و سوانحی واقعات"
python _extract_single_book.py 200 "مفتی محمد تقی عثمانیؒ" "خطبات و مواعظ"
```

---

## STEP 5 — VERIFY EACH BOOK AFTER EXTRACTION

After extracting from any book, immediately verify:

```powershell
python -c "
import sqlite3, sys
sys.stdout.reconfigure(encoding='utf-8')
BOOK_ID = 82  # <-- change this
conn = sqlite3.connect(r'F:\ISLAMIC RESEARCH HUB AI\data\books.db')
cnt = conn.execute(\"SELECT COUNT(*) FROM EventCandidates WHERE BookID=? AND Status='confirmed'\", (BOOK_ID,)).fetchone()[0]
title = conn.execute('SELECT Title FROM Books WHERE BookID=?', (BOOK_ID,)).fetchone()[0]
print(f'{title}: {cnt} confirmed waqiat')
# Check for exact duplicates
dups = conn.execute('''
    SELECT COUNT(*) FROM (
        SELECT BookID, ChunkStartPage, ExtractedDataJson, COUNT(*) c
        FROM EventCandidates WHERE BookID=? AND Status=\'confirmed\'
        GROUP BY BookID, ChunkStartPage, ExtractedDataJson HAVING c>1
    )
''', (BOOK_ID,)).fetchone()[0]
print(f'Exact duplicates: {dups}')
conn.close()
"
```

---

## STEP 6 — SYNC EVERYTHING AFTER EACH BATCH

After every batch of extractions, run sync:

```powershell
cd "F:\ISLAMIC RESEARCH HUB AI"
python sync_waqiat_app.py
```

This updates:
- Web Search App (`SEARCH APP/data.js`)
- Research App (`RESEARCH APP/data.js`)
- Dashboard (`waqiat_dashboard/data.js`)
- Mobile JSON (`mobile/app/src/main/assets/waqiat_database.json`)
- Grand Master Word Document (`.docx`)

---

## STEP 7 — REBUILD ANDROID APK (after all extractions done)

```powershell
cd "F:\ISLAMIC RESEARCH HUB AI\mobile"
gradlew.bat assembleDebug
```

Then copy APK:
```powershell
copy "F:\ISLAMIC RESEARCH HUB AI\mobile\app\build\outputs\apk\debug\app-debug.apk" "F:\ISLAMIC RESEARCH HUB AI\mobile\Maktaba_Shams.apk"
copy "F:\ISLAMIC RESEARCH HUB AI\mobile\app\build\outputs\apk\debug\app-debug.apk" "F:\ISLAMIC RESEARCH HUB AI\WAQIAT ENCYCLOPEDIA FROM CLAUDE DESKTOP\Maktaba_Shams.apk"
```

---

## BOOK SERIES REFERENCE — KEY FIGURES & SUBJECTS

Use this table when extracting — match the key_figure and subject correctly:

| Series Name | BookIDs (approx) | Key Figure | Subject Term |
|:---|:---|:---|:---|
| ملفوظات حکیم الامت | 72–106 | مولانا اشرف علی تھانویؒ | ملفوظات و سوانحی واقعات |
| اصلاحی خطبات | (check DB) | مفتی محمد تقی عثمانیؒ | خطبات و مواعظ |
| خطبات محمود | (check DB) | مولانا محمود الحسنؒ | خطبات و مواعظ |
| خطبات رحیمی | (check DB) | مفتی عبد الرحیم لاجپوریؒ | خطبات و مواعظ |
| خطبات حبان | (check DB) | مولانا محمد حبانؒ | خطبات و مواعظ |
| تاریخ دعوت و عزیمت | (check DB) | مولانا ابوالحسن علی ندویؒ | تاریخ دعوت و اسلامی تحریکات |
| قصص الانبیاء | (check DB) | مولانا ابوالحسن علی ندویؒ | انبیاء کرام کے واقعات |
| تفسیر عثمانی | (check DB) | علامہ شبیر احمد عثمانیؒ | شانِ نزول و قصص القرآن |
| معارف القرآن | (check DB) | مفتی محمد شفیعؒ | شانِ نزول و قصص القرآن |
| احیاء العلوم | (check DB) | امام ابو حامد الغزالیؒ | اخلاق و تزکیہ واقعات |
| سیرت النبی | (check DB) | علامہ شبلی نعمانیؒ | سیرت النبی ﷺ واقعات |
| حکایات خلیل | (check DB) | مولانا خلیل احمد سہارنپوریؒ | اخلاق و تزکیہ واقعات |

---

## FINDING CORRECT BookIDs

To find BookIDs for any series:

```powershell
python -c "
import sqlite3, sys
sys.stdout.reconfigure(encoding='utf-8')
keyword = 'خطبات رحیمی'  # change this
conn = sqlite3.connect(r'F:\ISLAMIC RESEARCH HUB AI\data\books.db')
rows = conn.execute('SELECT BookID, Title FROM Books WHERE Title LIKE ?', (f'%{keyword}%',)).fetchall()
for bid, title in rows: print(f'  [{bid}] {title}')
conn.close()
"
```

---

## WHAT TO REPORT WHEN DONE

After completing all books, provide this summary to the user:

```
Total confirmed waqiat in DB: [NUMBER]
Books processed this session: [LIST]
Net new waqiat added: [NUMBER]
Sync status: ✅ All apps updated
APK rebuilt: ✅ Maktaba_Shams.apk [SIZE] MB
```

---

## IMPORTANT NOTES

- The database has **`dismissed: 1`** record — do NOT touch it.
- Word documents are generated by `sync_waqiat_app.py` automatically — do NOT edit them manually.
- The `Pages.Content` field contains XML markup (`<urh1>`, `<urp>` etc.) — always strip with regex before processing.
- If a script errors with "from keyword not supported", you are running it in PowerShell's `-c` mode — save to a `.py` file and run with `python filename.py` instead.
- Average JSON record size should be **~7,000–9,000 bytes**. Records under 200 bytes are noise — do NOT insert them.
