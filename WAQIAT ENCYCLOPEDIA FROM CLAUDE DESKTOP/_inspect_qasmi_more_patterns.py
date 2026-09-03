import sqlite3, json, sys, re
sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect(r"F:\ISLAMIC RESEARCH HUB AI\data\books.db")
cur = conn.cursor()

# Get all pages of Khutbat Qasmi
cur.execute("SELECT BookID, PageNo, Content FROM Pages WHERE BookID IN (3534, 3545, 35451, 35452, 3556, 3567) ORDER BY BookID, PageNo")
pages = cur.fetchall()
print(f"Total Pages loaded for Khutbat Qasmi: {len(pages)}")

# Narrative patterns:
ADDITIONAL_PATTERNS = [
    r'(ایک دفعہ کا ذکر ہے[^۔\n]{5,50})',
    r'(ایک واقعہ یہ بھی ہے[^۔\n]{5,50})',
    r'(ایک عجیب واقعہ[^۔\n]{5,50})',
    r'(ایک عبرتناک واقعہ[^۔\n]{5,50})',
    r'(ایک شخص نے عرض کیا[^۔\n]{5,50})',
    r'(ایک دیہاتی نے آکر[^۔\n]{5,50})',
    r'(ایک اعرابی نے[^۔\n]{5,50})',
    r'(ایک یہودی نے[^۔\n]{5,50})',
    r'(ایک عیسائی نے[^۔\n]{5,50})',
    r'(حضرت عمر رضی اللہ عنہ کا واقعہ[^۔\n]{0,40})',
    r'(حضرت علی رضی اللہ عنہ کا واقعہ[^۔\n]{0,40})',
    r'(حضرت عثمان رضی اللہ عنہ کا واقعہ[^۔\n]{0,40})',
    r'(حضرت ابوبکر رضی اللہ عنہ کا واقعہ[^۔\n]{0,40})'
]
combined_add = re.compile("|".join(ADDITIONAL_PATTERNS), re.UNICODE)

found = []
for bid, pno, c in pages:
    if not c: continue
    clean_c = re.sub(r'\s+', ' ', c).strip()
    for m in combined_add.finditer(clean_c):
        trig = m.group(0).strip()
        span = clean_c[m.start(): m.start() + 700]
        found.append((bid, pno, trig, span[:120]))

print(f"Found {len(found)} additional narrative candidates:")
for bid, pno, trig, s in found[:15]:
    print(f"  BookID {bid} - Page {pno}: [{trig}] -> {s}...\n")

conn.close()
