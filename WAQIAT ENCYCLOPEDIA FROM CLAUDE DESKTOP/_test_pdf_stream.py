import urllib.request, fitz, sys
sys.stdout.reconfigure(encoding='utf-8')

# Download first 500 KB of a PDF from Archive.org or a complete small volume
item_id = "khutbaat-e-faqeer_202602"
pdf_filename = "KHUTBAAT-E-FAQEER-VOL-33.pdf"
url = f"https://archive.org/download/{item_id}/{urllib.parse.quote(pdf_filename)}"

print(f"Downloading PDF: {url}")
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})

try:
    with urllib.request.urlopen(req, timeout=30) as resp:
        pdf_bytes = resp.read()
        print(f"Downloaded PDF: {len(pdf_bytes)/(1024*1024):.2f} MB")

        # Open with PyMuPDF
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        print(f"Total Pages in PDF: {len(doc)}")

        # Check page 10 text
        text_p10 = doc[10].get_text()
        print("\n--- PAGE 10 TEXT STREAM CHECK ---")
        if text_p10.strip():
            print(f"Found {len(text_p10)} chars of native text:")
            print(text_p10[:400])
        else:
            print("❌ Page 10 has NO digital text stream (Scanned Image PDF).")
except Exception as e:
    print(f"Error: {e}")
