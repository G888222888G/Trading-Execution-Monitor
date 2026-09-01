from __future__ import annotations

from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
FRAME_DIR = ROOT / "output" / "playwright" / "demo-frames"
OUTPUT = ROOT / "docs" / "images" / "execution-monitor-demo.gif"


def main() -> int:
    paths = sorted(FRAME_DIR.glob("*.png"))
    if len(paths) != 4:
        raise SystemExit("Expected four Playwright demo frames.")
    frames = [Image.open(path).convert("P", palette=Image.Palette.ADAPTIVE) for path in paths]
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(
        OUTPUT,
        save_all=True,
        append_images=frames[1:],
        duration=[1400, 1400, 1800, 2600],
        loop=0,
        optimize=True,
    )
    print(OUTPUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
