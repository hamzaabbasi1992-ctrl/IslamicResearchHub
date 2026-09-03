import os, sys, glob, re, sqlite3, json
from docx import Document
sys.stdout.reconfigure(encoding='utf-8')

aitikaf_dir = r"E:\KHANQAH\AITIKAAF BAYANAT\book formatted"
sunday_dir = r"E:\KHANQAH\SUNDAY BAYANS (FINAL)\bayan to text gemini output"

URDU_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
def urdu_num(n): return str(n).translate(URDU_DIGITS)

def clean_xml_text(s):
    if not s: return ""
    s = re.sub(r'</?[^>]+>', ' ', s)
    s = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', ' ', s)
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

print("=" * 85)
print(" TESTING WAQIAT EXTRACTION FROM AITIKAF & SUNDAY BAYANAT")
print("=" * 85)

# 1. Test Aitikaf DOCX Books
aitikaf_files = sorted(glob.glob(os.path.join(aitikaf_dir, "*.docx")))
aitikaf_stories = []

for docx_p in aitikaf_files:
    fname = os.path.basename(docx_p)
    if "فہرست" in fname: continue
    year_match = re.search(r'\d{4}', fname)
    year = year_match.group(0) if year_match else "اعتکاف"

    try:
        doc = Document(docx_p)
        full_text = "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
        clean_text = clean_xml_text(full_text)

        for match in combined_pattern.finditer(clean_text):
            start_idx = match.start()
            trigger_phrase = match.group(0).strip()
            story_span = clean_text[start_idx: start_idx + 850]

            sentences = re.split(r'([۔！？])', story_span)
            if len(sentences) > 4:
                story_span = "".join(sentences[:8]).strip()

            if len(story_span) < 120: continue

            # Dedup
            if any(story_span[:40] in s['matn'] for s in aitikaf_stories):
                continue

            title = clean_title(trigger_phrase)
            if len(title) < 5: continue

            cit = f"بیاناتِ اعتکاف {year}ء (خانقاہ امدادیہ غفوریہ)"
            aitikaf_stories.append({'source': fname, 'title': title, 'matn': story_span, 'citation': cit})

    except Exception as e:
        print(f"Error reading {fname}: {e}")

print(f"✅ Extracted from Aitikaf Bayanat Books: {len(aitikaf_stories)} Waqiat")

# 2. Test Sunday Bayanat TXT Files
sunday_files = sorted(glob.glob(os.path.join(sunday_dir, "**", "*.txt"), recursive=True))
sunday_stories = []

for txt_p in sunday_files:
    fname = os.path.basename(txt_p)
    # Extract date/title from filename or content
    clean_fname = re.sub(r'^\d+\s*[-_)]\s*', '', fname).replace('.txt', '')

    try:
        with open(txt_p, "r", encoding="utf-8", errors="ignore") as tf:
            content = tf.read()
        clean_text = clean_xml_text(content)

        # Extract title from content if present
        title_match = re.search(r'عنوان[:\s]+([^\n\r]+)', clean_text)
        bayan_title = title_match.group(1).replace('*', '').strip() if title_match else clean_fname

        for match in combined_pattern.finditer(clean_text):
            start_idx = match.start()
            trigger_phrase = match.group(0).strip()
            story_span = clean_text[start_idx: start_idx + 850]

            sentences = re.split(r'([۔！？])', story_span)
            if len(sentences) > 4:
                story_span = "".join(sentences[:8]).strip()

            if len(story_span) < 120: continue

            # Dedup
            if any(story_span[:40] in s['matn'] for s in sunday_stories):
                continue

            title = clean_title(trigger_phrase)
            if len(title) < 5: continue

            cit = f"مواعظ اتوار، بیان: {bayan_title} (خانقاہ امدادیہ غفوریہ)"
            sunday_stories.append({'source': fname, 'title': title, 'matn': story_span, 'citation': cit})

    except Exception as e:
        pass

print(f"✅ Extracted from Sunday Transcribed Bayanat: {len(sunday_stories)} Waqiat")
print(f"🌟 TOTAL COMBINED KHANQAH WAQIAT: {len(aitikaf_stories) + len(sunday_stories)}")

print("\n--- SAMPLE 5 AITIKAF STORIES ---")
for s in aitikaf_stories[:5]:
    print(f"✦ {s['title']}")
    print(f"  حوالہ: {s['citation']}")
    print(f"  متن: {s['matn'][:120]}...\n")

print("\n--- SAMPLE 5 SUNDAY STORIES ---")
for s in sunday_stories[:5]:
    print(f"✦ {s['title']}")
    print(f"  حوالہ: {s['citation']}")
    print(f"  متن: {s['matn'][:120]}...\n")
