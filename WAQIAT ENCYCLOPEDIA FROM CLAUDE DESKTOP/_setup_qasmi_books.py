import sqlite3, sys
sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect(r"F:\ISLAMIC RESEARCH HUB AI\data\books.db")
cur = conn.cursor()

volumes_to_ensure = [
    (3534, 'خطبات قاسمی جلد 1', 'حضرت مولانا ضیاء القاسمؒ', 1, 492, 'khutbat_qasmi_vol_1'),
    (3545, 'خطبات قاسمی جلد 2', 'حضرت مولانا ضیاء القاسمؒ', 2, 550, 'khutbat_qasmi_vol_2'),
    (35451, 'خطبات قاسمی جلد 3', 'حضرت مولانا ضیاء القاسمؒ', 3, 406, 'khutbat_qasmi_vol_3'),
    (35452, 'خطبات قاسمی جلد 4', 'حضرت مولانا ضیاء القاسمؒ', 4, 392, 'khutbat_qasmi_vol_4'),
    (3556, 'خطبات قاسمی جلد 5', 'حضرت مولانا ضیاء القاسمؒ', 5, 274, 'khutbat_qasmi_vol_5'),
    (3567, 'خطبات قاسمی جلد 6', 'حضرت مولانا ضیاء القاسمؒ', 6, 81, 'khutbat_qasmi_vol_6'),
]

for bid, title, author, vol, pcount, src in volumes_to_ensure:
    cur.execute("""
        INSERT OR REPLACE INTO Books (BookID, Source, Title, Author, Language, Category, PageCount, ChapterCount, VolumeNumber)
        VALUES (?, ?, ?, ?, 'ur', 'خطبات و مواعظ', ?, 1, ?)
    """, (bid, src, title, author, pcount, vol))

conn.commit()

print("Ensured Books records for all 6 volumes of Khutbat Qasmi:")
for r in cur.execute("SELECT BookID, Title, Author, VolumeNumber, PageCount FROM Books WHERE BookID IN (3534, 3545, 35451, 35452, 3556, 3567)").fetchall():
    print(" ", r)

conn.close()
