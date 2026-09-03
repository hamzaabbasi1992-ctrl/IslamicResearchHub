import urllib.request, json, sys
sys.stdout.reconfigure(encoding='utf-8')

url = "https://archive.org/metadata/khutbaat-e-faqeer_202602/files"
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
try:
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode('utf-8'))
        files = data.get('result', [])
        pdf_files = [f for f in files if f.get('name', '').endswith('.pdf') and not f.get('name', '').endswith('_text.pdf')]
        print(f"Total PDF volumes in 'khutbaat-e-faqeer_202602': {len(pdf_files)}")
        for f in pdf_files[:20]:
            print(f"  📄 {f.get('name'):35s} ({int(f.get('size',0))/(1024*1024):5.2f} MB)")
except Exception as e:
    print(f"Error: {e}")
