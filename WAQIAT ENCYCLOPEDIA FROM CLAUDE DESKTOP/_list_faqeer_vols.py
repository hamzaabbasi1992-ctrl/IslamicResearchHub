import urllib.request, json, sys
sys.stdout.reconfigure(encoding='utf-8')

url = "https://archive.org/metadata/KHUTBAATEFAQEER/files"
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
try:
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode('utf-8'))
        files = data.get('result', [])
        pdf_files = [f for f in files if f.get('name', '').endswith('.pdf')]
        print(f"Total PDF files in 'KHUTBAATEFAQEER': {len(pdf_files)}")
        for f in sorted(pdf_files, key=lambda x: x.get('name')):
            name = f.get('name')
            size_mb = int(f.get('size', 0)) / (1024 * 1024)
            print(f"  📄 {name:35s} ({size_mb:5.2f} MB)")
except Exception as e:
    print(f"Error: {e}")
