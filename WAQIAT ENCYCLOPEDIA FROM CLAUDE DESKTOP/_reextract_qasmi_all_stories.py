import sys, os, pymupdf, sqlite3, json, time, re
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r"F:\ISLAMIC RESEARCH HUB AI\src")

from islamic_research_hub.application.event_extraction import ExtractedEvent
from islamic_research_hub.infrastructure.persistence.event_candidate_repository import EventCandidateRepository
from islamic_research_hub.infrastructure.persistence.taxonomy_repository import TaxonomyRepository
from islamic_research_hub.infrastructure.persistence.event_candidate_taxonomy_repository import EventCandidateTaxonomyRepository

DB_PATH = r"F:\ISLAMIC RESEARCH HUB AI\data\books.db"
OUTPUT_DIR = r"F:\ISLAMIC RESEARCH HUB AI\WAQIAT ENCYCLOPEDIA FROM CLAUDE DESKTOP\مکمل جلدیں واقعات کتابوں سے"

URDU_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
def urdu_num(n): return str(n).translate(URDU_DIGITS)

VOLUMES_MAP = {
    1: (3534, 1, 492, "خطبات قاسمی جلد 1"),
    2: (3545, 493, 1042, "خطبات قاسمی جلد 2"),
    3: (35451, 1043, 1448, "خطبات قاسمی جلد 3"),
    4: (35452, 1449, 1840, "خطبات قاسمی جلد 4"),
    5: (3556, 1841, 2114, "خطبات قاسمی جلد 5"),
    6: (3567, 2115, 2195, "خطبات قاسمی جلد 6")
}

def clean_xml_text(s):
    if not s: return ""
    s = re.sub(r'</?[^>]+>', ' ', s)
    s = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', ' ', s)
    s = re.sub(r'www\.[a-zA-Z0-9_\-\.]+', '', s)
    s = re.sub(r'خطبات\s+قاسمی', '', s)
    return re.sub(r'\s+', ' ', s).strip()

def clean_title(t, maxlen=85):
    t = clean_xml_text(t)
    t = re.sub(r'^[\d۱-۹١-٩\(\)\*\-\s٭…_]+', '', t).strip()
    return (t[:maxlen] + "...") if len(t) > maxlen else t

# COMPREHENSIVE NARRATIVE PATTERNS (COVERING CLASSICAL + JALSA ORATORICAL STYLES)
BROAD_NARRATIVE_TRIGGERS = [
    r'(ایک مرتبہ\s+(?:حضرت|کسی|ایک|وہ|بادشاہ|بزرگ|درویش|شخص|عورت|صحابی|واقعہ|قصہ)[^۔\n]{5,50}؟?)',
    r'(ایک دفعہ\s+(?:حضرت|کسی|ایک|وہ|بادشاہ|بزرگ|درویش|شخص|عورت|صحابی|واقعہ|قصہ)[^۔\n]{5,50}؟?)',
    r'(ایک بار\s+(?:حضرت|کسی|ایک|وہ|بادشاہ|بزرگ|درویش|شخص|عورت|صحابی|واقعہ|قصہ)[^۔\n]{5,50}؟?)',
    r'(ایک دن\s+(?:حضرت|حضور|آپ|رسول|نبی|سیدنا|کسی|ایک|صحابہ|وہ)[^۔\n]{5,55}؟?)',
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
    r'(ایک قصہ سنا\s+[^۔\n]{0,40})',
    r'(روایت میں آتا ہے کہ\s+[^۔\n]{10,60})',
    r'(تاریخ میں آتا ہے کہ\s+[^۔\n]{10,60})',
    r'(جب\s+حضرت\s+[^\n۔]{3,30}\s+(?:تشریف لائے|تشریف لے گئے|نے دیکھا|کے پاس|نے عرض کیا|روانہ ہوئے|کا انتقال ہوا|شہید ہوئے|کی وفات ہوئی)[^۔\n]{5,60})'
]
combined_pattern = re.compile("|".join(BROAD_NARRATIVE_TRIGGERS), re.UNICODE)

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

def is_valid_waqia(title, matn):
    title_clean = title.strip()
    for dp in DISQUALIFY_PATTERNS:
        if re.search(dp, title_clean):
            return False
    words = matn.split()
    if len(words) < 25 or len(matn) < 140:
        return False
    story_markers = ["تھا", "تھی", "تھے", "گئے", "آئے", "دیکھا", "کہا", "عرض کیا", "پوچھا", "جواب دیا", "پہنچے", "گزر رہے تھے", "واقعہ", "قصہ", "تشریف"]
    if sum(1 for m in story_markers if m in matn) < 2:
        return False
    return True

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# Clear existing Khutbat Qasmi EventCandidates so we can re-extract cleanly with full patterns
cur.execute("DELETE FROM EventCandidateTaxonomyTerms WHERE EventCandidateID IN (SELECT EventCandidateID FROM EventCandidates WHERE BookID IN (3534, 3545, 35451, 35452, 3556, 3567))")
cur.execute("DELETE FROM EventCandidates WHERE BookID IN (3534, 3545, 35451, 35452, 3556, 3567)")
conn.commit()

event_repo = EventCandidateRepository(DB_PATH)
taxo_repo = TaxonomyRepository(DB_PATH)
tag_repo = EventCandidateTaxonomyRepository(DB_PATH)

total_new_waqiat = 0
all_stories_collected = []

print("=" * 85)
print(" RE-EXTRACTING ALL PURE WAQIAT FROM KHUTBAT QASMI (VOLUMES 1-6)")
print("=" * 85)

for vol_num in range(1, 7):
    bid, start_pdf, end_pdf, vtitle = VOLUMES_MAP[vol_num]
    cur.execute("SELECT PageNo, Content FROM Pages WHERE BookID=? ORDER BY PageNo", (bid,))
    pages = {pno: (c or '') for pno, c in cur.fetchall()}

    vol_stories = []
    for pno in sorted(pages.keys()):
        content = pages[pno]
        if not content or len(content) < 100: continue
        clean_text = clean_xml_text(content)

        for match in combined_pattern.finditer(clean_text):
            start_idx = match.start()
            trigger_phrase = match.group(0).strip()
            story_span = clean_text[start_idx: start_idx + 900]

            sentences = re.split(r'([۔！？])', story_span)
            if len(sentences) > 4:
                story_span = "".join(sentences[:8]).strip()

            title = clean_title(trigger_phrase)
            if not is_valid_waqia(title, story_span):
                continue

            # Dedup
            if any(s['page'] == pno and (s['title'] == title or s['matn'][:40] in story_span) for s in vol_stories):
                continue

            cit = f"{vtitle}، صفحہ {urdu_num(pno)}"
            vol_stories.append({'vol': vol_num, 'book_id': bid, 'title': title, 'page': pno, 'matn': story_span, 'cit': cit})

            ev = ExtractedEvent(
                title=title, alternate_names=[], subject="مواعظ و خطبات",
                date_hijri=None, date_gregorian=None, location=None,
                background=story_span, summary=title,
                key_figures=["حضرت مولانا ضیاء القاسمؒ"], quoted_excerpt=story_span, citation=cit
            )
            nid = event_repo.add_candidate(bid, pno, pno, ev)
            event_repo.confirm(nid)
            terms = [
                taxo_repo.get_or_create_term("subject", "خطباتِ قاسمی", "ur"),
                taxo_repo.get_or_create_term("personality", "حضرت مولانا ضیاء القاسمؒ", "ur")
            ]
            tag_repo.tag_candidate(nid, terms)

    all_stories_collected.extend(vol_stories)
    print(f"  ✅ Volume {vol_num} ({vtitle:22s} | BookID {bid}): +{len(vol_stories):2d} Pure Waqiat Ingested")

conn.close()

print("=" * 85)
print(f" 🏆 TOTAL PURE WAQIAT INGESTED FOR KHUTBAT QASMI: {len(all_stories_collected)} WAQIAT!")
print("=" * 85)
