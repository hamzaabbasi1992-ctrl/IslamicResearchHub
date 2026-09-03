import os, sys, re
sys.stdout.reconfigure(encoding='utf-8')

OCR_DIR = r"F:\کتب\ocr text books\اسلام اور ہماری زندگی\pages"

EXPANDED_NARRATIVE_TRIGGERS = [
    # Core classical openings
    r'((?:چنانچہ\s+)?ایک\s+مرتبہ\s+(?:حضرت|کسی|ایک|وہ|بادشاہ|بزرگ|درویش|شخص|عورت|صحابی|واقعہ|قصہ|ایسا|صاحب)[^۔\n]{5,55}؟?)',
    r'((?:چنانچہ\s+)?ایک\s+دفعہ\s+(?:حضرت|کسی|ایک|وہ|بادشاہ|بزرگ|درویش|شخص|عورت|صحابی|واقعہ|قصہ|ایسا|صاحب)[^۔\n]{5,55}؟?)',
    r'((?:چنانچہ\s+)?ایک\s+بار\s+(?:حضرت|کسی|ایک|وہ|بادشاہ|بزرگ|درویش|شخص|عورت|صحابی|واقعہ|قصہ|ایسا|صاحب)[^۔\n]{5,55}؟?)',
    r'((?:چنانچہ\s+)?ایک\s+دن\s+(?:حضرت|حضور|آپ|رسول|نبی|سیدنا|کسی|ایک|صحابہ|وہ|بادشاہ|بزرگ)[^۔\n]{5,55}؟?)',
    r'(ایک\s+(?:بزرگ|شخص|بادشاہ|درویش|صاحب|ولی|فقیر|مجذوب|صحابی|نوجوان|عورت|بچہ|طالب\s+علم|تاجر|مسافر|چرواہا|پادری|یہودی|دیہاتی|اعرابی)\s+[^۔\n]{5,50}؟?)',
    r'((?:حضرت|علامہ|مولانا|امام|شیخ|حکیم\s+الامت|خواجہ)\s+[^\n۔]{3,30}\s+(?:کا\s+واقعہ|کا\s+قصہ|کی\s+حکایت|کا\s+ایک\s+واقعہ|کا\s+واقعہ\s+یاد\s+آیا|نے\s+ایک\s+واقعہ\s+سنایا|نے\s+ایک\s+قصہ\s+سنایا)[^۔\n]{0,35})',
    r'(خواب\s+میں\s+دیکھا\s+کہ\s+[^۔\n]{5,50})',
    r'(حکایت\s+ہے\s+کہ\s+[^۔\n]{5,50}؟?)',
    r'((?:ایک\s+)?واقعہ\s+(?:ہے\s+کہ|یہ\s+ہے\s+کہ|یاد\s+آیا\s+کہ|سناتا\s+ہوں|ذکر\s+کرتا\s+ہوں)\s*[^۔\n]{0,40})',
    r'((?:ایک\s+)?(?:سچا|عجیب|عبرتناک|ایمان\s+افروز|تاریخی|دلچسپ)\s+واقعہ\s+[^۔\n]{0,40})',
    r'(ایک\s+قصہ\s+(?:سنا|سناتا\s+ہوں|سنایا|ہے\s+کہ)\s*[^۔\n]{0,40})',
    r'((?:روایت|تاریخ|حدیث\s+شریف|سیرت)\s+میں\s+(?:ایک\s+)?واقعہ\s+آتا\s+ہے\s+کہ[^۔\n]{5,60})',
    r'(روایت\s+میں\s+آتا\s+ہے\s+کہ\s+[^۔\n]{10,60})',
    r'(تاریخ\s+میں\s+آتا\s+ہے\s+کہ\s+[^۔\n]{10,60})',
    r'(جب\s+حضرت\s+[^\n۔]{3,30}\s+(?:تشریف\s+لائے|تشریف\s+لے\s+گئے|نے\s+دیکھا|کے\s+پاس|نے\s+عرض\s+کیا|روانہ\s+ہوئے|کا\s+انتقال\s+ہوا|شہید\s+ہوئے|کی\s+وفات\s+ہوئی)[^۔\n]{5,60})'
]
combined_pat = re.compile("|".join(EXPANDED_NARRATIVE_TRIGGERS), re.UNICODE)

STORY_HEADING_KEYWORDS = [
    r'واقعہ', r'قصہ', r'شہادت', r'ہجرت', r'غزوہ', r'خواب', r'معجزہ', r'ملاقات',
    r'تعاقب', r'داستان', r'مناظرہ', r'توبہ', r'بیعت', r'عبرت'
]

DISQUALIFY_PATTERNS = [
    r'^ارشاد فرمایا', r'^فرمایا کہ', r'^بیان فرمایا', r'^لکھا ہے کہ', r'^آیا ہے کہ',
    r'^حدیث میں آتا ہے', r'^حدیث شریف میں ہے', r'^قرآن میں ہے', r'^قرآن پاک میں ہے',
    r'اللہم صل علی', r'لاکھ مرتبہ قسم کھا سکتا ہوں', r'درود شریف پڑھیں',
    r'نفل پڑھا کرو', r'تسبیح پڑھا کرو', r'مرتبہ پڑھ لیا کرو', r'نَحْمَدُه وَ نُصَلَّى'
]

def is_valid_waqia(title, matn):
    t_clean = title.strip()
    for dp in DISQUALIFY_PATTERNS:
        if re.search(dp, t_clean) or re.search(dp, matn[:80]):
            return False
    words = matn.split()
    if len(words) < 22 or len(matn) < 120:
        return False
    story_markers = ["تھا", "تھی", "تھے", "گئے", "آئے", "دیکھا", "کہا", "عرض کیا", "پوچھا", "جواب دیا", "پہنچے", "گزر رہے تھے", "واقعہ", "قصہ", "تشریف"]
    if sum(1 for m in story_markers if m in matn) < 2:
        return False
    return True

VOLUMES_MAP = {
    1: (1, 345), 2: (346, 682), 3: (683, 1051), 4: (1052, 1356), 5: (1357, 1701),
    6: (1702, 2014), 7: (2015, 2367), 8: (2368, 2720), 9: (2721, 3017), 10: (3018, 3306)
}

print("=" * 85)
print(" TESTING EXPANDED EXTRACTION ON ALL 10 VOLUMES OF ISLAM AUR HAMARI ZINDAGI")
print("=" * 85)

grand_stories = []

for vol, (sp, ep) in VOLUMES_MAP.items():
    vol_stories = []
    for p in range(sp, ep + 1):
        vol_pno = p - sp + 1
        if vol_pno <= 20: continue  # skip TOC

        pfile = os.path.join(OCR_DIR, f"page_{p:04d}.txt")
        if not os.path.exists(pfile): continue
        with open(pfile, 'r', encoding='utf-8') as f:
            content = f.read()

        if len(content) < 100: continue

        # Pass 1: Expanded Triggers
        for m in combined_pat.finditer(content):
            phrase = m.group(0).strip()
            start = m.start()
            span = content[start: start + 850]
            if is_valid_waqia(phrase, span):
                if not any(s['p'] == vol_pno and (s['title'] == phrase or s['span'][:30] in span or span[:30] in s['span']) for s in vol_stories):
                    vol_stories.append({'vol': vol, 'p': vol_pno, 'title': phrase, 'span': span})

        # Pass 2: Heading Sections
        lines = content.split('\n')
        for i, l in enumerate(lines):
            lc = l.strip()
            if 4 < len(lc) < 50 and not lc.endswith(('۔', '!', '؟', '،')):
                if any(re.search(kw, lc) for kw in STORY_HEADING_KEYWORDS):
                    following = " ".join(lines[i+1: i+13]).strip()
                    if is_valid_waqia(lc, following):
                        if not any(s['p'] == vol_pno and (s['title'] == lc or s['span'][:30] in following or following[:30] in s['span']) for s in vol_stories):
                            vol_stories.append({'vol': vol, 'p': vol_pno, 'title': lc, 'span': following[:850]})

    print(f"  Volume {vol:2d}: {len(vol_stories):3d} Pure Waqiat")
    grand_stories.extend(vol_stories)

print("-" * 85)
print(f"TOTAL WITH EXPANDED REFINED TRIGGERS: {len(grand_stories)} PURE WAQIAT (Up from 555)")
