import urllib.request, zipfile, sys, os
from bs4 import BeautifulSoup
sys.stdout.reconfigure(encoding='utf-8')

item_id = "KhutbaatEFaqeer-Volume1To26-ByShaykhZulfiqarAhmadNaqshbandi"
epub_file = "KhutbaatEFaqeer-Volume1-ByShaykhZulfiqarAhmadNaqshbandi.epub"
url = f"https://archive.org/download/{item_id}/{urllib.parse.quote(epub_file)}"

print(f"Downloading EPUB: {url}")
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})

try:
    with urllib.request.urlopen(req, timeout=30) as resp:
        epub_bytes = resp.read()
        print(f"Downloaded EPUB: {len(epub_bytes)/1024:.2f} KB")

        save_path = r"F:\ISLAMIC RESEARCH HUB AI\WAQIAT ENCYCLOPEDIA FROM CLAUDE DESKTOP\temp_v1.epub"
        with open(save_path, "wb") as f:
            f.write(epub_bytes)

        # Unzip and inspect html/xhtml files
        with zipfile.ZipFile(save_path, 'r') as z:
            html_files = [f for f in z.namelist() if f.endswith('.xhtml') or f.endswith('.html') or f.endswith('.htm')]
            print(f"Total HTML files in EPUB: {len(html_files)}")
            for h in html_files[:5]:
                content = z.read(h).decode('utf-8', errors='ignore')
                soup = BeautifulSoup(content, 'html.parser')
                clean_text = soup.get_text()
                print(f"\n--- FILE: {h} ({len(clean_text)} chars) ---")
                print(clean_text[:400].strip())

except Exception as e:
    print(f"Error: {e}")
