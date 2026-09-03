import urllib.request, json, sys
sys.stdout.reconfigure(encoding='utf-8')

url = "https://archive.org/advancedsearch.php?q=collection:(ShaykhZulfiqarAhmadNaqshbandiBooks)+AND+Khutbaat&fl[]=identifier,title,downloads&rows=50&output=json"
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
try:
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode('utf-8'))
        docs = data.get('response', {}).get('docs', [])
        print(f"Total matching items: {len(docs)}")
        for d in docs:
            print(f"  📦 {d.get('identifier'):40s} | {d.get('title')}")
except Exception as e:
    print(f"Error: {e}")
