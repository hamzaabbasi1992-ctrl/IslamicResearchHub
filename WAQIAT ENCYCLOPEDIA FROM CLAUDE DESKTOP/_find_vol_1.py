import os, sys
sys.stdout.reconfigure(encoding='utf-8')

for root_dir in [r"F:\کتب", r"F:\ISLAMIC RESEARCH HUB AI", r"F:\MAKNOON"]:
    if os.path.exists(root_dir):
        for r, d, fs in os.walk(root_dir):
            for f in fs:
                fl = f.lower()
                if ("اصلاحی تقریر" in f or "islahi taqreer" in fl or "taqreeren" in fl or "taqreerain" in fl) and f.endswith(('.pdf', '.docx', '.txt')):
                    print(f"Found: {os.path.join(r, f)}")
