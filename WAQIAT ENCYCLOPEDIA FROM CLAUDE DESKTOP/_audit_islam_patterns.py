import os, sys, sqlite3, re
sys.stdout.reconfigure(encoding='utf-8')

OCR_DIR = r"F:\کتب\ocr text books\اسلام اور ہماری زندگی\pages"
DB_PATH = r"F:\ISLAMIC RESEARCH HUB AI\data\books.db"

print("=" * 85)
print(" DEEP AUDIT: INVESTIGATING WAQIAT PATTERNS IN ISLAM AUR HAMARI ZINDAGI")
print("=" * 85)

# Let's inspect pages from Volume 1, 2, 3, etc.
# What storytelling triggers does Mufti Taqi Usmani use?
# Classical patterns used by Mufti Taqi Usmani:
# 1. "ہمارے حضرت ڈاکٹر صاحب رحمۃ اللہ علیہ فرمایا کرتے تھے کہ..."
# 2. "میرے والد ماجد حضرت مفتی محمد شفیع صاحب رحمۃ اللہ علیہ فرماتے تھے کہ..."
# 3. "حضرت تھانوی رحمۃ اللہ علیہ کا ایک واقعہ یاد آیا..."
# 4. "حکیم الامت حضرت تھانوی قدس سرہ نے ایک قصہ بیان فرمایا کہ..."
# 5. "ایک بزرگ کا واقعہ یاد آیا..."
# 6. "سیرت طیبہ میں آتا ہے کہ..."
# 7. "حدیث شریف میں ایک واقعہ آتا ہے کہ..."
# 8. "واقعہ یاد آیا کہ..."
# 9. "چنانچہ ایک مرتبہ..." / "چنانچہ ایک دفعہ..." / "چنانچہ ایک بار..."
# 10. "ایک مرتبہ کا واقعہ ہے..."
# 11. "ایک بار ایسا ہوا کہ..."
# 12. "ایک واقعہ سناتا ہوں..."
# 13. "ایک صاحب کا واقعہ ہے..."
# 14. "حضرت عمر رضی اللہ عنہ کے زمانے میں..."
# 15. "حضور اقدس صلی اللہ علیہ وسلم کے زمانے کا واقعہ ہے..."
# 16. "رسول اللہ صلی اللہ علیہ وسلم تشریف لے جا رہے تھے کہ..."

test_patterns = [
    (r'(چنانچہ\s+ایک\s+(?:مرتبہ|دفعہ|بار|دن|بزرگ|شخص|صاحب|بادشاہ)[^۔\n]{5,50})', "چنانچہ ایک مرتبہ/دفعہ"),
    (r'((?:میرے\s+والد\s+ماجد|حضرت\s+والد\s+صاحب|حضرت\s+ڈاکٹر\s+صاحب|حضرت\s+تھانوی|حضرت\s+مفتی\s+صاحب|حکیم\s+الامت|شاہ\s+عبد\s+العزیز|شیخ\s+الہند|مولانا\s+نانوتوی)[^\n۔]{0,35}(?:کا\s+ایک\s+واقعہ|ایک\s+واقعہ\s+سنایا|ایک\s+قصہ\s+سنایا|کا\s+واقعہ\s+یاد\s+آیا|ایک\s+واقعہ\s+ذکر\s+فرمایا)[^۔\n]{0,35})', "اکابر کا واقعہ یاد آیا"),
    (r'(ایک\s+واقعہ\s+یاد\s+آیا[^۔\n]{0,50})', "ایک واقعہ یاد آیا"),
    (r'(ایک\s+واقعہ\s+سناتا\s+ہوں[^۔\n]{0,50})', "ایک واقعہ سناتا ہوں"),
    (r'(حدیث\s+شریف\s+میں\s+(?:ایک\s+)?واقعہ\s+آتا\s+ہے[^۔\n]{0,50})', "حدیث شریف میں واقعہ آتا ہے"),
    (r'(روایات\s+میں\s+آتا\s+ہے\s+کہ[^۔\n]{5,50})', "روایات میں آتا ہے کہ"),
    (r'(سیرت\s+میں\s+آتا\s+ہے\s+کہ[^۔\n]{5,50})', "سیرت میں آتا ہے کہ"),
    (r'(حضور\s+اقدس\s+صلی\s+اللہ\s+علیہ\s+وسلم\s+کے\s+زمانے\s+کا\s+واقعہ\s+ہے[^۔\n]{0,50})', "حضور اقدس کے زمانے کا واقعہ"),
    (r'(حضرت\s+(?:عمر|ابوبکر|عثمان|علی|معاویہ|خالد|بلال|سلمان|ابوذر|انس|جابر|ابوہریرہ)[^\n۔]{0,30}(?:کا\s+ایک\s+واقعہ|کا\s+واقعہ\s+ہے|کا\s+قصہ|کے\s+زمانے\s+کا\s+واقعہ)[^۔\n]{0,40})', "صحابہ کا واقعہ"),
    (r'(ایک\s+مرتبہ\s+کا\s+واقعہ\s+ہے[^۔\n]{0,40})', "ایک مرتبہ کا واقعہ ہے"),
    (r'(ایک\s+بار\s+ایسا\s+ہوا\s+کہ[^۔\n]{0,40})', "ایک بار ایسا ہوا کہ"),
    (r'(ایک\s+دفعہ\s+کا\s+ذکر\s+ہے[^۔\n]{0,40})', "ایک دفعہ کا ذکر ہے"),
    (r'(ایک\s+مرتبہ\s+ایسا\s+ہوا[^۔\n]{0,40})', "ایک مرتبہ ایسا ہوا"),
]

# Let's count occurrences of these across all 3,306 OCR pages
page_files = [f for f in os.listdir(OCR_DIR) if f.startswith('page_') and f.endswith('.txt')]
page_files.sort()
print(f"Total OCR pages found on disk: {len(page_files)}")

pattern_hits = {label: [] for _, label in test_patterns}

for pf in page_files:
    pnum = int(pf.replace('page_', '').replace('.txt', ''))
    with open(os.path.join(OCR_DIR, pf), 'r', encoding='utf-8') as f:
        text = f.read()

    for pat, label in test_patterns:
        matches = re.findall(pat, text)
        if matches:
            for m in matches:
                pattern_hits[label].append((pnum, m.strip()))

print("\n--- NEW / ADDITIONAL NARRATIVE TRIGGERS HITS ---")
total_new_hits = 0
for label, hits in pattern_hits.items():
    print(f"  📌 {label:32s}: {len(hits):4d} hits")
    total_new_hits += len(hits)
    if hits:
        for p, sample in hits[:2]:
            print(f"      pg {p:4d}: {sample[:60]}")

print("-" * 85)
print(f"Total potential narrative trigger hits found: {total_new_hits}")
