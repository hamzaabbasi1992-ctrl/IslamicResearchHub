import urllib.request, sys
sys.stdout.reconfigure(encoding='utf-8')

item_id = "khutbaat-e-faqeer_202602"
filename = "KHUTBAAT-E-FAQEER-VOL-1_djvu.txt"
url = f"https://archive.org/download/{item_id}/{urllib.parse.quote(filename)}"

print(f"Downloading: {url}")
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})

try:
    with urllib.request.urlopen(req, timeout=30) as resp:
        content = resp.read().decode('utf-8', errors='ignore')
        print(f"✅ Successfully Downloaded: {len(content)} characters ({len(content)/1024:.2f} KB)")
        print("\n--- SAMPLE TEXT PREVIEW (First 1,000 chars) ---")
        print(content[:1000])
except Exception as e:
    print(f"❌ Error downloading: {e}")
