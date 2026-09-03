import os, sys
sys.stdout.reconfigure(encoding='utf-8')

aitikaf_dir = r"E:\KHANQAH\AITIKAAF BAYANAT"
sunday_dir = r"E:\KHANQAH\SUNDAY BAYANS (FINAL)"

print("=" * 85)
print(" INSPECTING E:\\KHANQAH\\AITIKAAF BAYANAT")
print("=" * 85)
for root, dirs, files in os.walk(aitikaf_dir):
    rel = os.path.relpath(root, aitikaf_dir)
    print(f"\n📁 [{rel}] ({len(files)} files)")
    for f in files[:10]:
        print(f"   - {f}")
    if len(files) > 10:
        print(f"   ... and {len(files)-10} more files")

print("\n" + "=" * 85)
print(" INSPECTING E:\\KHANQAH\\SUNDAY BAYANS (FINAL)")
print("=" * 85)
for root, dirs, files in os.walk(sunday_dir):
    rel = os.path.relpath(root, sunday_dir)
    print(f"\n📁 [{rel}] ({len(files)} files)")
    for f in files[:10]:
        print(f"   - {f}")
    if len(files) > 10:
        print(f"   ... and {len(files)-10} more files")
