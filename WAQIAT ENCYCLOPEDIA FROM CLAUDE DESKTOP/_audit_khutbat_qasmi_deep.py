import os, sys, pymupdf, sqlite3, re
from collections import defaultdict
sys.stdout.reconfigure(encoding='utf-8')

pdf_path = r"F:\کتب\خطبات و مواعظ ۔\خطبات قاسمی\خطبات قاسمی 6 جلدیں مع فہرست م ضیاء القاسمی.pdf"
doc = pymupdf.open(pdf_path)
total_pages = len(doc)

print("=" * 85)
print(" COMPREHENSIVE PRE-INGESTION AUDIT: KHUTBAT QASMI (6 VOLUMES)")
print(f" Source File: {pdf_path}")
print(f" Total Pages: {total_pages}")
print("=" * 85)

# 1. VOLUME BOUNDARIES AUDIT
vol_markers = [
    (1, 1, 492, "جلد 1"),
    (2, 493, 1042, "جلد 2"),
    (3, 1043, 1448, "جلد 3"),
    (4, 1449, 1840, "جلد 4"),
    (5, 1841, 2114, "جلد 5"),
    (6, 2115, 2195, "جلد 6")
]

print("\n--- 1. VOLUME STRUCTURE & PAGE DISTRIBUTION ---")
for v, sp, ep, vname in vol_markers:
    cnt = ep - sp + 1
    print(f"  📖 Volume {v} ({vname:8s}): Pages {sp:4d} to {ep:4d} ({cnt:4d} pages)")

# 2. TEXT STREAM AUDIT ACROSS ALL 2,195 PAGES
print("\n--- 2. DIGITAL TEXT STREAM AUDIT ACROSS ALL PAGES ---")
pages_with_text = 0
pages_empty = 0
total_chars = 0
sample_pages = []

for pno in range(total_pages):
    page = doc[pno]
    txt = page.get_text().strip()
    if len(txt) > 30:
        pages_with_text += 1
        total_chars += len(txt)
    else:
        pages_empty += 1

print(f"  • Pages with readable digital text: {pages_with_text} ({(pages_with_text/total_pages*100):.1f}%)")
print(f"  • Pages blank / title-only: {pages_empty} ({(pages_empty/total_pages*100):.1f}%)")
print(f"  • Total digital characters extracted: {total_chars:,} chars")
print(f"  • Average characters per text page: {total_chars // max(1, pages_with_text):,}")

# 3. TEXT ENCODING & URDU READABILITY AUDIT (SAMPLE 1 FROM EACH VOLUME)
print("\n--- 3. SAMPLE TEXT AUDIT FROM EACH VOLUME (FIRST 200 CHARS) ---")
for v, sp, ep, vname in vol_markers:
    # Pick page at middle of volume
    sample_p = sp + min(25, (ep - sp) // 2)
    stxt = doc[sample_p].get_text().strip().replace('\n', ' ')
    print(f"\n  [Volume {v} — Page {sample_p+1}]:")
    print(f"  {stxt[:220]}...")

# 4. NARRATIVE TRIGGER SCAN & STORY CANDIDATE DENSITY
print("\n--- 4. NARRATIVE INCIDENT SCAN & FALSE-POSITIVE AUDIT ---")
STRICT_NARRATIVE_TRIGGERS = [
    r'(ایک مرتبہ\s+(?:حضرت|کسی|ایک|وہ|بادشاہ|بزرگ|درویش|شخص|عورت|صحابی|واقعہ|قصہ)[^۔\n]{5,50}؟?)',
    r'(ایک دفعہ\s+(?:حضرت|کسی|ایک|وہ|بادشاہ|بزرگ|درویش|شخص|عورت|صحابی|واقعہ|قصہ)[^۔\n]{5,50}؟?)',
    r'(ایک بار\s+(?:حضرت|کسی|ایک|وہ|بادشاہ|بزرگ|درویش|شخص|عورت|صحابی|واقعہ|قصہ)[^۔\n]{5,50}؟?)',
    r'(ایک بزرگ\s+[^۔\n]{5,50}؟?)',
    r'(ایک شخص\s+[^۔\n]{5,50}؟?)',
    r'(ایک بادشاہ\s+[^۔\n]{5,50}؟?)',
    r'(ایک درویش\s+[^۔\n]{5,50}؟?)',
    r'(ایک صاحب\s+[^۔\n]{5,50}؟?)',
    r'(ایک ولی\s+[^۔\n]{5,50}؟?)',
    r'(ایک فقیر\s+[^۔\n]{5,50}؟?)',
    r'(ایک مجذوب\s+[^۔\n]{5,50}؟?)',
    r'(ایک صحابی\s+[^۔\n]{5,50}؟?)',
    r'(حضرت\s+[^\n۔]{3,30}\s+(?:کا واقعہ|کا قصہ|کی حکایت|کا ایک واقعہ)[^۔\n]{0,35})',
    r'(خواب میں دیکھا\s+کہ\s+[^۔\n]{5,50})',
    r'(حکایت ہے کہ\s+[^۔\n]{5,50}؟?)',
    r'(واقعہ ہے کہ\s+[^۔\n]{5,50}؟?)',
    r'(واقعہ یہ ہے کہ\s+[^۔\n]{5,50}؟?)',
    r'(ایک سچا واقعہ\s+[^۔\n]{0,40})',
    r'(عجیب واقعہ ہے کہ\s+[^۔\n]{0,40})',
    r'(ایک قصہ سنا\s+[^۔\n]{0,40})'
]
combined_strict = re.compile("|".join(STRICT_NARRATIVE_TRIGGERS), re.UNICODE)

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

vol_story_counts = defaultdict(int)
sample_stories = []

for v, sp, ep, vname in vol_markers:
    for pno in range(sp - 1, ep):
        txt = doc[pno].get_text()
        if not txt: continue
        clean_t = re.sub(r'\s+', ' ', txt).strip()
        
        for m in combined_strict.finditer(clean_t):
            trig = m.group(0).strip()
            # check if disqualified
            if any(re.search(dp, trig) for dp in DISQUALIFY_PATTERNS):
                continue
            span = clean_t[m.start(): m.start() + 700]
            words = span.split()
            if len(words) < 25:
                continue
            vol_story_counts[v] += 1
            if len(sample_stories) < 6:
                sample_stories.append((v, pno + 1, trig[:60], span[:140]))

print(f"  • Total Pure Narrative Incidents Detected Across All 6 Volumes: {sum(vol_story_counts.values())}")
for v, sp, ep, vname in vol_markers:
    print(f"    - Volume {v} ({vname}): ~{vol_story_counts[v]} Pure Waqiat candidates")

print("\n--- 5. SAMPLE STORY DETECTIONS ---")
for v, pno, title, body in sample_stories:
    print(f"  ✦ [Vol {v} - Page {pno}]: {title}")
    print(f"    متن: {body}...\n")

doc.close()
print("=" * 85)
