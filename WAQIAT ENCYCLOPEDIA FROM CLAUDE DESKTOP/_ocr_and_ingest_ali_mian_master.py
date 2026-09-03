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

CREDS_PATH = r"F:\AI TOOLS N APPS MADE\URDU OCR GOOGLE VISION\urdu ocr google coude vision key\urdu-ocr-503414-fb3d59ab845b.json"
PDF_PATH = r"F:\کتب\خطبات و مواعظ ۔\خطباتِ علی میاں ۔\خطبات علی میاں 7 جلدین.pdf"
OCR_BASE_DIR = r"F:\کتب\ocr text books\خطبات علی میاں"
DB_PATH = r"F:\ISLAMIC RESEARCH HUB AI\data\books.db"

os.makedirs(OCR_BASE_DIR, exist_ok=True)
os.makedirs(os.path.join(OCR_BASE_DIR, "pages"), exist_ok=True)

URDU_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
def urdu_num(n): return str(n).translate(URDU_DIGITS)

# Volumes Map: (BookID, StartPDFPage, EndPDFPage, VolumeTitle)
VOLUMES_MAP = {
    1: (3274, 1, 401, "تعلیم و تعلم"),
    2: (3284, 402, 818, "دعوت و عزیمت"),
    3: (3294, 819, 1251, "ہدایت و تبلیغ"),
    4: (3305, 1252, 1700, "تہذیب و معاشرہ"),
    5: (3316, 1701, 2149, "خطباتِ علی میاں جلد ۵"),
    6: (3327, 2150, 2574, "خطباتِ علی میاں جلد ۶"),
    7: (3336, 2575, 2975, "خطباتِ علی میاں جلد ۷")
}

def clean_xml_text(s):
    if not s: return ""
    s = re.sub(r'</?[^>]+>', ' ', s)
    s = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', ' ', s)
    s = re.sub(r'www\.[a-zA-Z0-9_\-\.]+', '', s)
    s = re.sub(r'خطبات\s+علی\s+میاں', '', s)
    return re.sub(r'\s+', ' ', s).strip()

def clean_title(t, maxlen=85):
    t = clean_xml_text(t)
    t = re.sub(r'^[\d۱-۹١-٩\(\)\*\-\s٭…_]+', '', t).strip()
    return (t[:maxlen] + "...") if len(t) > maxlen else t

# STRICT NARRATIVE STORY PATTERNS
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
combined_strict_pattern = re.compile("|".join(STRICT_NARRATIVE_TRIGGERS), re.UNICODE)

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
    story_markers = ["تھا", "تھی", "تھے", "گئے", "آئے", "دیکھا", "کہا", "عرض کیا", "پوچھا", "جواب دیا", "پہنچے", "گزر رہے تھے", "واقعہ", "قصہ"]
    if sum(1 for m in story_markers if m in matn) < 2:
        return False
    return True

def get_volume_for_pdf_page(pdf_page):
    for vol, (bid, sp, ep, vname) in VOLUMES_MAP.items():
        if sp <= pdf_page <= ep:
            vol_page = pdf_page - sp + 1
            return vol, bid, vol_page, vname
    return 1, 3274, pdf_page, "تعلیم و تعلم"

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
    b_title = row[0] if row else f"خطبات علی میاں جلد {vol_num}"

    event_repo = EventCandidateRepository(DB_PATH)
    taxo_repo = TaxonomyRepository(DB_PATH)
    tag_repo = EventCandidateTaxonomyRepository(DB_PATH)

    cur.execute("SELECT ChunkStartPage, ExtractedDataJson FROM EventCandidates WHERE BookID=? AND Status='confirmed'", (bid,))
    existing_records = []
    for sp, data_json in cur.fetchall():
        data = json.loads(data_json) if data_json else {}
        ex = data.get('quoted_excerpt') or data.get('background') or ''
        existing_records.append({'page': sp, 'excerpt': ex})

    cur.execute("SELECT PageNo, Content FROM Pages WHERE BookID=? ORDER BY PageNo", (bid,))
    pages = {pno: (c or '') for pno, c in cur.fetchall()}

    new_stories = []
    for pno in sorted(pages.keys()):
        content = pages[pno]
        if not content or len(content) < 100: continue
        clean_text = clean_xml_text(content)

        for match in combined_strict_pattern.finditer(clean_text):
            start_idx = match.start()
            trigger_phrase = match.group(0).strip()
            story_span = clean_text[start_idx: start_idx + 900]

            sentences = re.split(r'([۔！？])', story_span)
            if len(sentences) > 4:
                story_span = "".join(sentences[:8]).strip()

            title = clean_title(trigger_phrase)
            if not is_valid_waqia(title, story_span):
                continue

            if any(s['page'] == pno and s['title'] == title for s in new_stories):
                continue
            if any(r['page'] == pno and story_span[:40] in r['excerpt'] for r in existing_records):
                continue

            cit = f"{b_title}، صفحہ {urdu_num(pno)}"
            new_stories.append({'title': title, 'page': pno, 'matn': story_span, 'cit': cit})

            ev = ExtractedEvent(
                title=title, alternate_names=[], subject="مواعظ و خطبات",
                date_hijri=None, date_gregorian=None, location=None,
                background=story_span, summary=title,
                key_figures=["حضرت مولانا سید ابوالحسن علی ندویؒ"], quoted_excerpt=story_span, citation=cit
            )
            nid = event_repo.add_candidate(bid, pno, pno, ev)
            event_repo.confirm(nid)
            terms = [
                taxo_repo.get_or_create_term("subject", "خطباتِ علی میاں", "ur"),
                taxo_repo.get_or_create_term("personality", "حضرت مولانا سید ابوالحسن علی ندویؒ", "ur")
            ]
            tag_repo.tag_candidate(nid, terms)

    conn.close()
    return len(new_stories)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=int, default=1, help="Start PDF page")
    parser.add_argument("--end", type=int, default=2975, help="End PDF page")
    parser.add_argument("--workers", type=int, default=8, help="Concurrent workers")
    args = parser.parse_args()

    print("=" * 85)
    print(f" GOOGLE VISION OCR & INGESTION PIPELINE: KHUTBAT ALI MIAN (VOLUMES 1-7)")
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
                cur.execute("""
                    INSERT OR REPLACE INTO Pages (BookID, PageNo, Content)
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
    # Determine which volumes fall into the requested page range
    volumes_to_extract = set()
    for p in range(args.start, args.end + 1):
        v, _, _, _ = get_volume_for_pdf_page(p)
        volumes_to_extract.add(v)

    for v in sorted(volumes_to_extract):
        count = extract_and_ingest_volume(v)
        total_waqiat_extracted += count
        bid, _, _, vname = VOLUMES_MAP[v]
        print(f"  ✅ Volume {v} ({vname:25s} | BookID {bid}): +{count} Pure Waqiat Ingested")

    print("=" * 85)
    print(f" 🏆 TOTAL PURE WAQIAT INGESTED FOR KHUTBAT ALI MIAN: +{total_waqiat_extracted} WAQIAT!")
    print("=" * 85)

if __name__ == "__main__":
    main()
