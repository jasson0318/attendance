"""產生簡易 PWA 圖示。"""
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    Image = None


def make_png(path: Path, size: int):
    if Image is None:
        # 最小合法 1x1 PNG 再不行就寫 raw placeholder
        # 使用純色 PPM 轉不行，改寫最小 PNG bytes
        import struct
        import zlib

        def chunk(tag, data):
            return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

        # solid teal pixel expanded via IHDR
        raw = b"".join(b"\x00" + bytes([15, 76, 92]) * size for _ in range(size))
        png = b"\x89PNG\r\n\x1a\n"
        png += chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0))
        png += chunk(b"IDAT", zlib.compress(raw, 9))
        png += chunk(b"IEND", b"")
        path.write_bytes(png)
        return

    img = Image.new("RGB", (size, size), (15, 76, 92))
    draw = ImageDraw.Draw(img)
    margin = size // 8
    draw.rounded_rectangle(
        [margin, margin, size - margin, size - margin],
        radius=size // 10,
        fill=(232, 241, 242),
    )
    draw.ellipse([size * 0.3, size * 0.28, size * 0.7, size * 0.68], fill=(227, 100, 20))
    img.save(path)


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1] / "frontend" / "static" / "icons"
    root.mkdir(parents=True, exist_ok=True)
    make_png(root / "icon-192.png", 192)
    make_png(root / "icon-512.png", 512)
    print("icons ok")
