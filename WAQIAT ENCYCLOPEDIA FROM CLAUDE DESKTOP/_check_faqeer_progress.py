import os, sys, glob, sqlite3
sys.stdout.reconfigure(encoding='utf-8')

pages_dir = r"F:\کتب\ocr text books\خطبات فقیر\pages"
txt_dir = r"F:\کتب\ocr text books\خطبات فقیر"
db_path = r"F:\ISLAMIC RESEARCH HUB AI\data\books.db"

# Count total page files
all_page_files = glob.glob(os.path.join(pages_dir, "*.txt"))

# Count volume text files
vol_text_files = glob.glob(os.path.join(txt_dir, "خطبات_فقیر_جلد_*.txt"))

# Check DB
conn = sqlite3.connect(db_path)
cur = conn.cursor()

# Get total confirmed Waqiat in DB
total_db_waqiat = cur.execute("SELECT COUNT(*) FROM EventCandidates WHERE Status='confirmed'").fetchone()[0]

# Get Waqiat count per Khutbat Faqeer volume
cur.execute("""
    SELECT b.BookID, b.Title, COUNT(ec.EventCandidateID) as WaqiatCount,
           (SELECT COUNT(*) FROM Pages p WHERE p.BookID=b.BookID AND LENGTH(p.Content)>50) as TextPages
    FROM Books b
    LEFT JOIN EventCandidates ec ON b.BookID=ec.BookID AND ec.Status='confirmed'
    WHERE b.Title LIKE '%خطبات فقیر%' AND b.BookID >= 3358 AND b.BookID <= 4808
    GROUP BY b.BookID, b.Title
    HAVING TextPages > 0
    ORDER BY b.BookID
""")
faqeer_vols = cur.fetchall()
conn.close()

print("=" * 80)
print(f" KHUTBAT-E-FAQEER OCR & EXTRACTION PROGRESS (Task-4846)")
print("=" * 80)
print(f" Total Single Page Text Files Generated: {len(all_page_files)} pages")
print(f" Total Complete Volume Text Files: {len(vol_text_files)} volumes")
print(f" Current Global Waqiat in Database: {total_db_waqiat}\n")

print(f"{'BookID':>7} | {'Text Pages':>10} | {'Waqiat Extracted':>16} | Title")
print("-" * 80)
total_faqeer_waqiat = 0
total_faqeer_pages = 0
for bid, title, w_count, t_pages in faqeer_vols:
    print(f"{bid:>7} | {t_pages:>10} | {w_count:>16} | {title}")
    total_faqeer_waqiat += w_count
    total_faqeer_pages += t_pages

print("-" * 80)
print(f" TOTAL COMPLETED SO FAR: {total_faqeer_pages} Pages | {total_faqeer_waqiat} Waqiat across {len(faqeer_vols)} Volumes")
print("=" * 80)
