import sqlite3, json, sys, re
sys.stdout.reconfigure(encoding='utf-8')

DB_PATH = r"F:\ISLAMIC RESEARCH HUB AI\data\books.db"
conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# Untapped Khutbat series that have text in DB
UNTAPPED_SERIES = [
    ("خطبات مدنی", "مولانا سید حسین احمد مدنیؒ", "خطبات و مواعظ"),
    ("مواعظ حسنہ", "مولانا شاہ حکیم محمد اخترؒ", "مواعظ و اخلاق"),
    ("خطبات آزاد", "مولانا ابوالکلام آزادؒ", "خطبات و بیانات"),
    ("خطبات بہاولپور", "ڈاکٹر محمد حمید اللہؒ", "سیرت و اسلامی تاریخ"),
    ("خطبات علی میاں", "مولانا سید ابوالحسن علی ندویؒ", "خطبات و بیانات"),
    ("صدارتی خطبات", "فضیلۃ الشیخ عبداللہ ناصر رحمانی", "خطبات و بیانات"),
    ("ریاض الخطبات", "حافظ نثار مصطفیٰ", "خطبات و مواعظ"),
    ("دروس و خطبات", "مولانا اسعد اعظمی", "خطبات و مواعظ")
]

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

def clean_xml_text(s):
    if not s: return ""
    s = re.sub(r'</?[^>]+>', ' ', s)
    s = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', ' ', s)
    return re.sub(r'\s+', ' ', s).strip()

print("=" * 80)
print(" SCANNING UNTAPPED KHUTBAT SERIES WITH REAL TEXT IN DATABASE")
print("=" * 80)

total_found_potential = 0

for s_kw, author, subj in UNTAPPED_SERIES:
    cur.execute("SELECT BookID, Title FROM Books WHERE Title LIKE ?", (f"%{s_kw}%",))
    books = cur.fetchall()

    series_vols_with_text = 0
    series_potential = 0
    series_pages = 0

    for bid, btitle in books:
        cur.execute("SELECT PageNo, Content FROM Pages WHERE BookID=? AND LENGTH(Content) > 50 ORDER BY PageNo", (bid,))
        pages = {pno: (c or '') for pno, c in cur.fetchall()}
        if not pages: continue

        series_vols_with_text += 1
        series_pages += len(pages)

        # Scan for stories
        for pno, content in pages.items():
            clean_text = clean_xml_text(content)
            for match in combined_pattern.finditer(clean_text):
                start_idx = match.start()
                story_span = clean_text[start_idx: start_idx + 600]
                if len(story_span) > 120:
                    series_potential += 1
                    break  # count 1 per page

    print(f"  {s_kw:25s} ({author[:25]}): {series_vols_with_text} Vols ({series_pages:5d} Pages) → Potential Waqiat: +{series_potential:4d}")
    total_found_potential += series_potential

print("-" * 80)
print(f" TOTAL POTENTIAL WAQIAT IN UNTAPPED KHUTBAT: +{total_found_potential}")
conn.close()
