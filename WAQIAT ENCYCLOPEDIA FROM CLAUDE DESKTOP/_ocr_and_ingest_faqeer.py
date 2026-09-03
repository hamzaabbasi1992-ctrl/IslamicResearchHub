import sys, os, pymupdf, sqlite3, json, time, argparse, re
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r"F:\ISLAMIC RESEARCH HUB AI\src")

from google.cloud import vision
from google.oauth2 import service_account

from islamic_research_hub.application.event_extraction import ExtractedEvent
from islamic_research_hub.infrastructure.persistence.event_candidate_repository import EventCandidateRepository
from islamic_research_hub.infrastructure.persistence.taxonomy_repository import TaxonomyRepository
from islamic_research_hub.infrastructure.persistence.event_candidate_taxonomy_repository import EventCandidateTaxonomyRepository

CREDS_PATH = r"F:\AI TOOLS N APPS MADE\URDU OCR GOOGLE VISION\urdu ocr google coude vision key\urdu-ocr-503414-fb3d59ab845b.json"
PDF_PATH = r"F:\کتب\خطبات و مواعظ ۔\خطباتِ فقیر ۔\خطبات فقیر 43 جلد مع فہرست.pdf"
OCR_TEXT_DIR = r"F:\کتب\ocr text books\خطبات فقیر"
DB_PATH = r"F:\ISLAMIC RESEARCH HUB AI\data\books.db"

os.makedirs(OCR_TEXT_DIR, exist_ok=True)
os.makedirs(os.path.join(OCR_TEXT_DIR, "pages"), exist_ok=True)

URDU_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
def urdu_num(n): return str(n).translate(URDU_DIGITS)

def clean_xml_text(s):
    if not s: return ""
    s = re.sub(r'</?[^>]+>', ' ', s)
    s = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', ' ', s)
    s = re.sub(r'www\.[a-zA-Z0-9_\-\.]+', '', s)
    s = re.sub(r'خطبات\s+فقیر', '', s)
    return re.sub(r'\s+', ' ', s).strip()

def clean_title(t, maxlen=85):
    t = clean_xml_text(t)
    t = re.sub(r'^[\d۱-۹١-٩\(\)\*\-\s٭…_]+', '', t).strip()
    return (t[:maxlen] + "...") if len(t) > maxlen else t

ALL_TRIGGERS = [
    r'(ایک مرتبہ\s+[^۔\n]{5,50}؟?)',
    r'(ایک دفعہ\s+[^۔\n]{5,50}؟?)',
    r'(ایک بار\s+[^۔\n]{5,50}؟?)',
    r'(ایک بزرگ\s+[^۔\n]{5,50}؟?)',
    r'(ایک شخص\s+[^۔\n]{5,50}؟?)',
    r'(ایک بادشاہ\s+[^۔\n]{5,50}؟?)',
    r'(ایک صاحب\s+[^۔\n]{5,50}؟?)',
    r'(منقول ہے کہ\s+[^۔\n]{5,50}؟?)',
    r'(روایت ہے کہ\s+[^۔\n]{5,50}؟?)',
    r'(حکایت ہے کہ\s+[^۔\n]{5,50}؟?)',
    r'(واقعہ ہے کہ\s+[^۔\n]{5,50}؟?)',
    r'(واقعہ یہ ہے کہ\s+[^۔\n]{5,50}؟?)',
    r'(حضرت\s+[^\n۔]{3,25}\s+کا واقعہ\s+[^۔\n]{0,30})',
    r'(خواب میں دیکھا\s+کہ\s+[^۔\n]{5,50})',
    r'(فرمایا کہ\s+[^۔\n]{10,50})',
    r'(ارشاد فرمایا\s+[^۔\n]{5,50})',
    r'(بیان فرمایا\s+[^۔\n]{5,50})',
    r'(لکھا ہے کہ\s+[^۔\n]{5,50})',
    r'(آیا ہے کہ\s+[^۔\n]{5,50})',
    r'(ایک ولی\s+[^۔\n]{5,50})',
    r'(ایک درویش\s+[^۔\n]{5,50})',
    r'(ایک فقیر\s+[^۔\n]{5,50})',
    r'(ایک قصہ\s+[^۔\n]{0,40})',
    r'(ایک واقعہ\s+[^۔\n]{0,40})'
]
combined_pattern = re.compile("|".join(ALL_TRIGGERS), re.UNICODE)

# Complete Map of All 43 Volumes
VOLUMES_MAP = {
    1:  (3358, 2, 266),
    2:  (3368, 267, 491),
    3:  (3372, 492, 732),
    4:  (3381, 733, 972),
    5:  (3393, 973, 1278),
    6:  (3399, 1279, 1535),
    7:  (3407, 1536, 1808),
    8:  (3408, 1809, 2063),
    9:  (3412, 2064, 2342),
    10: (3423, 2343, 2623),
    11: (4808, 2624, 2896),
    12: (3434, 2897, 3169),
    13: (3445, 3170, 3450),
    14: (3456, 3451, 3739),
    15: (3461, 3740, 4020),
    16: (3466, 4021, 4293),
    17: (3471, 4294, 4574),
    18: (3475, 4575, 4839),
    19: (3483, 4840, 5128),
    20: (3485, 5129, 5400),
    21: (3490, 5401, 5657),
    22: (3491, 5658, 5931),
    23: (3494, 5932, 6188),
    24: (3505, 6189, 6453),
    25: (3513, 6454, 6702),
    26: (3524, 6703, 6975),
    27: (4793, 6976, 7231),
    28: (4794, 7232, 7483),
    29: (4795, 7484, 7761),
    30: (4796, 7762, 8023),
    31: (4792, 8024, 8269),
    32: (4797, 8270, 8494),
    33: (4798, 8495, 8740),
    34: (4799, 8741, 9001),
    35: (4801, 9002, 9261),
    36: (4802, 9262, 9541),
    37: (4803, 9542, 9797),
    38: (4804, 9798, 10070),
    39: (4805, 10071, 10322),
    40: (4806, 10323, 10584),
    41: (4788, 10585, 10854),
    42: (4790, 10855, 11111),
    43: (4791, 10855, 11111)  # Vol 43
}

def extract_waqiat_from_volume(conn, bid, vol_num):
    cur = conn.cursor()
    cur.execute("SELECT Title FROM Books WHERE BookID=?", (bid,))
    row = cur.fetchone()
    b_title = row[0] if row else f"خطبات فقیر جلد {vol_num}"

    event_repo = EventCandidateRepository(DB_PATH)
    taxo_repo = TaxonomyRepository(DB_PATH)
    tag_repo = EventCandidateTaxonomyRepository(DB_PATH)

    # Load existing records for dedup
    cur.execute("SELECT ChunkStartPage, ExtractedDataJson FROM EventCandidates WHERE BookID=? AND Status='confirmed'", (bid,))
    existing_records = []
    for sp, data_json in cur.fetchall():
        data = json.loads(data_json) if data_json else {}
        ex = data.get('quoted_excerpt') or data.get('background') or ''
        existing_records.append({'page': sp, 'excerpt': ex})

    # Load pages from DB
    cur.execute("SELECT PageNo, Content FROM Pages WHERE BookID=? ORDER BY PageNo", (bid,))
    pages = {pno: (c or '') for pno, c in cur.fetchall()}

    new_stories = []
    for pno in sorted(pages.keys()):
        content = pages[pno]
        if not content or len(content) < 100: continue
        clean_text = clean_xml_text(content)

        for match in combined_pattern.finditer(clean_text):
            start_idx = match.start()
            trigger_phrase = match.group(0).strip()
            story_span = clean_text[start_idx: start_idx + 850]

            if len(story_span) < 500 and (pno + 1) in pages:
                next_clean = clean_xml_text(pages[pno + 1])
                story_span += " " + next_clean[:400]

            sentences = re.split(r'([۔！？])', story_span)
            if len(sentences) > 4:
                story_span = "".join(sentences[:8]).strip()

            if len(story_span) < 120: continue

            # Dedup check
            is_dup = False
            for ex in existing_records:
                if abs(ex['page'] - pno) <= 1:
                    anchor1 = story_span[:45].strip()
                    anchor2 = story_span[50:95].strip() if len(story_span) > 100 else ""
                    if (anchor1 and anchor1 in ex['excerpt']) or (anchor2 and anchor2 in ex['excerpt']):
                        is_dup = True
                        break

            if not is_dup:
                for nst in new_stories:
                    if abs(nst['page'] - pno) <= 1 and story_span[:40] in nst['matn']:
                        is_dup = True
                        break

            if not is_dup:
                title = clean_title(trigger_phrase)
                if len(title) < 5: continue
                new_stories.append({'page': pno, 'title': title, 'matn': story_span})

    added = 0
    for s in new_stories:
        cit = f"{b_title}، صفحہ {urdu_num(s['page'])}"
        ev = ExtractedEvent(
            title=s['title'], alternate_names=[], subject="خطبات و مواعظ",
            date_hijri=None, date_gregorian=None, location=None,
            background=s['matn'], summary=s['title'],
            key_figures=["مولانا پیر ذوالفقار احمد نقشبندی"], quoted_excerpt=s['matn'], citation=cit
        )
        nid = event_repo.add_candidate(bid, s['page'], s['page'], ev)
        event_repo.confirm(nid)
        terms = [
            taxo_repo.get_or_create_term("subject", "خطبات و مواعظ", "ur"),
            taxo_repo.get_or_create_term("personality", "مولانا پیر ذوالفقار احمد نقشبندی", "ur")
        ]
        tag_repo.tag_candidate(nid, terms)
        added += 1

    return added

def ocr_single_volume(vol_num, client, doc, conn):
    if vol_num not in VOLUMES_MAP:
        return 0, 0

    bid, start_pdf_p, end_pdf_p = VOLUMES_MAP[vol_num]
    total_vol_pages = end_pdf_p - start_pdf_p + 1

    print("\n" + "=" * 80)
    print(f" 🚀 PROCESSING: خطبات فقیر — جلد {vol_num} (BookID: {bid}) | Pages: {start_pdf_p} to {end_pdf_p} ({total_vol_pages} pgs)")
    print("=" * 80)

    cur = conn.cursor()
    vol_text_file = os.path.join(OCR_TEXT_DIR, f"خطبات_فقیر_جلد_{vol_num:02d}.txt")

    # Get cached DB pages
    cur.execute("SELECT PageNo, Content FROM Pages WHERE BookID=?", (bid,))
    existing_db_pages = {r[0]: r[1] for r in cur.fetchall() if r[1] and len(r[1]) > 50}

    processed = 0
    skipped = 0

    for pdf_p in range(start_pdf_p, end_pdf_p + 1):
        book_page_no = pdf_p - start_pdf_p + 1
        p_index = pdf_p - 1

        page_file = os.path.join(OCR_TEXT_DIR, "pages", f"vol_{vol_num:02d}_p_{book_page_no:03d}.txt")

        # Cache check
        if os.path.exists(page_file) and os.path.getsize(page_file) > 50 and book_page_no in existing_db_pages:
            skipped += 1
            continue

        try:
            page = doc[p_index]
            pix = page.get_pixmap(dpi=300)
            img_bytes = pix.tobytes("png")

            image = vision.Image(content=img_bytes)
            response = client.document_text_detection(image=image)

            if response.error.message:
                print(f"  ❌ Error P.{pdf_p} (Book P.{book_page_no}): {response.error.message}")
                continue

            page_text = response.full_text_annotation.text.strip() if response.full_text_annotation else ""

            # Save individual page
            with open(page_file, "w", encoding="utf-8") as pf:
                pf.write(page_text)

            # Upsert into Pages in DB
            cur.execute("SELECT COUNT(*) FROM Pages WHERE BookID=? AND PageNo=?", (bid, book_page_no))
            exists = cur.fetchone()[0]
            if exists:
                cur.execute("UPDATE Pages SET Content=? WHERE BookID=? AND PageNo=?", (page_text, bid, book_page_no))
            else:
                cur.execute("INSERT INTO Pages (BookID, PageNo, Content, HadeesNumber, AyahNumber) VALUES (?, ?, ?, '', '')",
                            (bid, book_page_no, page_text))

            conn.commit()
            processed += 1

            if processed % 15 == 0 or processed == 1:
                print(f"  ⚡ OCR Progress: {processed + skipped:3d}/{total_vol_pages:3d} (P.{book_page_no:3d}) | Chars: {len(page_text):4d}")

        except Exception as e:
            print(f"  ❌ Exception P.{pdf_p}: {e}")

    # Rebuild complete Volume text file
    with open(vol_text_file, "w", encoding="utf-8") as vf:
        for p in range(1, total_vol_pages + 1):
            pf_path = os.path.join(OCR_TEXT_DIR, "pages", f"vol_{vol_num:02d}_p_{p:03d}.txt")
            if os.path.exists(pf_path):
                with open(pf_path, "r", encoding="utf-8") as pf:
                    vf.write(f"\n\n--- [صفحہ {p}] ---\n\n" + pf.read())

    print(f"  ✅ Vol {vol_num} OCR Complete: {processed} new pages OCR'd, {skipped} cached.")

    # Extract Waqiat
    new_waqiat = extract_waqiat_from_volume(conn, bid, vol_num)
    print(f"  🌟 Extracted +{new_waqiat} Confirmed Waqiat from Volume {vol_num}!")

    return processed, new_waqiat

def run_all_volumes(start_vol=2, end_vol=43):
    credentials = service_account.Credentials.from_service_account_file(CREDS_PATH)
    client = vision.ImageAnnotatorClient(credentials=credentials)
    doc = pymupdf.open(PDF_PATH)
    conn = sqlite3.connect(DB_PATH)

    print("=" * 85)
    print(f" PROCESSING KHUTBAT-E-FAQEER — ALL VOLUMES ({start_vol} to {end_vol})")
    print("=" * 85)

    total_pages_ocrd = 0
    total_waqiat_extracted = 0

    for v in range(start_vol, end_vol + 1):
        p_count, w_count = ocr_single_volume(v, client, doc, conn)
        total_pages_ocrd += p_count
        total_waqiat_extracted += w_count

    conn.close()
    doc.close()

    print("\n" + "=" * 85)
    print(f" 🏆 ALL REQUESTED VOLUMES ({start_vol} to {end_vol}) FINISHED!")
    print(f" Total New Pages OCR'd: {total_pages_ocrd} | Total Net-New Waqiat Added: +{total_waqiat_extracted}")
    print("=" * 85)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=int, default=2, help="Start volume (default 2)")
    parser.add_argument("--end", type=int, default=43, help="End volume (default 43)")
    args = parser.parse_args()

    run_all_volumes(args.start, args.end)
