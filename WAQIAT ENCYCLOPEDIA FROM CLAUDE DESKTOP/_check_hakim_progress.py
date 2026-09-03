import os, sys, glob, sqlite3
sys.stdout.reconfigure(encoding='utf-8')

pages_dir = r"F:\کتب\ocr text books\خطبات حکیم الاسلام\pages"
txt_dir = r"F:\کتب\ocr text books\خطبات حکیم الاسلام"
db_path = r"F:\ISLAMIC RESEARCH HUB AI\data\books.db"

# Count total page files
all_page_files = glob.glob(os.path.join(pages_dir, "*.txt"))

# Count volume text files
vol_text_files = glob.glob(os.path.join(txt_dir, "خطبات_حکیم_الاسلام_جلد_*.txt"))

# Check DB
conn = sqlite3.connect(db_path)
cur = conn.cursor()

total_db_waqiat = cur.execute("SELECT COUNT(*) FROM EventCandidates WHERE Status='confirmed'").fetchone()[0]

cur.execute("""
    SELECT b.BookID, b.Title, COUNT(ec.EventCandidateID) as WaqiatCount,
           (SELECT COUNT(*) FROM Pages p WHERE p.BookID=b.BookID AND LENGTH(p.Content)>50) as TextPages
    FROM Books b
    LEFT JOIN EventCandidates ec ON b.BookID=ec.BookID AND ec.Status='confirmed'
    WHERE b.BookID IN (5091, 5102, 5113, 5123, 5128)
    GROUP BY b.BookID, b.Title
    ORDER BY b.BookID
""")
hakim_vols = cur.fetchall()
conn.close()

print("=" * 85)
print(f" KHUTBAT HAKIM UL ISLAM OCR & EXTRACTION PROGRESS (Task-4997)")
print("=" * 85)
print(f" Total Single Page Text Files Generated: {len(all_page_files)} / 3002 pages")
print(f" Total Complete Volume Text Files: {len(vol_text_files)} volumes")
print(f" Current Global Waqiat in Database: {total_db_waqiat}\n")

print(f"{'BookID':>7} | {'Text Pages':>10} | {'Waqiat Extracted':>16} | Title")
print("-" * 85)
total_hakim_waqiat = 0
total_hakim_pages = 0
for bid, title, w_count, t_pages in hakim_vols:
    print(f"{bid:>7} | {t_pages:>10} | {w_count:>16} | {title}")
    total_hakim_waqiat += w_count
    total_hakim_pages += t_pages

print("-" * 85)
print(f" TOTAL COMPLETED SO FAR: {total_hakim_pages} Pages | {total_hakim_waqiat} Waqiat across 5 Volumes")
print("=" * 85)
