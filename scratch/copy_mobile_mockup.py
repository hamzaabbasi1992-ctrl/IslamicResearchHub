import shutil
from pathlib import Path

src_img = Path(r"C:\Users\DELL\.gemini\antigravity-ide\brain\aa2e4da3-a3aa-4823-9201-194b4f51d87f\mobile_app_screens_mockup_1786285076675.png")
dest_dir = Path("screenshots of app for other ai/mobile")
dest_dir.mkdir(parents=True, exist_ok=True)
dest_img = dest_dir / "mobile_app_screens_mockup.png"

if src_img.is_file():
    shutil.copy2(src_img, dest_img)
    print(f"Mobile mockup image copied to: {dest_img.resolve()}")
else:
    print("Source image not found.")
