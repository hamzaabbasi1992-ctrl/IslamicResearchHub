import pandas as pd
import sqlite3, sys
sys.stdout.reconfigure(encoding='utf-8')

df = pd.read_excel(r"F:\ISLAMIC RESEARCH HUB AI\Urdu_Khutbat_Bayanat_Catalog.xlsx")
print("Catalog Columns:", df.columns.tolist())
print(f"Total Rows in Catalog: {len(df)}")
print("\nFirst 15 series:")
for idx, r in df.head(15).iterrows():
    print(f"  {r.iloc[0]} | {r.iloc[1]} | Vols: {r.iloc[2]}")
