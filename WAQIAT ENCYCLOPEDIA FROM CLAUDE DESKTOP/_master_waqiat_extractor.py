import sqlite3, json, sys, re, os
sys.stdout.reconfigure(encoding='utf-8')

DB_PATH = r"F:\ISLAMIC RESEARCH HUB AI\data\books.db"
conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

URDU_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
def urdu_num(n): return str(n).translate(URDU_DIGITS)
def clean(s):
    if not s: return ""
    s = re.sub(r'<[^>]+>', ' ', s)
    return re.sub(r'\s+', ' ', s).strip()

# ─────────────────────────────────────────────────────────────────
# ALL NARRATIVE TRIGGERS — combined comprehensive set
# ─────────────────────────────────────────────────────────────────
ALL_TRIGGERS = re.compile(
    r"("
    # Pass-1 triggers (may overlap some already-extracted pages — dedup handles it)
    r"(ایک مرتبہ\s+[^۔\n]{5,60})"
    r"|(ایک دفعہ\s+[^۔\n]{5,60})"
    r"|(ایک بار\s+[^۔\n]{5,60})"
    r"|(ایک بزرگ\s+[^۔\n]{5,60})"
    r"|(ایک شخص\s+[^۔\n]{5,60})"
    r"|(ایک بادشاہ\s+[^۔\n]{5,60})"
    r"|(ایک صاحب\s+[^۔\n]{5,60})"
    r"|(منقول ہے کہ\s+[^۔\n]{5,60})"
    r"|(روایت ہے کہ\s+[^۔\n]{5,60})"
    r"|(حکایت ہے کہ\s+[^۔\n]{5,60})"
    r"|(واقعہ ہے کہ\s+[^۔\n]{5,60})"
    r"|(واقعہ یہ ہے کہ\s+[^۔\n]{5,60})"
    r"|(کا واقعہ\s+[^۔\n]{0,40})"
    r"|(خواب میں دیکھا\s+کہ\s+[^۔\n]{5,60})"
    # Pass-2 triggers (new)
    r"|(فرمایا کہ\s+[^۔\n]{10,60})"
    r"|(ارشاد فرمایا\s+[^۔\n]{5,60})"
    r"|(بیان فرمایا\s+[^۔\n]{5,60})"
    r"|(میں فرمایا کہ\s+[^۔\n]{5,60})"
    r"|(لکھا ہے کہ\s+[^۔\n]{5,60})"
    r"|(آیا ہے کہ\s+[^۔\n]{5,60})"
    r"|(انہوں نے کہا\s+[^۔\n]{5,60})"
    r"|(پیش آیا\s+[^۔\n]{0,40})"
    r"|(ذکر ہے کہ\s+[^۔\n]{5,60})"
    r"|(نقل ہے کہ\s+[^۔\n]{5,60})"
    r"|(مروی ہے کہ\s+[^۔\n]{5,60})"
    r"|(کہا جاتا ہے کہ\s+[^۔\n]{5,60})"
    r"|(ایک مولوی\s+[^۔\n]{5,60})"
    r"|(ایک عالم\s+[^۔\n]{5,60})"
    r"|(ایک ولی\s+[^۔\n]{5,60})"
    r"|(ایک درویش\s+[^۔\n]{5,60})"
    r"|(ایک فقیر\s+[^۔\n]{5,60})"
    r"|(ایک طالب علم\s+[^۔\n]{5,60})"
    r"|(ایک نوجوان\s+[^۔\n]{5,60})"
    r"|(ایک خاتون\s+[^۔\n]{5,60})"
    r"|(ایک آدمی\s+[^۔\n]{5,60})"
    r"|(ایک مرید\s+[^۔\n]{5,60})"
    r"|(ایک حکیم\s+[^۔\n]{5,60})"
    r"|(ایک تاجر\s+[^۔\n]{5,60})"
    r"|(ایک مریض\s+[^۔\n]{5,60})"
    r"|(ایک مسافر\s+[^۔\n]{5,60})"
    r"|(ایک واقعہ\s+[^۔\n]{0,50})"
    r"|(یہ واقعہ\s+[^۔\n]{0,50})"
    r"|(اس واقعہ\s+[^۔\n]{0,50})"
    r"|(ایک قصہ\s+[^۔\n]{0,50})"
    r"|(قصہ یہ ہے\s+[^۔\n]{0,50})"
    r"|(کسی نے عرض\s+[^۔\n]{0,50})"
    r"|(حضرت\s+\S+\s+کا واقعہ\s+[^۔\n]{0,40})"
    r")",
    re.UNICODE
)

# High-noise triggers that need minimum surrounding context
HIGH_NOISE = {'فرمایا کہ', 'ارشاد فرمایا', 'بیان فرمایا', 'میں فرمایا کہ', 'انہوں نے کہا'}

def extract_waqiat_from_book(b_id, b_title, key_figure=""):
    """
    Extract ALL narrative waqiat from a book using the comprehensive trigger set.
    Strictly deduplicates against existing confirmed records.
    Returns list of new stories to insert.
    """
    # Load existing records
    existing = []
    for sp, dj in cur.execute(
        "SELECT ChunkStartPage, ExtractedDataJson FROM EventCandidates WHERE BookID=? AND Status='confirmed'", (b_id,)
    ).fetchall():
        d = json.loads(dj) if dj else {}
        ex = d.get('quoted_excerpt') or d.get('background') or ''
        existing.append({'page': sp, 'excerpt': ex})

    extracted_pgs = set(r['page'] for r in existing)

    pages = dict(cur.execute(
        "SELECT PageNo, Content FROM Pages WHERE BookID=? ORDER BY PageNo", (b_id,)
    ).fetchall())

    new_stories = []

    for pno in sorted(pages.keys()):
        text = pages[pno]
        if not text or len(text) < 100: continue
        c = clean(text)

        for match in ALL_TRIGGERS.finditer(c):
            trigger = match.group(0).strip()
            idx = match.start()

            # Noise filter for high-frequency generic triggers
            if any(hn in trigger for hn in HIGH_NOISE):
                surrounding = c[max(0, idx-50): idx+700]
                if len(surrounding) < 500 or c.count('۔', idx, idx+500) < 2:
                    continue

            span = c[idx: idx+900]
            if len(span) < 500 and (pno+1) in pages:
                span += " " + clean(pages[pno+1])[:400]

            parts = re.split(r'([۔！؟])', span)
            if len(parts) > 4:
                span = "".join(parts[:8]).strip()

            if len(span) < 130: continue

            # Dedup vs existing DB records
            is_dup = False
            for ex in existing:
                if abs(ex['page'] - pno) <= 1:
                    a1, a2 = span[:45].strip(), span[50:95].strip()
                    if (a1 and a1 in ex['excerpt']) or (a2 and a2 in ex['excerpt']):
                        is_dup = True; break

            if not is_dup:
                for ns in new_stories:
                    if abs(ns['page'] - pno) <= 1 and span[:40] in ns['span']:
                        is_dup = True; break

            if not is_dup:
                title = re.sub(r'^[\d۱-۹١-٩\(\)\*\-\s٭…_]+', '', trigger).strip()
                if len(title) < 8: continue
                new_stories.append({'page': pno, 'title': title[:90], 'span': span})
                break  # one per page

    return new_stories


def run_full_book_audit_and_extract(book_ids, subject_label, key_figure, subject_term):
    """
    Run full coverage extraction on a list of BookIDs.
    Inserts new records, returns total added.
    """
    import sys
    sys.path.insert(0, r"F:\ISLAMIC RESEARCH HUB AI\src")
    from islamic_research_hub.application.event_extraction import ExtractedEvent
    from islamic_research_hub.infrastructure.persistence.event_candidate_repository import EventCandidateRepository
    from islamic_research_hub.infrastructure.persistence.taxonomy_repository import TaxonomyRepository
    from islamic_research_hub.infrastructure.persistence.event_candidate_taxonomy_repository import EventCandidateTaxonomyRepository

    event_repo = EventCandidateRepository(DB_PATH)
    taxo_repo  = TaxonomyRepository(DB_PATH)
    tag_repo   = EventCandidateTaxonomyRepository(DB_PATH)

    grand = 0
    for b_id in book_ids:
        row = cur.execute("SELECT Title FROM Books WHERE BookID=?", (b_id,)).fetchone()
        if not row: continue
        b_title = row[0]

        before = cur.execute(
            "SELECT COUNT(*) FROM EventCandidates WHERE BookID=? AND Status='confirmed'", (b_id,)
        ).fetchone()[0]

        stories = extract_waqiat_from_book(b_id, b_title, key_figure)
        added = 0
        for s in stories:
            cit = f"{b_title}، صفحہ {urdu_num(s['page'])}"
            ev = ExtractedEvent(
                title=s['title'], alternate_names=[], subject=subject_label,
                date_hijri=None, date_gregorian=None, location=None,
                background=s['span'], summary=s['title'],
                key_figures=[key_figure] if key_figure else [],
                quoted_excerpt=s['span'], citation=cit
            )
            nid = event_repo.add_candidate(b_id, s['page'], s['page'], ev)
            event_repo.confirm(nid)
            terms = [taxo_repo.get_or_create_term("subject", subject_term, "ur")]
            if key_figure:
                terms.append(taxo_repo.get_or_create_term("personality", key_figure, "ur"))
            tag_repo.tag_candidate(nid, terms)
            added += 1

        after = before + added
        grand += added
        print(f"  [{b_id:5d}] {before:4d} → {after:4d}  (+{added:4d}) | {b_title[:55]}")

    return grand


# ─────────────────────────────────────────────────────────────────
# MAIN — run this directly for FULL audit of all books
# ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # This is the master script Gemini can run for any book group
    # Usage: python _master_waqiat_extractor.py <group>
    # Groups: malfoozat | khutbat | seerah | tafseer | all

    import sys
    group = sys.argv[1] if len(sys.argv) > 1 else "all"

    BOOK_GROUPS = {
        "malfoozat": {
            "ids": [72,73,74,75,76,77,78,79,80,81,82,83,84,85,86,87,88,89,90,91,92,93,100,101,102,103,104,105,106],
            "subject": "ملفوظات و سوانحی واقعات",
            "key_figure": "مولانا اشرف علی تھانویؒ",
            "term": "ملفوظات و سوانحی واقعات"
        },
        "islahi_khutbat": {
            "ids": list(range(107, 126)),  # اصلاحی خطبات BookIDs — adjust if needed
            "subject": "خطبات و مواعظ",
            "key_figure": "مفتی محمد تقی عثمانیؒ",
            "term": "خطبات و مواعظ"
        },
        "khutbat_mehmood": {
            "ids": list(range(126, 136)),
            "subject": "خطبات و مواعظ",
            "key_figure": "مولانا محمود الحسنؒ",
            "term": "خطبات و مواعظ"
        },
        # Add more groups as needed
    }

    if group == "all":
        targets = BOOK_GROUPS
    else:
        targets = {group: BOOK_GROUPS[group]} if group in BOOK_GROUPS else {}

    total_added = 0
    for grp_name, grp in targets.items():
        print(f"\n{'='*65}")
        print(f" GROUP: {grp_name}")
        print(f"{'='*65}")
        added = run_full_book_audit_and_extract(
            grp["ids"], grp["subject"], grp["key_figure"], grp["term"]
        )
        total_added += added
        print(f" Subtotal: +{added}")

    conn.close()

    final = sqlite3.connect(DB_PATH).execute(
        "SELECT COUNT(*) FROM EventCandidates WHERE Status='confirmed'"
    ).fetchone()[0]
    print(f"\n{'='*65}")
    print(f" TOTAL NET-NEW ADDED THIS RUN: {total_added}")
    print(f" NEW GRAND TOTAL IN DATABASE : {final}")
    print(f"{'='*65}")

    print("\nRunning sync_all()...")
    sys.path.insert(0, r"F:\ISLAMIC RESEARCH HUB AI")
    from sync_waqiat_app import sync_all
    sync_all()
    print("DONE.")
