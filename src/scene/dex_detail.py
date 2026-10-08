"""도감 오른쪽 상세 칸 (DEX_UI.md, 목업 tools/art/reference/dex/dex_redesign.png).

구역 5개를 가로 구분선으로 나눈다: 1 이름(굵은 이름 · 등급 배지 · 난이도 별 · 설명 2줄) / 2 서식(시계·날씨·자·계절 아이콘 2칸 × 2줄) /
3 내 기록(최대·최고·잡은 수 상자 — 못 잡았으면 "아직 잡지 못했어요") / 4 도감 별 · 숙련(단계 + 다음 단계 막대) /
5 해금(자물쇠/체크 + 짧은 이름 + 작은 막대 + n/n회, 누르면 내용). 어떤 물고기도 줄바꿈·넘침 없이: 넘치면 글자 한 단계 작게 → 그래도 넘치면 '…'.

draw(scene, canvas, d, f, kind) → 누를 수 있는 칸 [(rect, 제목, 내용 줄들)] (해금된 항목 · 패턴).
kind: normal(낚시터 도감) · phantom(환상) · limited(계절·이벤트 한정)
"""
import pygame

from src.core.config import load_json
from src.core.fonts import get_font
from src.core.weather import WEATHER_KO
from src.fishing.patterns import TIP_SHORT, fish_patterns
from src.render.fish_draw import RANK_COLORS
from src.save import dexbook
from src.save.save_game import baits
from src.ui import dex_icons as ic
from src.ui import widgets as ui
from src.ui.hud import text, wrap_text
from src.ui.shop_ui import btext

# 색 규칙 (상세 칸 안에서만)
WHITE, SUB, GRAY = (232, 236, 245), (110, 118, 145), (140, 148, 170)
YELLOW, MINT = (255, 220, 120), (170, 255, 200)
DIV = (46, 56, 86)
BOX_BG, BOX_BORDER = (22, 30, 54), (46, 56, 86)
STAR_DARK = (60, 64, 84)
RARITY_KO = {"common": "일반", "uncommon": "고급", "rare": "희귀", "phantom": "환상", "legend": "전설"}
RARITY_COL = {"common": (230, 230, 230), "uncommon": (130, 230, 150), "rare": (130, 190, 255),
              "phantom": (190, 120, 255), "legend": (255, 214, 90)}
TIME_KO = {"morning": "아침", "day": "낮", "evening": "저녁", "night": "밤"}
SEASON_KO = {"spring": "봄", "summer": "여름", "autumn": "가을", "winter": "겨울"}


def _w(s: str, size: int) -> int:
    return get_font(size).size(s)[0]


def fit_text(canvas, s: str, pos, col, max_w: int, anchor: str = "midleft", bold: bool = False) -> pygame.Rect:
    """한 줄: 11 로 안 들어가면 10, 그래도 넘치면 뒤를 '…'."""
    size = 11 if _w(s, 11) + (1 if bold else 0) <= max_w else 10
    if _w(s, size) > max_w:
        while len(s) > 1 and _w(s + "…", size) > max_w:
            s = s[:-1]
        s += "…"
    if bold and size == 11:
        return btext(canvas, s, pos, col, 11, anchor)
    return text(canvas, s, pos, col, size, anchor)


def _join(values, table, all_count) -> str:
    return "시간 전체" if table is TIME_KO and len(values) >= all_count else \
        ("날씨 전체" if len(values) >= all_count else " · ".join(table[v] for v in values))


def _div(canvas, d: pygame.Rect, y: int) -> None:
    canvas.fill(DIV, (d.x + 5, y, d.w - 10, 1))


def _stars5(canvas, x_right: int, cy: int, n: int, col=YELLOW) -> None:
    """★ 5개 (n 개 노랑, 나머지 어둡게), 오른쪽 끝 x_right."""
    s_on, s_off = "★" * n, "★" * (5 - n)
    w_off = _w(s_off, 11) if s_off else 0
    if s_off:
        text(canvas, s_off, (x_right, cy), STAR_DARK, 11, "midright", shadow=False)
    if s_on:
        text(canvas, s_on, (x_right - w_off, cy), col, 11, "midright")


def _stars5_left(canvas, x: int, cy: int, n: int) -> None:
    w = _w("★" * 5, 11)
    _stars5(canvas, x + w, cy, n)


def _badge(canvas, s: str, right: int, cy: int, col) -> pygame.Rect:
    r = pygame.Rect(0, 0, _w(s, 11) + 6, 13)
    r.midright = (right, cy)
    canvas.fill((16, 20, 36), r)
    pygame.draw.rect(canvas, col, r, 1)
    text(canvas, s, r.center, col, 11, "center")
    return r


def _bar(canvas, x: int, y: int, w: int, h: int, frac: float, col, track=(34, 40, 62)) -> None:
    canvas.fill(track, (x, y, w, h))
    canvas.fill(col, (x, y, int(w * max(0.0, min(1.0, frac))), h))


def _season_of(f: dict, kind: str) -> tuple[str | None, str]:
    """계절 칸: (아이콘 계절, 글자)."""
    from src.core import season as seasons
    if kind == "limited":
        if f.get("season"):
            return f["season"], f"{seasons.name(f['season'], f.get('continent') or 'sharmion')} 한정"
        return None, f"'{f.get('event_name', '')}' 때만"
    sf = load_json("seasons.json")["fish"].get(f["id"])
    if not sf or not sf.get("good"):
        return None, "계절 무관"
    cont = "eldrasion" if f.get("spot") in _eldra_spots() else "sharmion"
    good = "·".join(seasons.name(s, cont) for s in sf["good"])
    return sf["good"][0], f"{good}에 잘 잡힘"


def _eldra_spots() -> set:
    return {s["id"] for s in load_json("spots.json")["spots"] if s.get("continent") == "eldrasion"}


def draw(scene, canvas, d: pygame.Rect, f: dict, kind: str = "normal", border=None, fill=(16, 20, 36)) -> list:
    save = scene.save
    ui.panel(canvas, d, border or ui.BORDER, fill)
    e = dexbook.entry(save, f)
    x = d.x + 6
    right = d.right - 6
    clicks: list = []
    seen = save.data["dex"].get(f["id"], {}).get("seen")
    hinted = f["rarity"] in ("uncommon", "rare", "legend") or kind in ("limited", "phantom")
    if e or kind == "phantom":
        revealed, clue_rows = True, []
    elif kind == "limited":
        revealed, clue_rows = False, []   # 한정: 잡기 전엔 계절·이벤트만 (시간·날씨는 그대로 숨김)
    else:
        revealed, clue_rows = save.hint_status(f)

    # ── 1. 이름 · 등급 · 난이도 · 설명 ──
    y = d.y + 10
    br = _badge(canvas, RARITY_KO[f["rarity"]], right, y, RARITY_COL[f["rarity"]]) if (e or hinted) else None
    name = f["name"] if (e or seen) else "???"
    fit_text(canvas, name, (x, y), WHITE if e else GRAY, (br.x if br else right) - x - 4, bold=True)
    y = d.y + 23
    text(canvas, "난이도", (x, y), SUB, 11, "midleft")
    nd = min(5, (f["difficulty"] + 1) // 2) if e else 0
    _stars5_left(canvas, x + _w("난이도", 11) + 4, y, nd)
    pats = fish_patterns(f) if e else []
    if pats:   # 패턴 (만나 본 것만 이름) — 난이도 줄 오른쪽, 누르면 보기
        ps = save.data.get("patterns_seen", [])
        names = load_json("patterns.json")["names"]
        n_seen = sum(1 for p in pats if p in ps)
        r = fit_text(canvas, f"패턴 {n_seen}/{len(pats)}", (right, y), SUB, 50, "midright")
        lines = [f"{names[p]} — {TIP_SHORT[p]}" if p in ps else "??? (아직 만나지 못한 패턴)" for p in pats]
        clicks.append((r.inflate(6, 4), "패턴", lines))
    if e:
        desc = f["desc"]
    elif kind == "limited":
        desc = "그때가 오면 어딘가에서 모습을 드러낸다고 한다."
    elif f["rarity"] == "legend":
        desc = "특별한 조건에서만 나타난다고 한다."
        bait = next((b for b in baits().values() if b.get("legend_for") == f["id"]), None)
        if bait:
            desc += f" 필요한 미끼: {bait['name']}"
    elif not hinted:
        desc = "아직 잡지 못했다."
    else:
        desc = ""
    _desc(canvas, desc, x, d.y + 36, d.w - 12)
    _div(canvas, d, d.y + 54)

    # ── 2. 서식 (2칸 × 2줄) ──
    cx2 = d.x + 82
    show = e is not None or (hinted and revealed)
    tw = _join(f["times"], TIME_KO, 4) if show else "???"
    ww = _join(f["weathers"], WEATHER_KO, 3) if show else "???"
    sz = f"{f['size_cm'][0]}~{f['size_cm'][1]}cm" if e else "???"
    s_icon, s_txt = _season_of(f, kind)
    if not e and kind == "normal":
        s_txt = "???"
    y1, y2 = d.y + 62, d.y + 75
    ic.clock(canvas, x, y1)
    fit_text(canvas, tw, (x + 10, y1), WHITE, cx2 - x - 14)
    ic.weather(canvas, cx2, y1, f["weathers"] if show else ["clear"])
    fit_text(canvas, ww, (cx2 + 10, y1), WHITE, right - cx2 - 10)
    ic.ruler(canvas, x, y2)
    fit_text(canvas, sz, (x + 10, y2), WHITE, cx2 - x - 14)
    ic.season(canvas, cx2, y2, s_icon)
    fit_text(canvas, s_txt, (cx2 + 10, y2), WHITE, right - cx2 - 10)
    _div(canvas, d, d.y + 83)

    # ── 3. 내 기록 ──
    if e:
        text(canvas, "내 기록", (x, d.y + 90), SUB, 11, "midleft")
        boxes = (("최대", f"{e['max_size']:.1f}cm", 56), ("최고", e["best_rank"], 42), ("잡은 수", str(e["count"]), 0))
        bx = x
        for i, (lab, val, w) in enumerate(boxes):
            w = w or (right - bx)
            r = pygame.Rect(bx, d.y + 96, w, 25)
            canvas.fill(BOX_BG, r)
            pygame.draw.rect(canvas, BOX_BORDER, r, 1)
            text(canvas, lab, (r.centerx, r.y + 7), SUB, 11, "center")
            col = RANK_COLORS.get(val, YELLOW) if lab == "최고" and val != "S" else YELLOW
            vs = val if _w(val, 11) + 1 <= w - 4 else val.replace("cm", "")
            fit_text(canvas, vs, (r.centerx, r.y + 18), col, w - 4, "center", bold=True)
            bx = r.right + 3
        _div(canvas, d, d.y + 125)
        # ── 4. 도감 별 · 숙련 ──
        y = d.y + 132
        text(canvas, "도감 별", (x, y), SUB, 11, "midleft")
        _stars5(canvas, right, y, dexbook.star_count(save, f))
        y = d.y + 144
        m = dexbook.mastery(save, f)
        nxt = dexbook.next_mastery(save, f)
        btext(canvas, f"숙련 {m}단계", (x, y), MINT, 11, "midleft")
        if nxt:
            fit_text(canvas, f"다음 단계까지 {nxt[0]}/{nxt[1]}", (right, y), SUB, d.w - 70, "midright")
            prev = dexbook.thresholds(f)[m - 1] if m > 0 else 0
            frac = (nxt[0] - prev) / max(1, nxt[1] - prev)
        else:
            text(canvas, "최고 단계", (right, y), MINT, 11, "midright")
            frac = 1.0
        _bar(canvas, x, d.y + 151, d.w - 12, 3, frac, MINT)
        _div(canvas, d, d.y + 158)
        rows = _unlock_rows(save, f, e, kind)
    else:
        text(canvas, "아직 잡지 못했어요", (d.centerx, d.y + 96), GRAY, 11, "center")
        _div(canvas, d, d.y + 106)
        rows = []
        if kind == "normal" and hinted:
            prev = {"uncommon": None, "rare": "uncommon", "legend": "rare"}[f["rarity"]]
            if revealed:
                if f["rarity"] == "legend":
                    rows = [("info", "25m 이상 던지기", None, None), ("info", "달력(K)에서 날씨 예보 확인", None, None)]
            else:
                text(canvas, "이만큼 잡으면 단서가 보여요", (x, d.y + 114), SUB, 11, "midleft")
                for t, h, n in clue_rows:
                    rows.append(("clue", f"{RARITY_KO[t]} {'1종 이상' if t == prev else '모두'}", h, n))
        top = d.y + 128 if (kind == "normal" and hinted and not revealed) else d.y + 115
        _draw_rows(canvas, d, rows, top, clicks)
        return clicks
    _draw_rows(canvas, d, rows, d.y + 165, clicks)
    if kind == "normal":   # 가이드 튜토리얼 강조 구역 (TG-04)
        from src.tutorial import targets as T
        for tid, y0, y1 in (("dex.detail.name", 2, 54), ("dex.detail.habitat", 55, 83), ("dex.detail.records", 84, 125),
                            ("dex.detail.stars", 126, 138), ("dex.detail.mastery", 138, 158),
                            ("dex.detail.unlocks", 159, d.h - 2)):
            T.mark_ui(scene, tid, (d.x + 2, d.y + y0, d.w - 4, y1 - y0))
    return clicks


def _desc(canvas, s: str, x: int, y: int, w: int) -> None:
    """설명 최대 2줄 (회색). 11 로 2줄을 넘으면 10, 그래도 넘치면 둘째 줄 끝을 '…'."""
    if not s:
        return
    for size in (11, 10):
        lines = _wrap(s, w, size)
        if len(lines) <= 2:
            break
    if len(lines) > 2:
        last = " ".join(lines[1:])
        while len(last) > 1 and _w(last + "…", size) > w:
            last = last[:-1]
        lines = [lines[0], last + "…"]
    for i, ln in enumerate(lines):
        text(canvas, ln, (x, y + i * 11), GRAY, size, "midleft")


def _wrap(s: str, w: int, size: int) -> list[str]:
    if size == 11:
        return wrap_text(s, w)
    font = get_font(size)
    out, cur = [], ""
    for word in s.split(" "):
        cand = f"{cur} {word}".strip()
        if cur and font.size(cand)[0] > w:
            out.append(cur)
            cur = word
        else:
            cur = cand
    if cur:
        out.append(cur)
    return out


def _unlock_rows(save, f: dict, e: dict, kind: str) -> list:
    """(종류, 짧은 이름, 지금, 필요 [, 내용]) — 예고 힌트 1(3회) · 예고 힌트 2(10회). (선호 리듬은 루어 액션과 함께 삭제, DESIGN 47장)"""
    n = e["count"]
    rows = []
    if kind == "phantom":
        spot = next((s["name"] for s in load_json("spots.json")["spots"] if s["id"] == f["spot"]), "")
        rows.append(("lock", "출몰지", 1, 1, [f"환상 · {spot}"]))
        return rows
    if f.get("hint3"):
        rows.append(("lock", "예고 힌트 1", min(n, 3), 3, [f["hint3"]] if n >= 3 else None))
    if kind == "limited":
        return rows
    if f.get("hint10"):
        rows.append(("lock", "예고 힌트 2", min(n, 10), 10, [f["hint10"]] if n >= 10 else None))
    return rows


def _draw_rows(canvas, d: pygame.Rect, rows: list, top: int, clicks: list) -> None:
    """한 줄씩: 자물쇠/체크 + 짧은 이름 + 작은 막대 + 오른쪽 'n/n회' — 줄바꿈 없음."""
    x, right = d.x + 6, d.right - 6
    step = 12
    for i, row in enumerate(rows):
        y = top + i * step
        if y > d.bottom - 6:
            break
        k, name, have, need = row[0], row[1], row[2], row[3]
        content = row[4] if len(row) > 4 else None
        if k == "info":
            ic.check(canvas, x, y, GRAY)
            fit_text(canvas, name, (x + 10, y), GRAY, right - x - 10)
            continue
        done = (content is not None) if k == "lock" else have >= need
        if done:
            ic.check(canvas, x, y)
        else:
            ic.lock(canvas, x, y)
        nr = fit_text(canvas, name, (x + 10, y), WHITE if done else GRAY, 62)
        cnt = f"{have}/{need}" + ("회" if k == "lock" else "")
        cr = text(canvas, cnt, (right, y), SUB, 11, "midright")
        bx = max(nr.right + 4, x + 74)
        if cr.x - 4 - bx > 8:
            _bar(canvas, bx, y - 1, cr.x - 4 - bx, 2, have / max(1, need), WHITE if done else GRAY)
        if done and content:
            r = pygame.Rect(x - 2, y - 6, right - x + 4, 12)
            clicks.append((r, name, content))


def draw_popup(canvas, d: pygame.Rect, title: str, lines: list[str]) -> None:
    """해금 내용 보기: 상세 칸 아래쪽을 덮는 작은 창 (아무 곳이나 누르면 닫힘)."""
    body = [w for ln in lines for w in wrap_text(ln, d.w - 20)]
    h = 24 + len(body) * 12
    r = pygame.Rect(d.x + 3, max(d.y + 3, d.bottom - 3 - h), d.w - 6, min(h, d.h - 6))
    canvas.fill(ui.SHADOW, r.move(2, 2))
    canvas.fill((24, 30, 52), r)
    pygame.draw.rect(canvas, YELLOW, r, 1)
    text(canvas, title, (r.x + 6, r.y + 9), YELLOW, 11, "midleft")
    for i, ln in enumerate(body):
        if r.y + 21 + i * 12 > r.bottom - 4:
            break
        text(canvas, ln, (r.x + 6, r.y + 21 + i * 12), WHITE, 11, "midleft")
