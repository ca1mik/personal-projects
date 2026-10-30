from pathlib import Path
from datetime import datetime
from mss import mss
from PIL import Image

def make_screenshot(out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = out_dir / f"screenshot_{ts}.png"

    with mss() as sct:
        mon = sct.monitors[1]  # основной монитор
        raw = sct.grab(mon)
        img = Image.frombytes("RGB", raw.size, raw.rgb)
        img.save(path)
    return path
