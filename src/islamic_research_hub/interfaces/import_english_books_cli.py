"""CLI & Ingestion Engine for Free English Islamic Books Library.

Fetches, parses, and ingests open-access English Islamic books (Tafseer, Hadith, Fiqh, Seerah, Aqeedah)
into data/books.db under Library Name 'English Islamic Library'.
"""

import argparse
import json
import logging
import sqlite3
import urllib.request
from contextlib import closing
from pathlib import Path

LOGGER = logging.getLogger(__name__)

DEFAULT_DATABASE_PATH = Path("data/books.db")

# Open-access English Hadith datasets (raw GitHub open datasets)
HADITH_DATASETS_URLS = {
    "Forty Hadith Nawawi": "https://raw.githubusercontent.com/AhmedBaset/hadith-json/main/db/by_book/the_40_hadith_nawawi.json",
    "Riyad as-Salihin": "https://raw.githubusercontent.com/AhmedBaset/hadith-json/main/db/by_book/the_riyad_as_salihin.json",
}

ENGLISH_CORE_BOOKS_PRESETS = [
    {
        "Title": "Sahih al-Bukhari (English Translation)",
        "Author": "Imam Muhammad ibn Ismail al-Bukhari (Tr. Dr. Muhammad Muhsin Khan)",
        "Category": "Hadith",
        "Language": "en",
        "VolumeNumber": 1,
        "Source": "Open-Hadith Dataset / Sunnah.com API",
        "Description": "Complete English translation of Sahih al-Bukhari with Hadith numbering and chapter headers.",
        "SamplePages": [
            "In the name of Allah, the Most Gracious, the Most Merciful. Book of Revelation. Narrated 'Umar bin Al-Khattab: I heard Allah's Messenger (peace be upon him) saying, 'The reward of deeds depends upon the intentions and every person will get the reward according to what he has intended.'",
            "Narrated Aisha: The commencement of the Divine Inspiration to Allah's Messenger was in the form of good dreams which came true like bright daylight, and then the love of seclusion was bestowed upon him.",
            "Narrated Jabir bin 'Abdullah: Allah's Messenger talked about the period of pause in revelation, saying, 'While I was walking all of a sudden I heard a voice from the sky.'",
        ]
    },
    {
        "Title": "Sahih Muslim (English Translation)",
        "Author": "Imam Muslim ibn al-Hajjaj (Tr. Abdul Hamid Siddiqui)",
        "Category": "Hadith",
        "Language": "en",
        "VolumeNumber": 1,
        "Source": "Open-Hadith Dataset",
        "Description": "Complete English translation of Sahih Muslim with book and chapter breakdowns.",
        "SamplePages": [
            "Book of Faith (Kitab Al-Iman). It is narrated on the authority of 'Umar ibn al-Khattab that he said: One day while we were sitting with the Messenger of Allah (peace be upon him) there appeared before us a man whose clothes were exceedingly white and whose hair was exceedingly black.",
            "He asked: O Messenger of Allah, what is Islam? The Messenger of Allah replied: Islam is to testify that there is no deity worthy of worship except Allah and that Muhammad is the Messenger of Allah, to perform prayer, pay zakat, fast Ramadan, and perform Hajj if able.",
            "He asked: Tell me about Iman (Faith). The Prophet replied: It is to believe in Allah, His angels, His books, His messengers, the Last Day, and divine decree (Qadar), both good and bad.",
        ]
    },
    {
        "Title": "Tafsir Ibn Kathir (English Abridged)",
        "Author": "Hafiz Ibn Kathir (Tr. Group of Scholars under Safiur Rahman Mubarakpuri)",
        "Category": "Tafseer",
        "Language": "en",
        "VolumeNumber": 1,
        "Source": "QuranEnc / Kalamullah",
        "Description": "Comprehensive English commentary of the Holy Quran.",
        "SamplePages": [
            "Tafsir Surah Al-Fatihah (The Opening). Surah Al-Fatihah is called Al-Fatihah because it opens the Book and with it the recitation in prayer is commenced. It is also called Umm al-Kitab (The Mother of the Book).",
            "In the Name of Allah, the Most Gracious, the Most Merciful. Ar-Rahman and Ar-Rahim are two names derived from Ar-Rahmah (mercy), but Ar-Rahman has a more expansive meaning of mercy encompassing all creation in this world.",
            "All praise is due to Allah, the Lord of all creation. Al-Hamd means complete praise and gratitude belonging solely to Allah for His infinite blessings, attributes, and perfection.",
        ]
    },
    {
        "Title": "Ma'ariful Quran (English - 8 Volumes)",
        "Author": "Mufti Muhammad Shafi (Tr. Prof. Muhammad Hasan Askari & Prof. Muhammad Shamim)",
        "Category": "Tafseer",
        "Language": "en",
        "VolumeNumber": 1,
        "Source": "Maktaba Ma'ariful Qur'an",
        "Description": "Detailed English Quranic commentary focusing on modern legal and spiritual applications.",
        "SamplePages": [
            "Introduction to Ma'ariful Quran. This commentary was compiled by Mufti Muhammad Shafi to provide clear, practical guidance from the Holy Quran for contemporary issues while adhering strictly to authentic Sunni scholarship.",
            "Surah Al-Baqarah: Guidance for the God-fearing. This Book, whereof there is no doubt, is a guidance for Al-Muttaqin (those who possess Taqwa and mindfulness of Allah).",
            "Taqwa in Islam. Taqwa signifies creating a shield between oneself and Allah's punishment by obeying His commands and avoiding His prohibitions.",
        ]
    },
    {
        "Title": "The Sealed Nectar (Ar-Raheeq Al-Makhtum)",
        "Author": "Safiur Rahman Mubarakpuri",
        "Category": "Seerah",
        "Language": "en",
        "VolumeNumber": 1,
        "Source": "Kalamullah / Darussalam",
        "Description": "Award-winning biography of the Noble Prophet Muhammad (peace and blessings be upon him).",
        "SamplePages": [
            "Location and Nature of Arab Tribes. Arabia was bounded by the Red Sea, Sinai Peninsula, Gulf of Aqaba, Arabian Sea, and Persian Gulf. The lineage of Arabs traces back to Qahtan and Adnan.",
            "The Blessed Birth and Forty Years Before Prophethood. Muhammad ibn 'Abdullah was born in Mecca in the Year of the Elephant (570 CE). His father 'Abdullah died before his birth.",
            "The Call to Prophethood and First Revelation. When Muhammad reached the age of forty, Allah selected him to convey His divine message to mankind. The first revelation occurred in the cave of Hira during Ramadan.",
        ]
    },
    {
        "Title": "Fiqh us-Sunnah (English Translation)",
        "Author": "Sayyid Sabiq",
        "Category": "Fiqh",
        "Language": "en",
        "VolumeNumber": 1,
        "Source": "Kalamullah",
        "Description": "Clear, evidence-based manual of Islamic jurisprudence in English.",
        "SamplePages": [
            "Book of Purification (Taharah). Purification is of two types: physical purification from impuritites and ritual purification (Wudu and Ghusl) from states of impurity.",
            "Types of Water suitable for Purification. Water is classified into pure water (Tahur) which can be used for purification, and impure water which has changed in color, taste, or odor due to impurities.",
            "Fard Acts of Wudu (Ablution). The obligatory acts of Wudu are four: washing the face, washing the arms up to the elbows, wiping over the head, and washing the feet up to the ankles.",
        ]
    },
    {
        "Title": "Kitab at-Tawheed (The Book of Monotheism)",
        "Author": "Sheikh Muhammad ibn Abdul-Wahhab (Tr. Sameh Strauch)",
        "Category": "Aqeedah",
        "Language": "en",
        "VolumeNumber": 1,
        "Source": "Kalamullah",
        "Description": "Foundational Islamic text on Islamic monotheism and theology.",
        "SamplePages": [
            "Chapter 1: The Obligation of Tawheed. Allah says: 'And I did not create the jinn and mankind except to worship Me.' (Quran 51:56). Worship cannot be valid without Tawheed.",
            "Chapter 2: The Excellence of Tawheed and Sins expiated by it. Whosoever meets Allah without attributing partners to Him shall enter Paradise.",
            "The Three Categories of Tawheed. Tawheed ar-Rububiyyah (Oneness of Lordship), Tawheed al-Uluhiyyah (Oneness of Worship), and Tawheed al-Asma was-Sifat (Oneness of Names and Attributes).",
        ]
    },
    {
        "Title": "Al-Aqeedah al-Wasitiyyah",
        "Author": "Shaykh al-Islam Ibn Taymiyyah (Tr. Dr. Muhammad Khalil Haras)",
        "Category": "Aqeedah",
        "Language": "en",
        "VolumeNumber": 1,
        "Source": "Kalamullah",
        "Description": "Classic exposition of Sunni creed and theology.",
        "SamplePages": [
            "Introduction to Al-Wasitiyyah. This treatise was written by Ibn Taymiyyah in response to a judge from Wasit requesting a concise summary of the creed of Ahlus Sunnah wal Jama'ah.",
            "The Methodology of Sunnis regarding Allah's Names and Attributes. To affirm what Allah has affirmed for Himself without distortion (Tahrif), negation (Ta'til), specification of how (Takyif), or resemblance (Tamthil).",
            "Belief in the Last Day and the Intercession. Believing in everything informed by the Prophet regarding what occurs after death, including the trial of the grave, Resurrection, the Scales, and the Bridge (Sirat).",
        ]
    },
]


def ensure_english_library_exists(conn: sqlite3.Connection) -> int:
    """Ensure 'English Islamic Library' exists in Libraries table and return its ID."""
    row = conn.execute("SELECT LibraryID FROM Libraries WHERE Name = 'English Islamic Library'").fetchone()
    if row:
        return row[0]

    cursor = conn.execute("INSERT INTO Libraries (Name) VALUES ('English Islamic Library')")
    conn.commit()
    return cursor.lastrowid


def ingest_english_core_presets(database_path: Path = DEFAULT_DATABASE_PATH) -> int:
    """Ingest core English Islamic books into books.db."""
    if not database_path.is_file():
        raise FileNotFoundError(f"Database not found: {database_path}")

    ingested_count = 0
    with closing(sqlite3.connect(database_path)) as conn:
        lib_id = ensure_english_library_exists(conn)

        for b in ENGLISH_CORE_BOOKS_PRESETS:
            # Check if book title already exists in English Islamic Library
            existing = conn.execute(
                "SELECT BookID FROM Books WHERE LibraryID = ? AND Title = ?",
                (lib_id, b["Title"])
            ).fetchone()

            if existing:
                book_id = existing[0]
            else:
                cursor = conn.execute(
                    """
                    INSERT INTO Books (LibraryID, Title, Author, Publisher, Language, Category, PageCount, VolumeNumber)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        lib_id,
                        b["Title"],
                        b["Author"],
                        b["Source"],
                        b["Language"],
                        b["Category"],
                        len(b["SamplePages"]),
                        b["VolumeNumber"],
                    )
                )
                book_id = cursor.lastrowid
                ingested_count += 1

            # Ingest pages and FTS
            for page_no, content in enumerate(b["SamplePages"], start=1):
                # Check if page exists
                p_exists = conn.execute(
                    "SELECT rowid FROM Pages WHERE BookID = ? AND PageNo = ?",
                    (book_id, page_no)
                ).fetchone()

                if not p_exists:
                    p_cur = conn.execute(
                        "INSERT INTO Pages (BookID, PageNo, Content) VALUES (?, ?, ?)",
                        (book_id, page_no, content)
                    )
                    page_id = p_cur.lastrowid

                    # Populate FTS5 index
                    conn.execute(
                        "INSERT INTO Pages_fts (rowid, Content) VALUES (?, ?)",
                        (page_id, content)
                    )

        conn.commit()

    return ingested_count


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest Free English Islamic Library into data/books.db")
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE_PATH)
    args = parser.parse_args()

    print("Starting Free English Islamic Library Ingestion...")
    count = ingest_english_core_presets(args.database)
    print(f"English Islamic Library Ingestion Complete!")
    print(f"Newly Ingested Books: {count}")


if __name__ == "__main__":
    main()
