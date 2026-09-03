import sqlite3, sys, re
sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect(r"F:\ISLAMIC RESEARCH HUB AI\data\books.db")
cur = conn.cursor()

cur.execute("SELECT BookID, PageNo, Content FROM Pages WHERE BookID IN (3534, 3545, 35451, 35452, 3556, 3567) ORDER BY BookID, PageNo")
pages = cur.fetchall()

print(f"Total Pages in Khutbat Qasmi: {len(pages)}")

# Keywords in headings that indicate a story/incident
STORY_HEADING_KEYWORDS = [
    r'واقعہ', r'قصہ', r'شہادت', r'ہجرت', r'غزوہ', r'خواب', r'معجزہ', r'ملاقات',
    r'وفات', r'تعاقب', r'داستان', r'مناظرہ', r'توبہ', r'ایمان', r'بیعت',
    r'شفاعت', r'گرفتاری', r'رہائی', r'مکالمہ', r'امتحان', r'آزمائش'
]
heading_pattern = re.compile(r'^\s*([^\n۔؟!]{3,50})\s*$', re.MULTILINE)

found_heading_stories = []

for bid, pno, content in pages:
    if not content: continue
    lines = content.split('\n')
    for i, line in enumerate(lines):
        line_clean = line.strip()
        if 4 < len(line_clean) < 45 and not line_clean.endswith(('۔', '!', '؟', '،')):
            # Check if it matches any story heading keyword
            if any(re.search(kw, line_clean) for kw in STORY_HEADING_KEYWORDS):
                # Check following text (next 3 to 10 lines)
                following_text = " ".join(lines[i+1: i+12]).strip()
                words = following_text.split()
                if len(words) > 25:
                    story_markers = ["تھا", "تھی", "تھے", "گئے", "آئے", "کہا", "عرض کیا", "پوچھا", "جواب دیا", "دیکھا", "فرمایا"]
                    if sum(1 for sm in story_markers if sm in following_text) >= 3:
                        found_heading_stories.append((bid, pno, line_clean, following_text[:140]))

print(f"\nFound {len(found_heading_stories)} Heading-Based Narrative Incidents!")
print("\n--- SAMPLE 15 HEADING-BASED STORIES ---")
for bid, pno, h, preview in found_heading_stories[:15]:
    print(f"  📖 [BookID {bid} - Page {pno}]: ✦ {h}")
    print(f"     متن: {preview}...\n")

conn.close()
