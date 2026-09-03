import urllib.request, json, sys
sys.stdout.reconfigure(encoding='utf-8')

for num in range(662, 675):
    ident = f"quasmi-quasmikitabghar-{num}"
    url = f"https://archive.org/metadata/{ident}"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            meta = data.get('metadata', {})
            title = meta.get('title')
            print(f"Identifier {ident}: {title}")
    except Exception as e:
        print(f"Identifier {ident}: Not Found ({e})")
