import os, sys, pymupdf
sys.stdout.reconfigure(encoding='utf-8')

BASE = r"F:\کتب\خطبات و مواعظ ۔"

folders_to_check = [
    "اصلاحی تقریریں ۔",
    "اصلاحی مواعظ م تقی عٹمانی",
    "اصلاحی مواعظ م یوسف لدھیانوی",
    "خطبات عثمانی",
    "خطبات نديم",
    "خطبات ممبر و محراب",
    "ندائے منبر و محراب ۔",
    "خطباتِ سلف ۔",
    "جواھرات حکیم الامت"
]

print("=" * 85)
print(" INSPECTING KHUTBAT & MAWAIZ FOLDERS")
print("=" * 85)

for fld in folders_to_check:
    fpath = os.path.join(BASE, fld)
    if os.path.exists(fpath):
        files = [f for f in os.listdir(fpath) if f.lower().endswith(('.pdf', '.docx', '.txt'))]
        print(f"\n📁 فولڈر: {fld} ({len(files)} فائلز):")
        for f in files[:8]:
            full = os.path.join(fpath, f)
            sz = os.path.getsize(full) / (1024 * 1024)
            pcount = ""
            if f.lower().endswith('.pdf'):
                try:
                    d = pymupdf.open(full)
                    pcount = f" | {len(d)} صفحات"
                    d.close()
                except:
                    pass
            print(f"   📄 {f} ({sz:.2f} MB{pcount})")

print("\n" + "=" * 85)
print(" STANDALONE PDFS IN F:\\کتب\\خطبات و مواعظ ۔\\")
print("=" * 85)
standalone = [
    "نزھۃ المجالس 2 جلدیں امام عبد الرحمن.pdf",
    "خطبات متکلم اسلام 3 جلدیں گھمن.pdf",
    "علمی خطبات 2 جلدیں مکمل.pdf",
    "MALFOOZAT_E_MAULANA_AHMAD_ALI_LAHORI.pdf",
    "ارشاداتِ گنگوھی .pdf"
]
for s in standalone:
    sp = os.path.join(BASE, s)
    if os.path.exists(sp):
        sz = os.path.getsize(sp) / (1024 * 1024)
        try:
            d = pymupdf.open(sp)
            print(f"📄 {s} ({sz:.2f} MB | {len(d)} صفحات)")
            d.close()
        except Exception as e:
            print(f"📄 {s} ({sz:.2f} MB)")
