"""할아버지(해강)의 흔적 (DETAILS.md H-3, DESIGN.md 45장 DT11). 위치 · 문장은 data/details/grandpa_marks.json.

샤르미온 낚시터 6곳 배경 속 작은 'ㅎ' 새김 (3x4px, 새김 = 바탕보다 조금 어두운 색). 전경(왼쪽 아래)과 함께 화면에 고정.
탭/클릭(던지기 전, 파이팅 아닐 때) → 일지에 한 줄 + 수첩 보관함 '이야기' 칸 "해강의 흔적 n/6" · 6개 = 칭호 "할아버지의 발자취".
비밀 장소의 '해강' 바위(STORY C3-02)와는 별개.
"""
import pygame

from src.core.config import load_json
from src.core.mathutil import lerp_color, scale_color

# 'ㅎ' 3x4: 짧은 위 획 · 긴 가로획 · 아래 동그라미(가운데 점)
GLYPH = ((1, 0), (0, 1), (1, 1), (2, 1), (0, 2), (2, 2), (1, 3))


def cfg() -> dict:
    return load_json("details/grandpa_marks.json")


def found(save) -> list:
    return save.data.setdefault("details", {}).setdefault("grandpa_marks", [])


def count(save) -> int:
    return len(found(save))


def total() -> int:
    return len(cfg()["marks"])


def mark_at(spot_id: str) -> dict | None:
    return cfg()["marks"].get(spot_id)


def draw(canvas, spot_id: str, pal) -> None:
    m = mark_at(spot_id)
    if m is None:
        return
    x, y = m["x"], m["y"]
    obj = m.get("obj", "none")
    wood = lerp_color(pal.get("rod", (120, 90, 60)), (110, 80, 52), 0.5)
    stone = lerp_color(pal.get("mountain_near", (90, 90, 96)), (100, 100, 104), 0.4)
    if obj == "post":      # 물가 나무 말뚝
        canvas.fill(scale_color(wood, 0.75), (x - 3, y - 8, 9, 40))
        canvas.fill(wood, (x - 3, y - 8, 8, 40))
        canvas.fill(lerp_color(wood, (230, 210, 170), 0.3), (x - 3, y - 9, 8, 2))
        base = wood
    elif obj == "anchor":  # 배 위 오래된 닻 (녹)
        rust = lerp_color(pal.get("rod", (120, 90, 60)), (120, 70, 40), 0.6)
        canvas.fill(rust, (x - 1, y - 9, 4, 18))                      # 자루
        pygame.draw.circle(canvas, rust, (x + 1, y - 11), 3, 1)      # 고리
        canvas.fill(rust, (x - 5, y - 6, 12, 2))                      # 가로대
        pygame.draw.arc(canvas, rust, (x - 8, y - 2, 18, 12), 3.3, 6.1, 2)   # 갈고리
        base = rust
        x, y = x - 0, y - 4
    elif obj == "rock":    # 폭포 옆 바위
        pts = [(x - 20, 270), (x - 16, y - 6), (x + 2, y - 14), (x + 18, y - 4), (x + 24, 270)]
        pygame.draw.polygon(canvas, stone, pts)
        pygame.draw.lines(canvas, lerp_color(stone, (80, 130, 80), 0.4), False, pts[1:-1], 2)
        base = stone
    else:                  # 이미 있는 전경(바위 · 테트라포드 · 뱃전) 위
        base = canvas.get_at((x + 1, y + 1))[:3] if 0 <= x + 1 < canvas.get_width() and 0 <= y + 1 < canvas.get_height() else stone
    ink = scale_color(base, 0.72)
    for dx, dy in GLYPH:
        canvas.fill(ink, (x + dx, y + dy, 1, 1))


def hit(spot_id: str, pos, touch: bool = False) -> bool:
    m = mark_at(spot_id)
    if m is None or pos is None:
        return False
    c = cfg()
    pad = c["hit_pad_touch"] if touch else c["hit_pad"]
    return pygame.Rect(m["x"] - pad, m["y"] - pad, 3 + pad * 2, 4 + pad * 2).collidepoint(pos)


def find(save, spot_id: str, day: int = 1, season: str = "spring") -> dict | None:
    """찾음: 일지 한 줄 · 개수 · 칭호. 이미 찾은 곳이면 None."""
    m = mark_at(spot_id)
    got = found(save)
    if m is None or spot_id in got:
        return None
    got.append(spot_id)
    from src.story import story
    st = story.state(save)
    jid = f"grandpa_{spot_id}"
    if not any(e["id"] == jid for e in st["journal"]):
        st["journal"].append({"id": jid, "text": m["line"], "day": int(day), "season": season})
        st["journal_toasts"].append(jid)
    title = None
    if len(got) >= total():
        cos = save.data.setdefault("cosmetics", {"titles": [], "float_skins": [], "rod_skins": []})
        tid = cfg()["title_id"]
        if tid not in cos.setdefault("titles", []):
            cos["titles"].append(tid)
            title = tid
    return {"n": len(got), "total": total(), "line": m["line"], "title": title}
