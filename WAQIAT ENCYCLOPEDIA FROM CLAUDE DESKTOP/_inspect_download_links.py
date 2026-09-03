import pandas as pd
import sys
sys.stdout.reconfigure(encoding='utf-8')

df = pd.read_excel(r"F:\ISLAMIC RESEARCH HUB AI\Urdu_Khutbat_Bayanat_Catalog.xlsx")

print("=" * 85)
print(" KHUTBAT SERIES WITH DOWNLOAD LINKS IN CATALOG")
print("=" * 85)

with_links = []
for idx, r in df.iterrows():
    title = str(r.get('Khutbat & Bayanat Series Title', '')).strip()
    author = str(r.get('Author / Scholar', '')).strip()
    links = str(r.get('Download Sources / Reference Links', '')).strip()
    vols = r.get('Volumes Present Count', '')
    if links and links.lower() != 'nan' and len(links) > 5:
        with_links.append((title, author, vols, links))

print(f"Total Series with Download Links in Excel: {len(with_links)}\n")
for t, a, v, l in with_links[:25]:
    print(f"📖 {t} ({a}):")
    print(f"   Link: {l}\n")
