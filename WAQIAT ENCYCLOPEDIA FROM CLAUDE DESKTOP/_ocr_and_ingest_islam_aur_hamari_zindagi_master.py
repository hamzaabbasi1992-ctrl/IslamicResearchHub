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
PDF_PATH = r"F:\کتب\خطبات و مواعظ ۔\اسلام اور ہماری زندگی م تقی عثمانی\اسلام اور ہماری زندگی 10 جلدیں م تقی عثمانی.pdf"
OCR_BASE_DIR = r"F:\کتب\ocr text books\اسلام اور ہماری زندگی"
DB_PATH = r"F:\ISLAMIC RESEARCH HUB AI\data\books.db"

os.makedirs(OCR_BASE_DIR, exist_ok=True)
os.makedirs(os.path.join(OCR_BASE_DIR, "pages"), exist_ok=True)

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

STORY_HEADING_KEYWORDS = [
    r'واقعہ', r'قصہ', r'شہادت', r'ہجرت', r'غزوہ', r'خواب', r'معجزہ', r'ملاقات',
    r'تعاقب', r'داستان', r'مناظرہ', r'توبہ', r'بیعت'
]

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
    r'مرتبہ پڑھ لیا کرو',
    r'نَحْمَدُه وَ نُصَلَّى'
]

def is_toc_page(text):
    if not text: return True
    if "فہرست مضامین" in text or "تفصیلی فہرست" in text or "مفصل فہرست" in text or "اجمالی فہرست" in text:
        return True
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    if not lines: return True
    page_num_lines = sum(1 for l in lines if re.search(r'[\d۰-۹١-٩]{1,4}\s*$', l))
    if len(lines) > 6 and (page_num_lines / len(lines)) > 0.35:
        return True
    return False

def is_valid_waqia(title, matn):
    title_clean = title.strip()
    for dp in DISQUALIFY_PATTERNS:
        if re.search(dp, title_clean) or re.search(dp, matn[:80]):
            return False
    words = matn.split()
    if len(words) < 25 or len(matn) < 140:
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
    return 1, 3392, pdf_page, "اسلام اور ہماری زندگی جلد 1"

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

    # Clean old records for this book to ensure zero duplication
    cur.execute("DELETE FROM EventCandidateTaxonomyTerms WHERE EventCandidateID IN (SELECT EventCandidateID FROM EventCandidates WHERE BookID=?)", (bid,))
    cur.execute("DELETE FROM EventCandidates WHERE BookID=?", (bid,))
    conn.commit()

    event_repo = EventCandidateRepository(DB_PATH)
    taxo_repo = TaxonomyRepository(DB_PATH)
    tag_repo = EventCandidateTaxonomyRepository(DB_PATH)

    # Load only the latest OCR text for each page
    cur.execute("SELECT PageNo, Content FROM Pages WHERE BookID=? AND LENGTH(Content) > 150 ORDER BY PageNo", (bid,))
    pages = {}
    for pno, c in cur.fetchall():
        pages[pno] = c

    vol_stories = []

    for pno in sorted(pages.keys()):
        # Exclude TOC pages (pages <= 20 or matching is_toc_page)
        if pno <= 20: continue
        content = pages[pno]
        if not content or len(content) < 100: continue
        if is_toc_page(content): continue

        clean_text = clean_xml_text(content)

        # Pass 1: Inline Narrative Triggers
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

            # Dedup with overlap check
            if any(s['page'] == pno and (s['title'] == title or s['matn'][:30] in story_span or story_span[:30] in s['matn']) for s in vol_stories):
                continue

            cit = f"{b_title}، صفحہ {urdu_num(pno)}"
            vol_stories.append({'vol': vol_num, 'book_id': bid, 'title': title, 'page': pno, 'matn': story_span, 'cit': cit})

            ev = ExtractedEvent(
                title=title, alternate_names=[], subject="مواعظ و خطبات",
                date_hijri=None, date_gregorian=None, location=None,
                background=story_span, summary=title,
                key_figures=["مفتی محمد تقی عثمانی مدظلہم"], quoted_excerpt=story_span, citation=cit
            )
            nid = event_repo.add_candidate(bid, pno, pno, ev)
            event_repo.confirm(nid)
            terms = [
                taxo_repo.get_or_create_term("subject", "اسلام اور ہماری زندگی", "ur"),
                taxo_repo.get_or_create_term("personality", "مفتی محمد تقی عثمانی مدظلہم", "ur")
            ]
            tag_repo.tag_candidate(nid, terms)

        # Pass 2: Heading-Based Story Sections
        lines = content.split('\n')
        for i, line in enumerate(lines):
            line_clean = line.strip()
            if 4 < len(line_clean) < 50 and not line_clean.endswith(('۔', '!', '؟', '،')):
                if any(re.search(kw, line_clean) for kw in STORY_HEADING_KEYWORDS):
                    following_text = " ".join(lines[i+1: i+14]).strip()
                    following_clean = clean_xml_text(following_text)
                    if is_valid_waqia(line_clean, following_clean):
                        # Dedup
                        if any(s['page'] == pno and (s['title'] == line_clean or s['matn'][:30] in following_clean or following_clean[:30] in s['matn']) for s in vol_stories):
                            continue

                        cit = f"{b_title}، صفحہ {urdu_num(pno)}"
                        title = clean_title(line_clean)
                        vol_stories.append({'vol': vol_num, 'book_id': bid, 'title': title, 'page': pno, 'matn': following_clean[:850], 'cit': cit})

                        ev = ExtractedEvent(
                            title=title, alternate_names=[], subject="مواعظ و خطبات",
                            date_hijri=None, date_gregorian=None, location=None,
                            background=following_clean[:850], summary=title,
                            key_figures=["مفتی محمد تقی عثمانی مدظلہم"], quoted_excerpt=following_clean[:850], citation=cit
                        )
                        nid = event_repo.add_candidate(bid, pno, pno, ev)
                        event_repo.confirm(nid)
                        terms = [
                            taxo_repo.get_or_create_term("subject", "اسلام اور ہماری زندگی", "ur"),
                            taxo_repo.get_or_create_term("personality", "مفتی محمد تقی عثمانی مدظلہم", "ur")
                        ]
                        tag_repo.tag_candidate(nid, terms)

    conn.close()
    return len(vol_stories)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=int, default=1, help="Start PDF page")
    parser.add_argument("--end", type=int, default=345, help="End PDF page")
    parser.add_argument("--workers", type=int, default=10, help="Concurrent workers")
    args = parser.parse_args()

    print("=" * 85)
    print(f" GOOGLE VISION OCR & INGESTION PIPELINE: ISLAM AUR HAMARI ZINDAGI (10 VOLS)")
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

                # Delete old stub entry before inserting new full text
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
