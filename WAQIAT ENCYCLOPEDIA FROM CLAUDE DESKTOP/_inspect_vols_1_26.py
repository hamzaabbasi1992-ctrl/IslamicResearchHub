import urllib.request, json, sys
sys.stdout.reconfigure(encoding='utf-8')

url = "https://archive.org/metadata/KhutbaatEFaqeer-Volume1To26-ByShaykhZulfiqarAhmadNaqshbandi/files"
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
try:
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode('utf-8'))
        files = data.get('result', [])
        print(f"Total files in 'KhutbaatEFaqeer-Volume1To26': {len(files)}")
        for f in sorted(files, key=lambda x: x.get('name', '')):
            name = f.get('name', '')
            size_mb = int(f.get('size', 0)) / (1024 * 1024)
            if name.endswith('.pdf') or name.endswith('.txt') or name.endswith('.epub'):
                print(f"  📄 {name:55s} ({size_mb:5.2f} MB)")
except Exception as e:
    print(f"Error: {e}")
