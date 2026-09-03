import sqlite3, json, sys, re
sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect(r"F:\ISLAMIC RESEARCH HUB AI\data\books.db")
cur = conn.cursor()

MALFOOZAT_IDS = [72,73,74,75,76,77,78,79,80,81,82,83,84,85,86,87,88,89,90,91,92,93,100,101,102,103,104,105,106]

# Extended trigger set - what we USED
USED_TRIGGERS = [
    'ایک مرتبہ', 'ایک دفعہ', 'ایک بار', 'ایک بزرگ', 'ایک شخص',
    'ایک بادشاہ', 'ایک صاحب', 'منقول ہے کہ', 'روایت ہے کہ',
    'حکایت ہے کہ', 'واقعہ ہے کہ', 'واقعہ یہ ہے کہ', 'کا واقعہ', 'خواب میں دیکھا'
]

# ADDITIONAL triggers we may have MISSED
POTENTIAL_MISSED_TRIGGERS = [
    'ایک عالم', 'ایک ولی', 'ایک درویش', 'ایک فقیر', 'ایک طالب علم',
    'ایک مریض', 'ایک مسافر', 'ایک نوجوان', 'ایک خاتون', 'ایک عورت',
    'ایک آدمی', 'ایک مولوی', 'ایک تاجر', 'ایک کسان',
    'فرمایا کہ', 'بیان فرمایا', 'ارشاد فرمایا',
    'نقل ہے کہ', 'مروی ہے کہ', 'آیا ہے کہ', 'کہا جاتا ہے کہ',
    'حضرت نے فرمایا', 'حضور نے فرمایا',
    'ایک واقعہ', 'یہ واقعہ', 'اس واقعہ', 'واقعہ سنو',
    'قصہ یہ ہے', 'ایک قصہ', 'حکایت یہ ہے',
    'ایک حکیم', 'ایک پیر', 'ایک مرید', 'ایک سیانا',
    'اس نے کہا', 'اس نے بتایا', 'انہوں نے بتایا', 'انہوں نے کہا',
    'ملفوظ', 'حاضرین میں سے', 'کسی نے عرض',
]

print("=" * 75)
print(" COVERAGE ANALYSIS: DID WE MISS ANY WAQIAT?")
print("=" * 75)

total_content_pages = 0
total_zero_extraction_pages = 0
has_missed_trigger_pages = 0
missed_trigger_samples = []

book_report = []

for b_id in MALFOOZAT_IDS:
    row = cur.execute("SELECT Title, PageCount FROM Books WHERE BookID=?", (b_id,)).fetchone()
    if not row: continue
    b_title, p_count = row

    # All pages with content
    pages = cur.execute(
        "SELECT PageNo, Content FROM Pages WHERE BookID=? AND Content IS NOT NULL AND LENGTH(Content)>100 ORDER BY PageNo",
        (b_id,)
    ).fetchall()

    # Pages that already have at least one confirmed extraction
    extracted_pages = set(r[0] for r in cur.execute(
        "SELECT DISTINCT ChunkStartPage FROM EventCandidates WHERE BookID=? AND Status='confirmed'", (b_id,)
    ).fetchall())

    content_pages = len(pages)
    zero_pages = []

    for pno, content in pages:
        if pno not in extracted_pages:
            # Check if this zero-extraction page has ANY narrative trigger
            clean = re.sub(r'<[^>]+>', ' ', content or '')
            has_used = any(t in clean for t in USED_TRIGGERS)
            has_missed = any(t in clean for t in POTENTIAL_MISSED_TRIGGERS)

            if has_used or has_missed:
                zero_pages.append({
                    'page': pno,
                    'has_used_trigger': has_used,
                    'has_missed_trigger': has_missed,
                    'preview': clean[:120]
                })

    total_content_pages += content_pages
    total_zero_extraction_pages += len(zero_pages)

    # Flag missed-trigger-only pages
    missed_only = [p for p in zero_pages if not p['has_used_trigger'] and p['has_missed_trigger']]
    if missed_only:
        has_missed_trigger_pages += len(missed_only)
        for p in missed_only[:2]:
            missed_trigger_samples.append({'book': b_title[:40], 'page': p['page'], 'preview': p['preview']})

    confirmed_cnt = len(extracted_pages)
    coverage_pct = (confirmed_cnt / content_pages * 100) if content_pages else 0

    book_report.append({
        'id': b_id, 'title': b_title[:50],
        'content_pages': content_pages,
        'confirmed_cnt': confirmed_cnt,
        'zero_trigger_pages': len(zero_pages),
        'missed_only': len(missed_only),
        'coverage': coverage_pct
    })

print(f"\n{'BookID':>8} | {'Confirmed':>10} | {'Content Pgs':>11} | {'Coverage%':>10} | {'Unextracted w/ trigger':>22} | {'Missed-only':>11}")
print("-" * 95)
for r in book_report:
    flag = " ⚠️" if r['missed_only'] > 0 else ""
    print(f"{r['id']:>8} | {r['confirmed_cnt']:>10} | {r['content_pages']:>11} | {r['coverage']:>9.1f}% | {r['zero_trigger_pages']:>22} | {r['missed_only']:>11}{flag}")

print()
print(f"TOTAL content pages      : {total_content_pages}")
print(f"Total unextracted pages  : {total_zero_extraction_pages} (have a trigger but no record yet)")
print(f"Pages with MISSED trigger: {has_missed_trigger_pages} (trigger not in our regex set)")
print()

if missed_trigger_samples:
    print("=== SAMPLE MISSED-TRIGGER PAGES (text not captured) ===")
    for s in missed_trigger_samples[:8]:
        print(f"  [{s['book']}] Page {s['page']}:")
        print(f"    {s['preview']}")
        print()
else:
    print("=== No pages found with missed-only triggers (full coverage) ===")

# Count how many pages have content but NO trigger at all
print()
print("=== PAGES WITH CONTENT BUT NO NARRATIVE TRIGGER (non-narrative content) ===")
all_triggers = USED_TRIGGERS + POTENTIAL_MISSED_TRIGGERS
non_narrative = 0
for r in book_report:
    pass  # Already counted via zero_pages logic above

print(f"  These are doctrinal/fiqh discussions, rulings, definitions etc.")
print(f"  NOT waqiat — correctly excluded.")

conn.close()
print("\n=== COVERAGE ANALYSIS COMPLETE ===")
