# ============================================================
# GEMINI PROMPT — Copy everything below this line and paste into Gemini
# ============================================================

You are continuing the **واقعات انسائیکلوپیڈیا (Waqiat Encyclopedia)** project.
All your work files are in: `F:\ISLAMIC RESEARCH HUB AI\WAQIAT ENCYCLOPEDIA FROM CLAUDE DESKTOP\`
The database is at: `F:\ISLAMIC RESEARCH HUB AI\data\books.db`
The Python source code is at: `F:\ISLAMIC RESEARCH HUB AI\src`

---

## CURRENT STATE (as of handoff)
- Total confirmed Waqiat in DB: **25,162** (and still growing — Pass 2 may still be running)
- Pass 2 extraction (`_deep_extract_pass2.py`) was running in background — check if complete first

---

## CRITICAL RULES — NEVER BREAK THESE

1. **NEVER extract from `فضائل اعمال` (Fazail Amal)** — user excluded it
2. **NEVER delete existing records** — only ADD new ones
3. **ALWAYS use deduplication** — the scripts handle this automatically
4. **ALL scripts belong in**: `F:\ISLAMIC RESEARCH HUB AI\WAQIAT ENCYCLOPEDIA FROM CLAUDE DESKTOP\`
5. **NEVER save scripts in the main folder**: `F:\ISLAMIC RESEARCH HUB AI\` root

---

## YOUR TASK: Complete Full Coverage — All Books

### STEP 1 — Check if Pass 2 is still running

Run this:
```
cd F:\ISLAMIC RESEARCH HUB AI\WAQIAT ENCYCLOPEDIA FROM CLAUDE DESKTOP
python _count.py
```

If output is above 25,162 — Pass 2 completed. If still 23,631 — Pass 2 may have failed, re-run:
```
python _deep_extract_pass2.py
```

---

### STEP 2 — Run Full Library Coverage Scan

This finds ALL books that still have missed waqiat:
```
python _coverage_gap_analysis.py
```

Look for books with:
- `Coverage%` below 50%
- `Missed-only` column greater than 20

---

### STEP 3 — Run Missed Trigger Analysis

```
python _missed_trigger_analysis.py
```

This tells you exactly which Urdu phrase patterns are being missed in unextracted pages.

---

### STEP 4 — Extract From Low-Coverage Books

For each book that needs work, save and run `_extract_single_book.py` (code is inside `GEMINI_TASK_BRIEF.md`):

```
python _extract_single_book.py <BookID> "<Key Figure>" "<Subject>"
```

Examples:
```
python _extract_single_book.py 82 "مولانا اشرف علی تھانویؒ" "ملفوظات و سوانحی واقعات"
python _extract_single_book.py 93 "مولانا اشرف علی تھانویؒ" "ملفوظات و سوانحی واقعات"
python _extract_single_book.py 106 "مولانا اشرف علی تھانویؒ" "ملفوظات و سوانحی واقعات"
```

To find the BookID for any series, run:
```
python -c "
import sqlite3, sys
sys.stdout.reconfigure(encoding='utf-8')
keyword = 'خطبات رحیمی'
conn = sqlite3.connect(r'F:\ISLAMIC RESEARCH HUB AI\data\books.db')
for bid, title in conn.execute('SELECT BookID, Title FROM Books WHERE Title LIKE ?', (f'%{keyword}%',)).fetchall():
    print(f'[{bid}] {title}')
conn.close()
"
```

---

### STEP 5 — Sync After Each Batch

After every group of extractions:
```
cd F:\ISLAMIC RESEARCH HUB AI
python sync_waqiat_app.py
```

---

### STEP 6 — Rebuild APK When All Done

```
cd F:\ISLAMIC RESEARCH HUB AI\mobile
gradlew.bat assembleDebug
```

Then copy:
```
copy "F:\ISLAMIC RESEARCH HUB AI\mobile\app\build\outputs\apk\debug\app-debug.apk" "F:\ISLAMIC RESEARCH HUB AI\mobile\Maktaba_Shams.apk"
copy "F:\ISLAMIC RESEARCH HUB AI\mobile\app\build\outputs\apk\debug\app-debug.apk" "F:\ISLAMIC RESEARCH HUB AI\WAQIAT ENCYCLOPEDIA FROM CLAUDE DESKTOP\Maktaba_Shams.apk"
```

---

## BOOK SERIES → KEY FIGURE REFERENCE

| Series | Key Figure | Subject |
|--------|-----------|---------|
| ملفوظات حکیم الامت (BookIDs 72-106) | مولانا اشرف علی تھانویؒ | ملفوظات و سوانحی واقعات |
| اصلاحی خطبات | مفتی محمد تقی عثمانیؒ | خطبات و مواعظ |
| خطبات محمود | مولانا محمود الحسنؒ | خطبات و مواعظ |
| خطبات رحیمی | مفتی عبد الرحیم لاجپوریؒ | خطبات و مواعظ |
| خطبات حبان / تفسیری خطبات حبان | مولانا محمد حبانؒ | خطبات و مواعظ |
| خطبات رمضان المبارک | مختلف علماء | خطبات و مواعظ |
| بیانات سیرت نبویہ | مختلف علماء | سیرت النبی ﷺ واقعات |
| تاریخ دعوت و عزیمت | مولانا ابوالحسن علی ندویؒ | تاریخ دعوت و اسلامی تحریکات |
| قصص الانبیاء | مولانا ابوالحسن علی ندویؒ | انبیاء کرام کے واقعات |
| تفسیر عثمانی | علامہ شبیر احمد عثمانیؒ | شانِ نزول و قصص القرآن |
| معارف القرآن | مفتی محمد شفیعؒ | شانِ نزول و قصص القرآن |
| احیاء العلوم | امام ابو حامد الغزالیؒ | اخلاق و تزکیہ واقعات |
| سیرت النبی ﷺ | علامہ شبلی نعمانیؒ | سیرت النبی ﷺ واقعات |
| حکایات خلیل | مولانا خلیل احمد سہارنپوریؒ | اخلاق و تزکیہ واقعات |

---

## FINAL CHECK COMMAND

After everything, run this to confirm:
```
python _count.py
python _audit_db.py
```

Then report to user:
- Total Waqiat in DB
- Which books were processed
- Net new Waqiat added
- Whether sync and APK were done
