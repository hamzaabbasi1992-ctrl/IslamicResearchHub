import os, sys
sys.stdout.reconfigure(encoding='utf-8')

print("=" * 85)
print(" SEARCHING FOR KHANQAH DRIVE, AITIKAF BAYANAT, AND SUNDAY BAYANAT")
print("=" * 85)

potential_roots = [
    r"F:\کتب",
    r"F:\ISLAMIC RESEARCH HUB AI",
    r"F:\AI TOOLS N APPS MADE",
    r"F:",
    r"D:",
    r"E:"
]

found_dirs = []
found_files = []

keywords = ["khanqah", "خانقاہ", "اعتکاف", "aitikaf", "اتوار", "sunday", "bayanat", "بیانات", "مواعظ"]

for root_drive in ["F:\\", "D:\\", "E:\\"]:
    if not os.path.exists(root_drive): continue
    print(f"Scanning drive {root_drive} ...")
    try:
        top_items = os.listdir(root_drive)
        for item in top_items:
            full_item_path = os.path.join(root_drive, item)
            print(f"  Root Item: {item}")
            if any(k in item.lower() for k in ["khanqah", "خانقاہ", "اعتکاف", "aitikaf", "اتوار", "sunday", "bayanat", "بیانات", "کتب"]):
                found_dirs.append(full_item_path)
    except Exception as e:
        print(f"  Error reading {root_drive}: {e}")

print("\n" + "=" * 85)
print(" FOUND TARGET FOLDERS:")
for d in found_dirs:
    print(f"  --> {d}")
print("=" * 85)
