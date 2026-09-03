import sqlite3, sys
sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect(r"F:\ISLAMIC RESEARCH HUB AI\data\books.db")
cur = conn.cursor()

VOLUMES_SETUP = [
    (3601, 'خطبات حکیم العصر جلد 1', 'حضرت مولانا عبد المجید لدھیانوی مدظلہ', 1, 380, 'khutbat_hakeem_ul_asr_vol_1'),
    (3602, 'خطبات حکیم العصر جلد 2', 'حضرت مولانا عبد المجید لدھیانوی مدظلہ', 2, 379, 'khutbat_hakeem_ul_asr_vol_2'),
    (3603, 'خطبات حکیم العصر جلد 3', 'حضرت مولانا عبد المجید لدھیانوی مدظلہ', 3, 385, 'khutbat_hakeem_ul_asr_vol_3'),
    (3604, 'خطبات حکیم العصر جلد 4', 'حضرت مولانا عبد المجید لدھیانوی مدظلہ', 4, 300, 'khutbat_hakeem_ul_asr_vol_4'),
    (3605, 'خطبات حکیم العصر جلد 5', 'حضرت مولانا عبد المجید لدھیانوی مدظلہ', 5, 349, 'khutbat_hakeem_ul_asr_vol_5'),
    (3606, 'خطبات حکیم العصر جلد 6', 'حضرت مولانا عبد المجید لدھیانوی مدظلہ', 6, 374, 'khutbat_hakeem_ul_asr_vol_6'),
    (3607, 'خطبات حکیم العصر جلد 7', 'حضرت مولانا عبد المجید لدھیانوی مدظلہ', 7, 354, 'khutbat_hakeem_ul_asr_vol_7'),
    (3608, 'خطبات حکیم العصر جلد 8', 'حضرت مولانا عبد المجید لدھیانوی مدظلہ', 8, 286, 'khutbat_hakeem_ul_asr_vol_8'),
    (3609, 'خطبات حکیم العصر جلد 9', 'حضرت مولانا عبد المجید لدھیانوی مدظلہ', 9, 346, 'khutbat_hakeem_ul_asr_vol_9'),
    (3610, 'خطبات حکیم العصر جلد 10', 'حضرت مولانا عبد المجید لدھیانوی مدظلہ', 10, 313, 'khutbat_hakeem_ul_asr_vol_10'),
    (3611, 'خطبات حکیم العصر جلد 11', 'حضرت مولانا عبد المجید لدھیانوی مدظلہ', 11, 357, 'khutbat_hakeem_ul_asr_vol_11'),
    (3612, 'خطبات حکیم العصر جلد 12', 'حضرت مولانا عبد المجید لدھیانوی مدظلہ', 12, 404, 'khutbat_hakeem_ul_asr_vol_12'),
]

for bid, title, author, vol, pcount, src in VOLUMES_SETUP:
    cur.execute("""
        INSERT OR REPLACE INTO Books (BookID, Source, Title, Author, Language, Category, PageCount, ChapterCount, VolumeNumber)
        VALUES (?, ?, ?, ?, 'ur', 'خطبات و مواعظ', ?, 1, ?)
    """, (bid, src, title, author, pcount, vol))

conn.commit()

print("Ensured Books records for all 12 volumes of Khutbat Hakeem-ul-Asr:")
for r in cur.execute("SELECT BookID, Title, Author, VolumeNumber, PageCount FROM Books WHERE BookID BETWEEN 3601 AND 3612 ORDER BY BookID").fetchall():
    print(" ", r)

conn.close()
