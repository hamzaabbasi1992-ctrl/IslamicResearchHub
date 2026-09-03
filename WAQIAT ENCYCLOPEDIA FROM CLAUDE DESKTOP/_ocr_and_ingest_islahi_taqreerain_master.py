import sys, os, pymupdf, sqlite3, json, time, argparse, re
from concurrent.futures import ThreadPoolExecutor, as_completed
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r"F:\ISLAMIC RESEARCH HUB AI\src")

from google.cloud import vision
from google.oauth2 import service_account

from islamic_research_hub.application.event_extraction import ExtractedEvent
from islamic_research_hub.infrastructure.persistence.event_candidate_repository import EventCandidateRepository
from islamic_research_hub.infrastructure.persistence.taxonomy_repository import TaxonomyRepository
from islamic_research_hub.infrastructure.persistence.event_candidate_taxonomy_repository import EventCandidateTaxonomyRepository

CREDS_PATH = r"F:\AI TOOLS N APPS MADE\google vision ocr api keys\urdu-ocr-503414-fb3d59ab845b.json"
PDF_PATH = r"F:\کتب\خطبات و مواعظ ۔\اصلاحی تقریریں ۔\اصلاحی تقریریں مع فہرست 9 جلدیں م رفیع عثمانی.pdf"
OCR_BASE_DIR = r"F:\کتب\ocr text books\اصلاحی تقریریں"
DB_PATH = r"F:\ISLAMIC RESEARCH HUB AI\data\books.db"

os.makedirs(OCR_BASE_DIR, exist_ok=True)
os.makedirs(os.path.join(OCR_BASE_DIR, "pages"), exist_ok=True)

URDU_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
def urdu_num(n): return str(n).translate(URDU_DIGITS)

# Volumes Mapping: vol_num -> (BookID, StartPDFPage, EndPDFPage, VolumeTitle)
VOLUMES_MAP = {
    2: (4362, 2, 280, "اصلاحی تقریریں جلد 2"),
    3: (4473, 281, 521, "اصلاحی تقریریں جلد 3"),
    4: (4583, 522, 786, "اصلاحی تقریریں جلد 4"),
    5: (4594, 787, 1043, "اصلاحی تقریریں جلد 5"),
    6: (4604, 1044, 1282, "اصلاحی تقریریں جلد 6"),
    7: (4629, 1283, 1511, "اصلاحی تقریریں جلد 7"),
    8: (4680, 1512, 1728, "اصلاحی تقریریں جلد 8"),
    9: (4761, 1729, 1969, "اصلاحی تقریریں جلد 9")
}

def clean_xml_text(s):
    if not s: return ""
    s = re.sub(r'</?[^>]+>', ' ', s)
    s = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', ' ', s)
    s = re.sub(r'www\.[a-zA-Z0-9_\-\.]+', '', s)
    s = re.sub(r'اصلاحی\s+تقریریں', '', s)
    s = re.sub(r'جلد\s+(?:دوم|سوم|چہارم|پنجم|ششم|ہفتم|ہشتم|نہم)[^\n]{0,30}', '', s)
    return re.sub(r'\s+', ' ', s).strip()

def clean_title(t, maxlen=85):
    t = clean_xml_text(t)
    t = re.sub(r'^[\d۱-۹١-٩\(\)\*\-\s٭…_]+', '', t).strip()
    return (t[:maxlen] + "...") if len(t) > maxlen else t

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

def get_volume_for_pdf_page(pdf_page):
    for vol, (bid, sp, ep, vname) in VOLUMES_MAP.items():
        if sp <= pdf_page <= ep:
            vol_page = pdf_page - sp + 1
            return vol, bid, vol_page, vname
    return 2, 4362, pdf_page, "اصلاحی تقریریں جلد 2"

def ocr_single_page(client, pdf_path, pdf_page_num):
    txt_file = os.path.join(OCR_BASE_DIR, "pages", f"page_{pdf_page_num:04d}.txt")
    if os.path.exists(txt_file):
        try:
            with open(txt_file, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content:
                    return pdf_page_num, content, False
        except:
            pass

    doc = pymupdf.open(pdf_path)
    page = doc[pdf_page_num - 1]
    pix = page.get_pixmap(dpi=300)
    img_bytes = pix.tobytes("png")
    doc.close()

    image = vision.Image(content=img_bytes)
    response = client.document_text_detection(image=image)
    text = response.full_text_annotation.text if response.full_text_annotation else ""

    with open(txt_file, "w", encoding="utf-8") as f:
        f.write(text)

    return pdf_page_num, text, True

def extract_and_ingest_volume(vol_num):
    bid, start_pdf, end_pdf, vtitle = VOLUMES_MAP[vol_num]
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("SELECT Title FROM Books WHERE BookID=?", (bid,))
    row = cur.fetchone()
    b_title = row[0] if row else vtitle

    # Clean old records for this book
    cur.execute("DELETE FROM EventCandidateTaxonomyTerms WHERE EventCandidateID IN (SELECT EventCandidateID FROM EventCandidates WHERE BookID=?)", (bid,))
    cur.execute("DELETE FROM EventCandidates WHERE BookID=?", (bid,))
    conn.commit()

    event_repo = EventCandidateRepository(DB_PATH)
    taxo_repo = TaxonomyRepository(DB_PATH)
    tag_repo = EventCandidateTaxonomyRepository(DB_PATH)

    cur.execute("SELECT PageNo, Content FROM Pages WHERE BookID=? AND LENGTH(Content) > 150 ORDER BY PageNo", (bid,))
    pages = {pno: c for pno, c in cur.fetchall()}

    vol_stories = []

    for pno in sorted(pages.keys()):
        # Skip first 15 pages of each volume (TOC / Front Matter)
        if pno <= 15: continue
        content = pages[pno]
        if not content or len(content) < 100: continue
        clean_text = clean_xml_text(content)

        # Pass 1: Expanded Narrative Triggers
        for match in combined_pat.finditer(clean_text):
            start_idx = match.start()
            phrase = match.group(0).strip()
            span = clean_text[start_idx: start_idx + 900]

            sentences = re.split(r'([۔！？])', span)
            if len(sentences) > 4:
                span = "".join(sentences[:8]).strip()

            title = clean_title(phrase)
            if is_valid_waqia(title, span):
                if not any(s['p'] == pno and (s['title'] == title or s['span'][:30] in span or span[:30] in s['span']) for s in vol_stories):
                    cit = f"{b_title}، صفحہ {urdu_num(pno)}"
                    vol_stories.append({'p': pno, 'title': title, 'span': span, 'cit': cit})

        # Pass 2: Heading-Based Story Sections
        lines = content.split('\n')
        for i, line in enumerate(lines):
            lc = line.strip()
            if 4 < len(lc) < 50 and not lc.endswith(('۔', '!', '؟', '،')):
                if any(re.search(kw, lc) for kw in STORY_HEADING_KEYWORDS):
                    following = " ".join(lines[i+1: i+14]).strip()
                    following_clean = clean_xml_text(following)
                    title = clean_title(lc)
                    if is_valid_waqia(title, following_clean):
                        if not any(s['p'] == pno and (s['title'] == title or s['span'][:30] in following_clean or following_clean[:30] in s['span']) for s in vol_stories):
                            cit = f"{b_title}، صفحہ {urdu_num(pno)}"
                            vol_stories.append({'p': pno, 'title': title, 'span': following_clean[:850], 'cit': cit})

    # Save to EventCandidates
    for s in vol_stories:
        ev = ExtractedEvent(
            title=s['title'], alternate_names=[], subject="مواعظ و خطبات",
            date_hijri=None, date_gregorian=None, location=None,
            background=s['span'], summary=s['title'],
            key_figures=["مفتی محمد رفیع عثمانیؒ"], quoted_excerpt=s['span'], citation=s['cit']
        )
        nid = event_repo.add_candidate(bid, s['p'], s['p'], ev)
        event_repo.confirm(nid)
        terms = [
            taxo_repo.get_or_create_term("subject", "اصلاحی تقریریں", "ur"),
            taxo_repo.get_or_create_term("personality", "مفتی محمد رفیع عثمانیؒ", "ur")
        ]
        tag_repo.tag_candidate(nid, terms)

    conn.close()
    return len(vol_stories)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=int, default=2, help="Start PDF page")
    parser.add_argument("--end", type=int, default=280, help="End PDF page")
    parser.add_argument("--workers", type=int, default=10, help="Concurrent workers")
    args = parser.parse_args()

    print("=" * 85)
    print(f" GOOGLE VISION OCR & INGESTION PIPELINE: ISLAHI TAQREERAIN (8 VOLS)")
    print(f" Pages: {args.start} to {args.end} | Workers: {args.workers}")
    print("=" * 85)

    credentials = service_account.Credentials.from_service_account_file(CREDS_PATH)
    client = vision.ImageAnnotatorClient(credentials=credentials)

    pages_to_process = list(range(args.start, args.end + 1))
    total_pages = len(pages_to_process)
    completed = 0
    new_ocr_calls = 0

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(ocr_single_page, client, PDF_PATH, p): p for p in pages_to_process}

        for future in as_completed(futures):
            pnum = futures[future]
            completed += 1
            try:
                pnum, text, was_new = future.result()
                if was_new: new_ocr_calls += 1

                vol, bid, vol_page, vname = get_volume_for_pdf_page(pnum)

                # Delete stub row and insert clean full page
                cur.execute("DELETE FROM Pages WHERE BookID=? AND PageNo=?", (bid, vol_page))
                cur.execute("""
                    INSERT INTO Pages (BookID, PageNo, Content)
                    VALUES (?, ?, ?)
                """, (bid, vol_page, text))

                if completed % 25 == 0 or completed == total_pages:
                    conn.commit()
                    pct = (completed / total_pages) * 100
                    print(f"  ⚡ [{completed:4d}/{total_pages:4d}] ({pct:5.1f}%) | Vol {vol} pg {vol_page:3d} (PDF {pnum:4d}) | New API Calls: {new_ocr_calls}")

            except Exception as e:
                print(f"  ❌ Error on PDF page {pnum}: {e}")

    conn.commit()
    conn.close()

    print("\n" + "=" * 85)
    print(f" OCR COMPLETE FOR {completed} PAGES! EXTRACTING PURE NARRATIVE WAQIAT...")
    print("=" * 85)

    total_waqiat_extracted = 0
    volumes_to_extract = set()
    for p in range(args.start, args.end + 1):
        v, _, _, _ = get_volume_for_pdf_page(p)
        volumes_to_extract.add(v)

    for v in sorted(volumes_to_extract):
        count = extract_and_ingest_volume(v)
        total_waqiat_extracted += count
        bid, _, _, vname = VOLUMES_MAP[v]
        print(f"  ✅ Volume {v} ({vname:28s} | BookID {bid}): +{count} Pure Waqiat Ingested")

    print("=" * 85)
    print(f" 🏆 TOTAL PURE WAQIAT INGESTED FOR THIS BATCH: +{total_waqiat_extracted} WAQIAT!")
    print("=" * 85)

if __name__ == "__main__":
    main()
