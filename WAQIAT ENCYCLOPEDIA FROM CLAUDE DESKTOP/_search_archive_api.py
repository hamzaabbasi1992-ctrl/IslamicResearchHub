import urllib.request, json, sys
sys.stdout.reconfigure(encoding='utf-8')

# Query Archive.org Search API for Urdu Khutbat items
def search_archive(query):
    url = f"https://archive.org/advancedsearch.php?q={urllib.parse.quote(query)}&fl[]=identifier,title,mediatype,downloads&rows=10&output=json"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            docs = data.get('response', {}).get('docs', [])
            return docs
    except Exception as e:
        print(f"Error querying Archive.org for '{query}': {e}")
        return []

print("=" * 80)
print(" ARCHIVE.ORG SEARCH FOR MISSING URDU KHUTBAT TEXT FILES")
print("=" * 80)

queries = [
    "Khutbat e Faqeer",
    "Khutbat e Tayyab",
    "Khutbat e Madani",
    "Khutbat e Usmani",
    "Mawaiz e Hasana",
    "Islahi Mawaiz"
]

for q in queries:
    print(f"\n🔍 Search Query: '{q}'")
    results = search_archive(q)
    if not results:
        print("  No items found.")
    for r in results[:4]:
        item_id = r.get('identifier')
        title = r.get('title', 'Unknown')
        print(f"  📦 Item ID: {item_id:40s} | Title: {title[:50]}")
