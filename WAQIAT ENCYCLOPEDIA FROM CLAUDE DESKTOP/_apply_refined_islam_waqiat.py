import os, sys, sqlite3, json, re
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r"F:\ISLAMIC RESEARCH HUB AI\src")

from islamic_research_hub.application.event_extraction import ExtractedEvent
from islamic_research_hub.infrastructure.persistence.event_candidate_repository import EventCandidateRepository
from islamic_research_hub.infrastructure.persistence.taxonomy_repository import TaxonomyRepository
from islamic_research_hub.infrastructure.persistence.event_candidate_taxonomy_repository import EventCandidateTaxonomyRepository

OCR_DIR = r"F:\کتب\ocr text books\اسلام اور ہماری زندگی\pages"
DB_PATH = r"F:\ISLAMIC RESEARCH HUB AI\data\books.db"

URDU_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
def urdu_num(n): return str(n).translate(URDU_DIGITS)

VOLUMES_MAP = {
    1: (3392, 1, 345, "اسلام اور ہماری زندگی جلد 1"),
    2: (3465, 346, 682, "اسلام اور ہماری زندگی جلد 2"),
    3: (3523, 683, 1051, "اسلام اور ہماری زندگی جلد 3"),
    4: (3633, 1052, 1356, "اسلام اور ہماری زندگی جلد 4"),
    5: (3744, 1357, 1701, "اسلام اور ہماری زندگی جلد 5"),
    6: (3854, 1702, 2014, "اسلام اور ہماری زندگی جلد 6"),
    7: (3961, 2015, 2367, "اسلام اور ہماری زندگی جلد 7"),
    8: (4051, 2368, 2720, "اسلام اور ہماری زندگی جلد 8"),
    9: (4146, 2721, 3017, "اسلام اور ہماری زندگی جلد 9"),
    10: (4251, 3018, 3306, "اسلام اور ہماری زندگی جلد 10")
}

EXPANDED_NARRATIVE_TRIGGERS = [
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

def clean_xml_text(s):
    if not s: return ""
    s = re.sub(r'</?[^>]+>', ' ', s)
    s = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', ' ', s)
    s = re.sub(r'www\.[a-zA-Z0-9_\-\.]+', '', s)
    s = re.sub(r'اسلام\s+اور\s+ہماری\s+زندگی', '', s)
    s = re.sub(r'جلد\s+(?:اول|دوم|سوم|چہارم|پنجم|ششم|ہفتم|ہشتم|نہم|دہم)[^\n]{0,30}', '', s)
    return re.sub(r'\s+', ' ', s).strip()

def clean_title(t, maxlen=85):
    t = clean_xml_text(t)
    t = re.sub(r'^[\d۱-۹١-٩\(\)\*\-\s٭…_]+', '', t).strip()
    return (t[:maxlen] + "...") if len(t) > maxlen else t

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

print("=" * 85)
print(" INGESTING 614 PURE NARRATIVE WAQIAT INTO BOOKS.DB")
print("=" * 85)

event_repo = EventCandidateRepository(DB_PATH)
taxo_repo = TaxonomyRepository(DB_PATH)
tag_repo = EventCandidateTaxonomyRepository(DB_PATH)

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# Clean previous entries for all 10 volumes to prevent any duplication
for v, (bid, sp, ep, vtitle) in VOLUMES_MAP.items():
    cur.execute("DELETE FROM EventCandidateTaxonomyTerms WHERE EventCandidateID IN (SELECT EventCandidateID FROM EventCandidates WHERE BookID=?)", (bid,))
    cur.execute("DELETE FROM EventCandidates WHERE BookID=?", (bid,))
conn.commit()

total_ingested = 0

for vol, (bid, sp, ep, vtitle) in VOLUMES_MAP.items():
    vol_stories = []
    for p in range(sp, ep + 1):
        vol_pno = p - sp + 1
        if vol_pno <= 20: continue  # Skip TOC pages

        pfile = os.path.join(OCR_DIR, f"page_{p:04d}.txt")
        if not os.path.exists(pfile): continue
        with open(pfile, 'r', encoding='utf-8') as f:
            content = f.read()

        if len(content) < 100: continue
        clean_text = clean_xml_text(content)

        # Pass 1: Expanded Triggers
        for m in combined_pat.finditer(clean_text):
            phrase = m.group(0).strip()
            start = m.start()
            span = clean_text[start: start + 900]

            sentences = re.split(r'([۔！？])', span)
            if len(sentences) > 4:
                span = "".join(sentences[:8]).strip()

            title = clean_title(phrase)
            if is_valid_waqia(title, span):
                if not any(s['p'] == vol_pno and (s['title'] == title or s['span'][:30] in span or span[:30] in s['span']) for s in vol_stories):
                    cit = f"{vtitle}، صفحہ {urdu_num(vol_pno)}"
                    vol_stories.append({'p': vol_pno, 'title': title, 'span': span, 'cit': cit})

        # Pass 2: Heading Sections
        lines = content.split('\n')
        for i, l in enumerate(lines):
            lc = l.strip()
            if 4 < len(lc) < 50 and not lc.endswith(('۔', '!', '؟', '،')):
                if any(re.search(kw, lc) for kw in STORY_HEADING_KEYWORDS):
                    following = " ".join(lines[i+1: i+14]).strip()
                    following_clean = clean_xml_text(following)
                    title = clean_title(lc)
                    if is_valid_waqia(title, following_clean):
                        if not any(s['p'] == vol_pno and (s['title'] == title or s['span'][:30] in following_clean or following_clean[:30] in s['span']) for s in vol_stories):
                            cit = f"{vtitle}، صفحہ {urdu_num(vol_pno)}"
                            vol_stories.append({'p': vol_pno, 'title': title, 'span': following_clean[:850], 'cit': cit})

    # Save to database
    for s in vol_stories:
        ev = ExtractedEvent(
            title=s['title'], alternate_names=[], subject="مواعظ و خطبات",
            date_hijri=None, date_gregorian=None, location=None,
            background=s['span'], summary=s['title'],
            key_figures=["مفتی محمد تقی عثمانی مدظلہم"], quoted_excerpt=s['span'], citation=s['cit']
        )
        nid = event_repo.add_candidate(bid, s['p'], s['p'], ev)
        event_repo.confirm(nid)
        terms = [
            taxo_repo.get_or_create_term("subject", "اسلام اور ہماری زندگی", "ur"),
            taxo_repo.get_or_create_term("personality", "مفتی محمد تقی عثمانی مدظلہم", "ur")
        ]
        tag_repo.tag_candidate(nid, terms)

    total_ingested += len(vol_stories)
    print(f"  ✅ Volume {vol:2d} ({vtitle:28s}): +{len(vol_stories):3d} Pure Waqiat Ingested")

conn.close()

print("=" * 85)
print(f" 🏆 TOTAL REFINED PURE WAQIAT INGESTED: {total_ingested} WAQIAT!")
print("=" * 85)
