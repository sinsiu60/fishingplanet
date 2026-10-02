"""모바일용 한글 폰트 만들기 (DESIGN.md 26-10).

안드로이드엔 맑은 고딕이 없고 재배포도 안 돼서, Noto Sans KR(OFL 1.1)을 게임에 쓰는 글자만 남겨 data/fonts/ 에 넣는다.
남기는 글자: 저장소의 src/·data/ 에 나오는 모든 글자 + 자주 쓰는 한글 2,350자(KS X 1001) + 영문·숫자·기호.

사용: python tools/make_mobile_font.py <NotoSansKR-Regular.ttf>
  원본: Google Fonts "Noto Sans KR" Regular (fonts.google.com/noto/specimen/Noto+Sans+KR)
  글자를 새로 쓴 문구를 추가했다면 다시 실행한다 (안 하면 그 글자만 □로 보임 — PC는 맑은 고딕이라 상관없음).
필요: pip install fonttools
"""
import os
import sys
from pathlib import Path

from fontTools import subset

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "fonts" / "NotoSansKR-Subset.ttf"


def used_chars() -> set[str]:
    chars = set(chr(c) for c in range(0x20, 0x7F))
    for b1 in range(0xB0, 0xC9):           # KS X 1001 한글 2,350자
        for b2 in range(0xA1, 0xFF):
            try:
                chars.add(bytes([b1, b2]).decode("euc-kr"))
            except UnicodeDecodeError:
                pass
    for folder in ("src", "data"):
        for path in (ROOT / folder).rglob("*"):
            if path.suffix in (".py", ".json", ".txt") and path.is_file():
                chars |= set(path.read_text(encoding="utf-8", errors="ignore"))
    return {c for c in chars if c.isprintable()}


def main() -> None:
    src = sys.argv[1]
    text = "".join(sorted(used_chars()))
    opts = subset.Options()
    opts.layout_features = ["*"]
    opts.name_IDs = ["*"]
    opts.notdef_outline = True
    font = subset.load_font(src, opts)
    sub = subset.Subsetter(opts)
    sub.populate(text=text)
    sub.subset(font)
    os.makedirs(OUT.parent, exist_ok=True)
    subset.save_font(font, str(OUT), opts)
    print(f"{OUT.name}: {len(text)}자, {OUT.stat().st_size / 1024:.0f}KB")


if __name__ == "__main__":
    main()
