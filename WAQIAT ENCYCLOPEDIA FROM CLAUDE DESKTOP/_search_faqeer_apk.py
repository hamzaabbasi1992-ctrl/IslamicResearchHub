import urllib.request, json, sys, os, zipfile
sys.stdout.reconfigure(encoding='utf-8')

# Check if we can download APK from direct public APK download mirrors
package_id = "com.maktabatulishaat.KhutbaateFaqeer"
print(f"Target Package: {package_id}")

# Search Archive.org for 'com.maktabatulishaat.KhutbaateFaqeer' or 'KhutbaateFaqeer.apk'
url = f"https://archive.org/advancedsearch.php?q=Khutbaat+e+Faqeer+apk&fl[]=identifier,title,downloads&rows=10&output=json"
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})

try:
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode('utf-8'))
        docs = data.get('response', {}).get('docs', [])
        print(f"Archive.org APK search results: {len(docs)}")
        for d in docs:
            print(f"  📦 {d.get('identifier')} | {d.get('title')}")
except Exception as e:
    print(f"Error: {e}")
