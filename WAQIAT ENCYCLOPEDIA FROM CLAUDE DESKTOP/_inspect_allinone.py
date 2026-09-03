import urllib.request, json, sys
sys.stdout.reconfigure(encoding='utf-8')

url = "https://archive.org/metadata/KHUTBAATEFAQEERAllInOne/files"
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
try:
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode('utf-8'))
        files = data.get('result', [])
        print(f"Total files in 'KHUTBAATEFAQEERAllInOne': {len(files)}")
        for f in files:
            name = f.get('name', '')
            size_mb = int(f.get('size', 0)) / (1024 * 1024)
            if name.endswith('.pdf') or name.endswith('.txt') or name.endswith('.epub'):
                print(f"  📄 {name:50s} ({size_mb:6.2f} MB)")
except Exception as e:
    print(f"Error: {e}")
