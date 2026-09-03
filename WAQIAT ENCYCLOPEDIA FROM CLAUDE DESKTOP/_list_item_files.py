import urllib.request, json, sys
sys.stdout.reconfigure(encoding='utf-8')

url = "https://archive.org/metadata/khutbaat-e-faqeer_202602/files"
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
resp = urllib.request.urlopen(req)
data = json.loads(resp.read().decode('utf-8'))
files = [f.get('name') for f in data.get('result', []) if f.get('name', '').endswith('.txt')]

print("First 15 text filenames in this item:")
for f in files[:15]:
    print(f"  {f}")
