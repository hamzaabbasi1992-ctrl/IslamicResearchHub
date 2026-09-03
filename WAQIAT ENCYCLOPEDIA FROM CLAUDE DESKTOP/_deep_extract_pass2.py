import sqlite3, json, sys, re
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r"F:\ISLAMIC RESEARCH HUB AI\src")

from islamic_research_hub.application.event_extraction import ExtractedEvent
from islamic_research_hub.infrastructure.persistence.event_candidate_repository import EventCandidateRepository
from islamic_research_hub.infrastructure.persistence.taxonomy_repository import TaxonomyRepository
from islamic_research_hub.infrastructure.persistence.event_candidate_taxonomy_repository import EventCandidateTaxonomyRepository

DB_PATH = r"F:\ISLAMIC RESEARCH HUB AI\data\books.db"

URDU_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
def urdu_num(n): return str(n).translate(URDU_DIGITS)

def clean_xml_text(s):
    if not s: return ""
    s = re.sub(r'</?[^>]+>', ' ', s)
    s = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', ' ', s)
    return re.sub(r'\s+', ' ', s).strip()

def clean_title(t, maxlen=90):
    t = re.sub(r'^[\d۱-۹١-٩\(\)\*\-\s٭…_]+', '', t).strip()
    return (t[:maxlen] + "...") if len(t) > maxlen else t

MALFOOZAT_IDS = [72,73,74,75,76,77,78,79,80,81,82,83,84,85,86,87,88,89,90,91,92,93,100,101,102,103,104,105,106]

# EXTENDED TRIGGER SET — patterns missed by first pass
# Only include meaningful narrative triggers that yield real anecdotes (not generic speech)
EXTENDED_TRIGGERS = re.compile(
    r"("
    # Story verbs + "keh" construction
    r"(فرمایا کہ\s+[^۔\n]{10,60})"
    r"|(ارشاد فرمایا\s+[^۔\n]{5,50})"
    r"|(بیان فرمایا\s+[^۔\n]{5,50})"
    r"|(میں فرمایا کہ\s+[^۔\n]{5,50})"
    r"|(لکھا ہے کہ\s+[^۔\n]{5,50})"
    r"|(آیا ہے کہ\s+[^۔\n]{5,50})"
    r"|(انہوں نے کہا\s+[^۔\n]{5,50})"
    r"|(پیش آیا\s+[^۔\n]{0,40})"
    r"|(ذکر ہے کہ\s+[^۔\n]{5,50})"
    # Person-type triggers (expanded)
    r"|(ایک مولوی\s+[^۔\n]{5,50})"
    r"|(ایک عالم\s+[^۔\n]{5,50})"
    r"|(ایک ولی\s+[^۔\n]{5,50})"
    r"|(ایک درویش\s+[^۔\n]{5,50})"
    r"|(ایک فقیر\s+[^۔\n]{5,50})"
    r"|(ایک طالب علم\s+[^۔\n]{5,50})"
    r"|(ایک نوجوان\s+[^۔\n]{5,50})"
    r"|(ایک خاتون\s+[^۔\n]{5,50})"
    r"|(ایک آدمی\s+[^۔\n]{5,50})"
    r"|(ایک مرید\s+[^۔\n]{5,50})"
    r"|(ایک حکیم\s+[^۔\n]{5,50})"
    r"|(ایک تاجر\s+[^۔\n]{5,50})"
    r"|(ایک مریض\s+[^۔\n]{5,50})"
    r"|(ایک مسافر\s+[^۔\n]{5,50})"
    # Incident words
    r"|(ایک واقعہ\s+[^۔\n]{0,40})"
    r"|(یہ واقعہ\s+[^۔\n]{0,40})"
    r"|(اس واقعہ\s+[^۔\n]{0,40})"
    r"|(ایک قصہ\s+[^۔\n]{0,40})"
    r"|(قصہ یہ ہے\s+[^۔\n]{0,40})"
    r"|(کسی نے عرض\s+[^۔\n]{0,40})"
    r"|(مروی ہے کہ\s+[^۔\n]{5,50})"
    r"|(نقل ہے کہ\s+[^۔\n]{5,50})"
    r"|(کہا جاتا ہے کہ\s+[^۔\n]{5,50})"
    r")",
    re.UNICODE
)

# ALREADY USED triggers (to avoid re-extracting from same pages we already handled)
ALREADY_USED = [
    'ایک مرتبہ', 'ایک دفعہ', 'ایک بار', 'ایک بزرگ', 'ایک شخص',
    'ایک بادشاہ', 'ایک صاحب', 'منقول ہے کہ', 'روایت ہے کہ',
    'حکایت ہے کہ', 'واقعہ ہے کہ', 'واقعہ یہ ہے کہ', 'کا واقعہ', 'خواب میں دیکھا'
]

# High-noise filter: these generic phrases appear too often in non-narrative context
# Only accept فرمایا کہ if context is rich (≥600 chars around it)
REQUIRE_LENGTH = {'فرمایا کہ', 'ارشاد فرمایا', 'بیان فرمایا', 'میں فرمایا کہ', 'انہوں نے کہا'}


def extract_extended(conn, event_repo, taxo_repo, tag_repo, b_id):
    cur = conn.cursor()
    row = cur.execute("SELECT Title FROM Books WHERE BookID=?", (b_id,)).fetchone()
    if not row: return 0
    b_title = row[0]

    # Load existing records for dedup
    cur.execute("SELECT ChunkStartPage, ExtractedDataJson FROM EventCandidates WHERE BookID=? AND Status='confirmed'", (b_id,))
    existing_records = []
    for sp, data_json in cur.fetchall():
        data = json.loads(data_json) if data_json else {}
        ex = data.get('quoted_excerpt') or data.get('background') or ''
        existing_records.append({'page': sp, 'excerpt': ex})

    # Already-extracted pages (skip pages that already have enough records)
    extracted_pages = set(r['page'] for r in existing_records)

    # Load pages
    pages = dict(cur.execute(
        "SELECT PageNo, Content FROM Pages WHERE BookID=? ORDER BY PageNo", (b_id,)
    ).fetchall())

    new_stories = []

    for pno in sorted(pages.keys()):
        # Only process pages with NO existing record
        if pno in extracted_pages:
            continue

        content = pages[pno]
        if not content or len(content) < 120: continue
        clean = clean_xml_text(content)

        # Skip if page has one of the already-used triggers (already handled)
        if any(t in clean for t in ALREADY_USED):
            continue

        for match in EXTENDED_TRIGGERS.finditer(clean):
            trigger = match.group(0).strip()
            start_idx = match.start()

            # Require more context for high-noise triggers
            if any(hn in trigger for hn in REQUIRE_LENGTH):
                # Check surrounding context length
                surrounding = clean[max(0, start_idx - 50): start_idx + 600]
                if len(surrounding) < 450:
                    continue
                # Must contain at least 2 sentences
                if clean.count('۔', start_idx, start_idx + 500) < 2:
                    continue

            story_span = clean[start_idx: start_idx + 900]
            # Append next page if short
            if len(story_span) < 500 and (pno + 1) in pages:
                story_span += " " + clean_xml_text(pages[pno + 1])[:400]

            # Trim to natural sentence boundary
            sentences = re.split(r'([۔！？])', story_span)
            if len(sentences) > 4:
                story_span = "".join(sentences[:8]).strip()

            if len(story_span) < 150: continue

            # DEDUP AGAINST EXISTING
            is_dup = False
            for ex in existing_records:
                if abs(ex['page'] - pno) <= 1:
                    a1 = story_span[:45].strip()
                    a2 = story_span[50:95].strip()
                    if (a1 and a1 in ex['excerpt']) or (a2 and a2 in ex['excerpt']):
                        is_dup = True
                        break

            if not is_dup:
                for ns in new_stories:
                    if abs(ns['page'] - pno) <= 1 and story_span[:40] in ns['matn']:
                        is_dup = True
                        break

            if not is_dup:
                title = clean_title(trigger)
                if len(title) < 8: continue
                new_stories.append({'page': pno, 'title': title, 'matn': story_span})
                break  # one record per previously-unextracted page

    # Insert
    added = 0
    for s in new_stories:
        cit = f"{b_title}، صفحہ {urdu_num(s['page'])}"
        ev = ExtractedEvent(
            title=s['title'], alternate_names=[], subject="ملفوظات و سوانحی واقعات",
            date_hijri=None, date_gregorian=None, location=None,
            background=s['matn'], summary=s['title'],
            key_figures=["مولانا اشرف علی تھانویؒ"],
            quoted_excerpt=s['matn'], citation=cit
        )
        nid = event_repo.add_candidate(b_id, s['page'], s['page'], ev)
        event_repo.confirm(nid)
        terms = [
            taxo_repo.get_or_create_term("subject", "ملفوظات و سوانحی واقعات", "ur"),
            taxo_repo.get_or_create_term("personality", "مولانا اشرف علی تھانویؒ", "ur")
        ]
        tag_repo.tag_candidate(nid, terms)
        added += 1

    return added


def main():
    from sync_waqiat_app import sync_all

    conn = sqlite3.connect(DB_PATH)
    event_repo = EventCandidateRepository(DB_PATH)
    taxo_repo = TaxonomyRepository(DB_PATH)
    tag_repo = EventCandidateTaxonomyRepository(DB_PATH)

    print("=" * 72)
    print(" EXTENDED DEEP EXTRACTION — PASS 2 (Missed Triggers)")
    print(" ملفوظات حکیم الامت (29 Volumes) — فرمایا / ارشاد / واقعہ / شخص types")
    print("=" * 72)

    grand_total = 0
    for b_id in MALFOOZAT_IDS:
        before = conn.execute(
            "SELECT COUNT(*) FROM EventCandidates WHERE BookID=? AND Status='confirmed'", (b_id,)
        ).fetchone()[0]
        added = extract_extended(conn, event_repo, taxo_repo, tag_repo, b_id)
        after = before + added
        grand_total += added
        print(f"  BookID {b_id:4d}: {before:4d} → {after:4d}  (+{added:4d} net-new)")

    conn.close()

    print("=" * 72)
    print(f" TOTAL NET-NEW WAQIAT (Pass 2): {grand_total}")
    print("=" * 72)

    # Check new grand total
    final = sqlite3.connect(DB_PATH).execute(
        "SELECT COUNT(*) FROM EventCandidates WHERE Status='confirmed'"
    ).fetchone()[0]
    print(f" NEW GRAND TOTAL IN DATABASE: {final}")

    print("\nRunning sync_all()...")
    sync_all()

if __name__ == "__main__":
    main()
