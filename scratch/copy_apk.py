import shutil
from pathlib import Path

src_apk = Path(r"F:\ISLAMIC RESEARCH HUB AI\mobile\app\build\outputs\apk\debug\app-debug.apk")
dest_dir = Path(r"F:\ISLAMIC RESEARCH HUB AI\installation\AndroidApp")
dest_dir.mkdir(parents=True, exist_ok=True)
dest_apk = dest_dir / "IslamicResearchHub_Companion.apk"

if src_apk.is_file():
    shutil.copy2(src_apk, dest_apk)
    print(f"APK file successfully copied to: {dest_apk.resolve()}")
    print(f"File size: {dest_apk.stat().st_size / (1024*1024):.2f} MB")
else:
    print("Source APK file not found.")
