import urllib.request, json, sys
sys.stdout.reconfigure(encoding='utf-8')

print("Searching Internet Archive API for Khutbat-e-Faqeer items...")
url = "https://archive.org/advancedsearch.php?q=title%3A%28Khutbat+Faqeer%29+OR+title%3A%28%D8%AE%D8%B7%D8%A8%D8%A7%D8%AA+%D9%81%D9%82%DB%8C%D8%B1%29&fl[]=identifier,title,mediatype&rows=50&output=json"

try:
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode('utf-8'))
        docs = data.get('response', {}).get('docs', [])
        print(f"Total archive items found: {len(docs)}")
        for d in docs:
            print(f"  Identifier: {d.get('identifier'):35s} | Title: {d.get('title')}")
except Exception as e:
    print(f"Error querying archive API: {e}")
