import sqlite3, json, sys, re
sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect(r"F:\ISLAMIC RESEARCH HUB AI\data\books.db")
cur = conn.cursor()

MALFOOZAT_IDS = [72,73,74,75,76,77,78,79,80,81,82,83,84,85,86,87,88,89,90,91,92,93,100,101,102,103,104,105,106]

# Original triggers (already extracted)
USED_TRIGGERS = [
    'ایک مرتبہ', 'ایک دفعہ', 'ایک بار', 'ایک بزرگ', 'ایک شخص',
    'ایک بادشاہ', 'ایک صاحب', 'منقول ہے کہ', 'روایت ہے کہ',
    'حکایت ہے کہ', 'واقعہ ہے کہ', 'واقعہ یہ ہے کہ', 'کا واقعہ', 'خواب میں دیکھا'
]

# Missed triggers from samples
MISSED_TRIGGERS = [
    'فرمایا کہ',        # mufti/hazrat narrating something
    'میں فرمایا کہ',    # "he said in..." 
    'بیان فرمایا',      # "narrated/described"
    'ارشاد فرمایا',     # "directed/stated"
    'نقل ہے کہ',        # "it is reported that"
    'مروی ہے کہ',       # "it is narrated that"
    'آیا ہے کہ',        # "it has come that"
    'کہا جاتا ہے کہ',   # "it is said that"
    'یہ واقعہ',         # "this incident"
    'اس واقعہ',         # "this incident..."
    'ایک واقعہ',        # "one incident"
    'قصہ یہ ہے',        # "the story is"
    'ایک قصہ',          # "one story"
    'ایک حکیم',         # "one wise man"
    'ایک مریض',         # "one patient"
    'ایک مسافر',        # "one traveler"
    'ایک عالم',         # "one scholar"
    'ایک ولی',          # "one saint"
    'ایک درویش',        # "one dervish"
    'ایک فقیر',         # "one faqeer"
    'ایک طالب علم',     # "one student"
    'ایک نوجوان',       # "one youth"
    'ایک خاتون',        # "one woman"
    'ایک آدمی',         # "one man"
    'ایک مولوی',        # "one maulvi"
    'ایک تاجر',         # "one merchant"
    'کسی نے عرض',      # "someone submitted/asked"
    'حاضرین میں سے',   # "from those present"
    'انہوں نے بتایا',   # "they informed"
    'انہوں نے کہا',     # "they said"
    'ایک مرید',         # "one disciple"
    'پیش آیا',          # "came to pass / occurred"
    'گزرا ہے کہ',       # "it passed that"
    'ذکر ہے کہ',        # "it is mentioned that"
    'لکھا ہے کہ',       # "it is written that"
    'بیربل نے',         # Birbal (stories)
    'مثال دیا کرتا',    # "I would give the example"
]

# Now scan missed pages for frequency of each missed trigger
print("=" * 70)
print(" MISSED TRIGGER FREQUENCY ANALYSIS")
print("=" * 70)

trigger_freq = {t: 0 for t in MISSED_TRIGGERS}
missed_page_details = []

for b_id in MALFOOZAT_IDS:
    extracted_pages = set(r[0] for r in cur.execute(
        "SELECT DISTINCT ChunkStartPage FROM EventCandidates WHERE BookID=? AND Status='confirmed'", (b_id,)
    ).fetchall())

    pages = cur.execute(
        "SELECT PageNo, Content FROM Pages WHERE BookID=? AND Content IS NOT NULL AND LENGTH(Content)>100",
        (b_id,)
    ).fetchall()

    for pno, content in pages:
        if pno in extracted_pages: continue
        clean = re.sub(r'<[^>]+>', ' ', content or '')
        if any(t in clean for t in USED_TRIGGERS): continue  # already handled

        found = [t for t in MISSED_TRIGGERS if t in clean]
        if found:
            for t in found:
                trigger_freq[t] += 1
            if len(missed_page_details) < 20:
                missed_page_details.append({
                    'bid': b_id, 'page': pno,
                    'triggers': found[:3],
                    'preview': clean[:200]
                })

print("\nFrequency of each MISSED trigger across unextracted pages:")
sorted_freq = sorted(trigger_freq.items(), key=lambda x: -x[1])
for t, freq in sorted_freq:
    if freq > 0:
        bar = "█" * min(freq // 5, 40)
        print(f"  {t:25s}: {freq:4d} pages  {bar}")

print()
print("=== TOP SAMPLE PAGES THAT NEED EXTRACTION ===")
for s in missed_page_details[:10]:
    print(f"\n  BookID={s['bid']}, Page={s['page']}, Triggers found: {s['triggers']}")
    print(f"  {s['preview']}")

# Estimate how many more waqiat we could extract
high_value = sum(freq for t, freq in trigger_freq.items() if freq >= 10)
print()
print(f"=== ESTIMATED ADDITIONAL WAQIAT RECOVERABLE ===")
print(f"  Pages with high-value missed triggers (>=10 occurrences): {high_value}")
print(f"  Estimated net-new waqiat (conservative, ~60% yield): {int(high_value * 0.6)}")
print(f"  Estimated net-new waqiat (optimistic, ~85% yield)  : {int(high_value * 0.85)}")

conn.close()
print("\n=== ANALYSIS COMPLETE ===")
