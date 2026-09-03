import sqlite3, json, sys
sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect(r"F:\ISLAMIC RESEARCH HUB AI\data\books.db")
cur = conn.cursor()

print("=== 1. TOTAL CONFIRMED WAQIAT ===")
total = cur.execute("SELECT COUNT(*) FROM EventCandidates WHERE Status='confirmed'").fetchone()[0]
print(f"Total: {total}")

print()
print("=== 2. PER-BOOK COUNTS FOR MALFOOZAT (BookIDs 72-106) ===")
rows = cur.execute("""
    SELECT b.BookID, b.Title, COUNT(ec.EventCandidateID) as cnt
    FROM Books b
    LEFT JOIN EventCandidates ec ON b.BookID=ec.BookID AND ec.Status='confirmed'
    WHERE b.BookID IN (72,73,74,75,76,77,78,79,80,81,82,83,84,85,86,87,88,89,90,91,92,93,100,101,102,103,104,105,106)
    GROUP BY b.BookID, b.Title
    ORDER BY b.BookID
""").fetchall()
malfoozat_total = 0
for bid, title, cnt in rows:
    print(f"  BookID {bid:4d}: {cnt:5d}  | {title[:55]}")
    malfoozat_total += cnt
print(f"  MALFOOZAT SUBTOTAL: {malfoozat_total}")

print()
print("=== 3. SAMPLE 5 RECORDS — TEXT QUALITY CHECK ===")
samples = cur.execute("""
    SELECT ec.BookID, ec.ChunkStartPage, ec.ExtractedDataJson
    FROM EventCandidates ec
    WHERE ec.BookID BETWEEN 73 AND 106 AND ec.Status='confirmed'
    ORDER BY ec.EventCandidateID DESC LIMIT 5
""").fetchall()
for bid, pg, djson in samples:
    d = json.loads(djson) if djson else {}
    excerpt = (d.get("quoted_excerpt") or d.get("background") or "")[:150]
    print(f"  BookID={bid}, Page={pg}: {excerpt}")
    print()

print("=== 4. HIGH-DENSITY PAGE CHECK (potential over-extraction) ===")
dup_check = cur.execute("""
    SELECT BookID, ChunkStartPage, COUNT(*) as c
    FROM EventCandidates
    WHERE Status='confirmed' AND BookID BETWEEN 72 AND 106
    GROUP BY BookID, ChunkStartPage
    HAVING c > 15
    ORDER BY c DESC LIMIT 15
""").fetchall()
if dup_check:
    print("  WARNING — pages with >15 records (may be over-extracted):")
    for bid, pg, c in dup_check:
        print(f"    BookID={bid}, Page={pg}: {c} records")
else:
    print("  OK — No page has >15 records. Density looks healthy.")

print()
print("=== 5. CROSS-CHECK: Script claimed +5694, verify by pre/post counts ===")
pre_total = 17937
post_total = total
claimed_added = 5694
actual_diff = post_total - pre_total
print(f"  Pre-extraction baseline: {pre_total}")
print(f"  Post-extraction total  : {post_total}")
print(f"  Actual difference      : {actual_diff}")
print(f"  Script claimed added   : {claimed_added}")
if actual_diff == claimed_added:
    print("  RESULT: MATCH — numbers are consistent.")
elif abs(actual_diff - claimed_added) < 50:
    print(f"  RESULT: NEAR MATCH (diff={abs(actual_diff - claimed_added)}) — likely minor rounding.")
else:
    print(f"  RESULT: MISMATCH — discrepancy of {abs(actual_diff - claimed_added)}")

print()
print("=== 6. STATUS DISTRIBUTION (full DB) ===")
statuses = cur.execute("SELECT Status, COUNT(*) FROM EventCandidates GROUP BY Status").fetchall()
for s, c in statuses:
    print(f"  {s}: {c}")

print()
print("=== 7. SPOT-CHECK DEDUP — any exact duplicate excerpts on same book/page? ===")
dups = cur.execute("""
    SELECT BookID, ChunkStartPage, ExtractedDataJson, COUNT(*) as c
    FROM EventCandidates
    WHERE Status='confirmed' AND BookID BETWEEN 72 AND 106
    GROUP BY BookID, ChunkStartPage, ExtractedDataJson
    HAVING c > 1
    LIMIT 5
""").fetchall()
if dups:
    print(f"  DUPLICATES FOUND: {len(dups)} exact JSON duplicates exist!")
    for bid, pg, dj, c in dups:
        d = json.loads(dj) if dj else {}
        print(f"    BookID={bid}, Page={pg}, count={c}: {str(d)[:80]}")
else:
    print("  CLEAN — Zero exact JSON duplicates on same book/page found.")

conn.close()
print()
print("=== AUDIT COMPLETE ===")
