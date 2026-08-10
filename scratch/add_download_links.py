"""One-off: append a researched-links column to the Khutbat/Bayanat
to-be-downloaded CSV, covering both the 11 'Not In Library' rows and the
15 'INCOMPLETE' rows (missing some volumes of a series already present)."""
import csv

PATH = "Urdu_Khutbat_Bayanat_ to be downloaded.csv"

# SeriesID -> researched links. Verified by web search 2026-08-10;
# not fetched/downloaded, just located - review before downloading.
LINKS: dict[str, str] = {
    # --- Not In Library (11) ---
    "113": (
        "https://archive.org/details/KhutbatEBahawalPurByDr.MuhammadHamidullahComplete "
        "(complete, all volumes) | https://archive.org/details/20210118_20210118_0208 "
        "| https://hamidullah.info/khutbat-e-bahawalpur-complete/"
    ),
    "114": (
        "NOT CONFIDENTLY LOCATED under this exact title - closest matches: "
        "https://www.rekhta.org/authors/husain-ahmad-madani/ebooks (author's ebook list, browse for the right title) "
        "| https://archive.org/details/maktabasheikhulislam_202004 (Sheikh-ul-Islam Hussain Ahmad Madani library collection) "
        "| https://archive.org/details/Maktaba-Sufi-Abdul-Hameed-Sawati-ra (has a different compiled title 'خطباتِ صدارت'). "
        "Recommend checking these collections manually rather than trusting an auto-match."
    ),
    "115": (
        "CAUTION - author mismatch: besturdubooks.net's 'Khutbat e Usmani' is by Mufti Muhammad TAQI Usmani (son), "
        "not Mufti Muhammad SHAFI Usmani (father) as this row lists - verify before downloading: "
        "https://besturdubooks.net/khutbat-e-usmani/ | closer possible match for Mufti Shafi: "
        "https://archive.org/details/109-mawaiz-malfoozat-mufti-m.-shafee-sahib-rehmahullah "
        "| https://archive.org/details/20251014_20251014_0913"
    ),
    "116": (
        "NOT CONFIDENTLY LOCATED as a text/PDF series - Tariq Jamil's khutbaat circulate mainly as audio/video "
        "on his own channels, not a standard archive.org/besturdubooks text series. Best starting points: "
        "https://archive.org/details/AllahKoApnaBanaloByMaulanaTariqJameel (one compiled work, not the 8-vol series) "
        "| check besturdubooks.net's own search directly for 'طارق جمیل'."
    ),
    "117": (
        "https://archive.org/details/Maktaba-Allama-Anwar-Shah-Kashmiri-ra "
        "(full library collection - browse inside for 'خطبات محدث کبیر' specifically) "
        "| https://archive.org/details/mphilislamiate_gmail_20151127_1809 (ملفوظات, a related but distinct work)"
    ),
    "118": (
        "https://besturdubooks.net/tag/maulana-muhammad-ilyas-ghuman-books/ (author's full book list) "
        "| https://islamicgyan.shakirgyan.com/book-details/%D8%AE%D8%B7%D8%A8%D8%A7%D8%AA-%D9%85%D8%AA%DA%A9%D9%84%D9%85-%D8%A7%D8%B3%D9%84%D8%A7%D9%85-%D9%A1-6484 "
        "(vol 1 direct) | Scribd has vol 1 & 2 (may require an account): "
        "https://www.scribd.com/document/205420153/ and https://www.scribd.com/document/205420152/"
    ),
    "119": (
        "LIKELY MATCH under a variant title 'مواعظ اختر' (Mawaiz-e-Akhtar), not 'مواعظ حسنہ' exactly - verify before downloading: "
        "https://archive.org/details/MAkhar"
    ),
    "120": (
        "NOT CONFIDENTLY LOCATED - no direct match found for 'خطبات ازہر' by Maulana Muhammad Azhar; "
        "search results only surfaced an unrelated scholar with a similar name (Azhar Shah Qaisar). "
        "Recommend searching besturdubooks.net's khutbaat category directly: "
        "https://besturdubooks.net/category/khutbaat-o-maqalaat/"
    ),
    "121": (
        "https://archive.org/details/20251014_20251014_0913 (خطبات جمعہ وعیدین کو آداب و احکام) "
        "| https://archive.org/details/109-mawaiz-malfoozat-mufti-m.-shafee-sahib-rehmahullah"
    ),
    "122": (
        "https://besturdubooks.net/khutbat-e-azad/ "
        "| https://www.rekhta.org/ebooks/detail/khutbaat-e-aazad-abul-kalam-azad-ebooks"
    ),
    "123": (
        "https://www.rekhta.org/ebooks/detail/khutbat-e-iqbal-ebooks "
        "| https://archive.org/details/Maktaba_allama_iqbal (browse inside for the specific edition)"
    ),
    # --- Already in library, INCOMPLETE (missing some volumes) (15) ---
    "7": (
        "NOT CONFIDENTLY LOCATED as a clean multi-volume download - references found but no direct link: "
        "https://kitabbhubon.com/tag/%D9%85%D9%81%D8%AA%DB%8C-%D8%B1%D9%81%DB%8C%D8%B9-%D8%B9%D8%AB%D9%85%D8%A7%D9%86%DB%8C/ "
        "(has some volumes 2-9) | https://www.rekhta.org/editors/mufti-mohammad-rafi-usmani/ebooks (author list)"
    ),
    "8": (
        "STRONG MATCH - full 23-volume set (covers missing 19 & 20): "
        "https://archive.org/details/islahi-khutbat-by-mufti-taqi-usmani_202104 "
        "| https://besturdubooks.net/islahi-khutbaat/"
    ),
    "27": (
        "https://archive.org/details/abdazizsalman_pdf_1 (full author library collection, Arabic, browse for the missing volume)"
    ),
    "28": (
        "NOT CONFIDENTLY LOCATED under this exact title/author - besturdubooks.net's khutbaat category "
        "did not surface a direct match: https://besturdubooks.net/category/khutbaat-o-maqalaat/ "
        "(CAUTION: an unrelated same-surname work 'خطبات علامہ احتشام الحق تھانوی' also turned up - do not confuse the two)"
    ),
    "29": (
        "STRONG MATCH - 8-volume set, covers missing 1-6: https://besturdubooks.net/khutbat-ur-rasheed/"
    ),
    "33": (
        "Not confidently isolated to this exact title - candidate collection to browse: "
        "https://archive.org/details/Maktaba_hakeem_ul_ummat (full Ashraf Ali Thanvi library) "
        "| https://besturdubooks.net/khutbat-ul-ahkam/ (a related but distinctly-titled work, verify before use)"
    ),
    "50": (
        "STRONG MATCH: https://besturdubooks.net/khutbat-e-hakeem-ul-islam/ "
        "| https://archive.org/details/Maktaba-Hakeem-ul-Islam-Maulana-Qari-Tayyib-ra"
    ),
    "51": (
        "STRONG MATCH - full collection, covers missing 1-10: "
        "https://besturdubooks.net/khutbaat-e-hakeem-ul-ummat/ "
        "| https://archive.org/details/Maktaba_hakeem_ul_ummat"
    ),
    "73": (
        "https://besturdubooks.net/category/khutbaat-o-maqalaat/ (khutbaat category, browse for the exact title) "
        "| https://deobandi-books.aislam.org/book.php?b=125&p=21 (has vol 8 specifically, viewer not direct PDF)"
    ),
    "74": (
        "STRONG MATCH - all 45 volumes in one file, covers all 44 missing: "
        "https://archive.org/details/KHUTBAATEFAQEERAllInOne"
    ),
    "75": (
        "https://www.mziaulqasmi.com/books (author's own official site, lists خطبات قاسمیؒ directly)"
    ),
    "76": (
        "CAUTION - volume-count mismatch: one source describes this work as only 5 volumes total, "
        "not 10 as this row's 'True Total' says - verify before treating any volume as 'missing'. "
        "https://archive.org/details/Maktaba-Mufti-Mahmood-Bardoli-Sahib (author's full archive.org collection)"
    ),
    "84": (
        "STRONG MATCH: https://archive.org/details/4486Bok"
    ),
    "107": (
        "Same collection as row 119 (Mawaiz-e-Akhtar) - the missing volume may be inside it: "
        "https://archive.org/details/MAkhar"
    ),
    "108": (
        "CAUTION - this row's author is listed as Unknown; besturdubooks.net's 'Mawaiz-e-Usmani' below is "
        "attributed to Mufti Muhammad TAQI Usmani specifically - verify it's the same work before downloading: "
        "https://besturdubooks.net/mawaiz-e-usmani/"
    ),
}

with open(PATH, encoding="utf-8-sig", newline="") as f:
    rows = list(csv.reader(f))

header = "Researched Direct Links (2026-08-10, unverified by download - review before use)"
if rows[0][-1] != header:
    rows[0].append(header)
    for row in rows[1:]:
        row.append(LINKS.get(row[0], ""))
else:
    for row in rows[1:]:
        row[-1] = LINKS.get(row[0], "")

with open(PATH, "w", encoding="utf-8-sig", newline="") as f:
    csv.writer(f).writerows(rows)

print("Done. Rows written:", len(rows))
print("Linked rows:", sum(1 for r in rows[1:] if r[-1]))
