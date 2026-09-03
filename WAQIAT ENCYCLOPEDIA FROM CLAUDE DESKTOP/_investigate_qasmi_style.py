import sqlite3, json, sys, re
sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect(r"F:\ISLAMIC RESEARCH HUB AI\data\books.db")
cur = conn.cursor()

cur.execute("SELECT BookID, PageNo, Content FROM Pages WHERE BookID IN (3534, 3545, 35451, 35452, 3556, 3567) ORDER BY BookID, PageNo")
pages = cur.fetchall()
print(f"Total pages inspected: {len(pages)}")

# Broader oratorical story anchors common in Jalsa sermons
ORATOR_STORY_PATTERNS = [
    r'(جب\s+حضرت\s+[^\n۔]{3,30}\s+(?:تشریف لائے|تشریف لے گئے|نے دیکھا|کے پاس|نے فرمایا|نے عرض کیا|روانہ ہوئے|کا انتقال ہوا|شہید ہوئے|کی وفات ہوئی)[^۔\n]{5,60})',
    r'(روایت\s+میں\s+آتا\s+ہے\s+کہ\s+[^۔\n]{10,60})',
    r'(تاریخ\s+میں\s+آتا\s+ہے\s+کہ\s+[^۔\n]{10,60})',
    r'(تاریخ\s+کا\s+واقعہ\s+ہے\s+کہ\s+[^۔\n]{10,60})',
    r'(ایک\s+دن\s+(?:حضور|آپ|نبی|رسول|حضرت|صحابہ|سیدنا)[^۔\n]{10,60})',
    r'(واقعہ\s+سناتا\s+ہوں\s+[^۔\n]{5,50})',
    r'(واقعہ\s+عرض\s+کرتا\s+ہوں\s+[^۔\n]{5,50})',
    r'(واقعہ\s+ملاحظہ\s+فرمائیں\s+[^۔\n]{5,50})',
    r'(واقعہ\s+کچھ\s+یوں\s+ہے\s+کہ\s+[^۔\n]{5,50})',
    r'(بخاری\s+شریف\s+میں\s+واقعہ\s+ہے\s+کہ\s+[^۔\n]{5,50})',
    r'(مسلم\s+شریف\s+میں\s+واقعہ\s+ہے\s+کہ\s+[^۔\n]{5,50})',
    r'(صلح\s+حدیبیہ\s+کے\s+موقع\s+پر\s+[^۔\n]{10,60})',
    r'(غزوۂ\s+(?:بدر|احد|خندق|خیبر|تبوک|حنین)\s+کے\s+موقع\s+پر\s+[^۔\n]{10,60})',
    r'(حضرت\s+[^\n۔]{3,25}\s+کی\s+وفات\s+کا\s+واقعہ\s+[^۔\n]{0,35})',
    r'(حضرت\s+[^\n۔]{3,25}\s+کی\s+شہادت\s+کا\s+واقعہ\s+[^۔\n]{0,35})'
]

compiled_orator = re.compile("|".join(ORATOR_STORY_PATTERNS), re.UNICODE)

found_stories = []
for bid, pno, content in pages:
    if not content: continue
    clean_c = re.sub(r'\s+', ' ', content).strip()
    
    for m in compiled_orator.finditer(clean_c):
        trig = m.group(0).strip()
        span = clean_c[m.start(): m.start() + 800]
        words = span.split()
        if len(words) < 30: continue
        
        # Check story narrative markers
        story_markers = ["تھا", "تھی", "تھے", "گئے", "آئے", "کہا", "عرض کیا", "پوچھا", "جواب دیا", "دیکھا", "فرمایا"]
        if sum(1 for sm in story_markers if sm in span) >= 3:
            found_stories.append((bid, pno, trig, span[:140]))

print(f"\nPotential Additional Narrative Incidents Found: {len(found_stories)}")
print("\n--- SAMPLE 15 MISSED STORIES FROM KHUTBAT QASMI ---")
for bid, pno, trig, preview in found_stories[:15]:
    print(f"  📖 [BookID {bid} - Page {pno}]:")
    print(f"     عنوان: {trig}")
    print(f"     متن: {preview}...\n")

conn.close()
