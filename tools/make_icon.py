"""물고기 아이콘을 코드로 그려 build/icon.ico 로 저장한다 (build.bat에서 호출).

Pillow 없이 ICO 포맷을 직접 쓴다: 각 크기를 PNG로 인코딩해 담는 방식 (Vista 이후 표준).
사용: python tools/make_icon.py [출력경로]
"""
import io
import os
import struct
import sys

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame  # noqa: E402

from src.render.icon import icon_surface  # noqa: E402

SIZES = (16, 24, 32, 48, 64, 128, 256)


def png_bytes(surf: pygame.Surface) -> bytes:
    buf = io.BytesIO()
    pygame.image.save(surf, buf, "icon.png")
    return buf.getvalue()


def write_ico(path: str) -> None:
    images = [(size, png_bytes(icon_surface(size))) for size in SIZES]
    header = struct.pack("<HHH", 0, 1, len(images))
    offset = 6 + 16 * len(images)
    entries, blobs = b"", b""
    for size, data in images:
        dim = 0 if size >= 256 else size  # 256은 0으로 표기
        entries += struct.pack("<BBBBHHII", dim, dim, 0, 0, 1, 32, len(data), offset)
        blobs += data
        offset += len(data)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "wb") as f:
        f.write(header + entries + blobs)


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join("build", "icon.ico")
    write_ico(out)
    pygame.image.save(icon_surface(256), os.path.splitext(out)[0] + "_preview.png")
    print(f"아이콘 생성: {out}")
