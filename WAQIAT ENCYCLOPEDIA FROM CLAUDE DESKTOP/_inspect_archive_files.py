import urllib.request, json, sys
sys.stdout.reconfigure(encoding='utf-8')

def inspect_archive_files(item_id):
    url = f"https://archive.org/metadata/{item_id}/files"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            files = data.get('result', [])
            print(f"\n📦 Files for Item: '{item_id}' ({len(files)} files)")
            for f in files:
                name = f.get('name', '')
                fmt = f.get('format', '')
                size_mb = int(f.get('size', 0)) / (1024 * 1024)
                if fmt in ['Text', 'DjVuTXT', 'OCR Page Index', 'Abbyy GZ', 'Text PDF', 'Item Tile', 'Single Page Processed JP2 ZIP']:
                    print(f"   📄 {name:50s} | Format: {fmt:15s} | Size: {size_mb:6.2f} MB")
                elif name.endswith('.txt') or name.endswith('.pdf'):
                    print(f"   📄 {name:50s} | Format: {fmt:15s} | Size: {size_mb:6.2f} MB")
    except Exception as e:
        print(f"Error for '{item_id}': {e}")

print("=" * 80)
print(" INSPECTING ARCHIVE.ORG DOWNLOADABLE FILES FOR KHUTBAT")
print("=" * 80)

inspect_archive_files("khutbaat-e-faqeer_202602")
inspect_archive_files("Khutbat-e-Tayyabr.aByShaykhQariMuhammadTayyabr.a")
