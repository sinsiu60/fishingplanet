"""전설·환상 전용 파이팅 곡 스펙 만들기 (DESIGN.md 43, BOSS_BGM.md B3·B4).

곡마다 주제 A·B(각 8마디)와 화성·악기·타악을 여기서 적고, data/music_patterns.json 의 "boss.songs" 에 써 넣는다
(시험곡 T00 등 다른 곡은 그대로). 그 뒤 python tools/bake_boss.py --preview 로 굽는다.

  python tools/audio/boss_songs.py          스펙 다시 쓰기
  python tools/audio/boss_songs.py --check  서명 검사만 (전설: 주인의 동기 1→5→4 · 단조 · #4·리디안 없음)

선율 표기: "마디:박:도수:길이" (박·길이 = 4분음표 단위, 도수 1=으뜸음 8=옥타브 위, '#7' 이끎음) — 공백으로 나열.
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PAT = os.path.join(ROOT, "data", "music_patterns.json")


def mel(src: str, shift: int = 0, bar_off: int = 0) -> list:
    """'마디:박:도수:길이 …' → [[마디, 박, 도수, 길이]] (shift = 도수 이동, bar_off = 마디 이동)."""
    out = []
    for tok in src.split():
        b, at, d, ln = tok.split(":")
        if d.lstrip("-").isdigit():
            d = int(d) + shift
        elif shift:
            d = d[0] + str(int(d[1:]) + shift)
        out.append([int(b) + bar_off, float(at), d, float(ln)])
    return out


def motif(bar: int, beat: float = 0.0, base: int = 1, big: float = 1.0) -> list:
    """주인의 동기: 으뜸음 → 5도 → 4도 (4분 · 4분 · 2분). big = 길이 배율 (크게 = 2배)."""
    return [[bar, beat, base, 1.0 * big], [bar, beat + 1.0 * big, base + 4, 1.0 * big], [bar, beat + 2.0 * big, base + 3, 2.0 * big]]


def part(inst, style, gain, **kw) -> dict:
    return dict(inst=inst, style=style, gain=gain, **kw)


def lead(inst, notes, gain=0.5, oct=0, **kw) -> dict:
    return dict(inst=inst, style="melody", gain=gain, oct=oct, notes=notes, **kw)


# ───────────────────────── 전설 12곡 ─────────────────────────
# 주제 A·B 는 모두 0마디(B는 8마디)에서 주인의 동기로 시작한다.

THEMES = {
    "L01": ("0:0:1:1 0:1:5:1 0:2:4:2 1:0:3:1 1:1:2:1 1:2:1:2 2:0:5:1.5 2:1.5:6:.5 2:2:5:1 2:3:4:1 3:0:3:4 "
            "4:0:1:1 4:1:5:1 4:2:4:2 5:0:6:1 5:1:5:1 5:2:4:1 5:3:3:1 6:0:2:2 6:2:#7:2 7:0:1:4",
            "8:0:1:1 8:1:5:1 8:2:4:2 9:0:6:1 9:1:5:1 9:2:4:2 10:0:3:2 10:2:2:2 11:0:1:4 "
            "12:0:5:1 12:1:6:1 12:2:7:2 13:0:8:2 13:2:7:1 13:3:6:1 14:0:5:2 14:2:#7:2 15:0:8:4"),
    "L02": ("0:0:1:1 0:1:5:1 0:2:4:2 1:0:5:.5 1:.5:6:.5 1:1:7:1 1:2:8:2 2:0:7:1 2:1:6:1 2:2:5:1 2:3:4:1 3:0:5:4 "
            "4:0:1:1 4:1:5:1 4:2:4:2 5:0:3:.5 5:.5:4:.5 5:1:5:1 5:2:6:2 6:0:5:1 6:1:4:1 6:2:3:1 6:3:2:1 7:0:1:4",
            "8:0:1:1 8:1:5:1 8:2:4:2 9:0:8:1 9:1:7:1 9:2:6:1 9:3:5:1 10:0:6:2 10:2:4:2 11:0:5:4 "
            "12:0:3:1 12:1:4:1 12:2:5:1 12:3:6:1 13:0:7:2 13:2:8:2 14:0:6:1 14:1:5:1 14:2:#7:2 15:0:8:4"),
    "L03": ("0:0:1:1 0:1:5:1 0:2:4:2 1:0:3:2 1:2:4:2 2:0:5:3 2:3:6:1 3:0:5:4 "
            "4:0:1:1 4:1:5:1 4:2:4:2 5:0:6:2 5:2:5:2 6:0:4:2 6:2:3:2 7:0:2:4",
            "8:0:1:1 8:1:5:1 8:2:4:2 9:0:3:2 9:2:2:2 10:0:6:3 10:3:5:1 11:0:4:4 "
            "12:0:5:2 12:2:6:2 13:0:7:2 13:2:8:2 14:0:7:2 14:2:#7:2 15:0:8:4"),
    "L04": ("0:0:1:1 0:1:5:1 0:2:4:2 1:1:3:.5 1:1.5:2:1.5 2:0:1:1.5 2:1.5:3:1.5 3:0:5:3 "
            "4:0:1:1 4:1:5:1 4:2:4:2 5:1:6:.5 5:1.5:5:1.5 6:0:4:1.5 6:1.5:3:1.5 7:0:2:3",
            "8:0:1:1 8:1:5:1 8:2:4:2 9:1:5:.5 9:1.5:6:1.5 10:0:7:1.5 10:1.5:6:1.5 11:0:5:3 "
            "12:0:6:1.5 12:1.5:7:1.5 13:0:8:3 14:0:7:1.5 14:1.5:#7:1.5 15:0:8:3"),
    "L05": ("0:0:1:1 0:1:5:1 0:2:4:2 1:0:3:4 2:0:2:2 2:2:1:2 3:0:0:4 "
            "4:0:1:1 4:1:5:1 4:2:4:2 5:0:6:4 6:0:5:2 6:2:4:2 7:0:5:4",
            "8:0:1:1 8:1:5:1 8:2:4:2 9:0:3:2 9:2:2:2 10:0:1:4 11:0:-1:4 "
            "12:0:1:2 12:2:3:2 13:0:5:4 14:0:4:2 14:2:#7:2 15:0:8:4"),
    "L07": ("0:0:1:1 0:1:5:1 0:2:4:2 1:0:3:1.5 1:1.5:4:.5 1:2:6:2 2:0:5:1 2:1:4:1 2:2:3:1 2:3:2:1 3:0:1:4 "
            "4:0:1:1 4:1:5:1 4:2:4:2 5:0:6:1 5:1:7:1 5:2:8:2 6:0:7:1 6:1:6:1 6:2:5:2 7:0:4:4",
            "8:0:1:1 8:1:5:1 8:2:4:2 9:0:6:2 9:2:7:2 10:0:5:3 10:3:4:1 11:0:3:4 "
            "12:0:4:1 12:1:5:1 12:2:6:2 13:0:5:2 13:2:4:2 14:0:2:2 14:2:3:2 15:0:1:4"),
    "L08": ("0:0:1:1 0:1:5:1 0:2:4:2 1:0:5:.5 1:.5:4:.5 1:1:3:1 1:2:2:2 2:0:3:1 2:1:4:1 2:2:5:1 2:3:7:1 3:0:5:4 "
            "4:0:1:1 4:1:5:1 4:2:4:2 5:0:3:1 5:1:2:1 5:2:1:2 6:0:2:1 6:1:3:1 6:2:#7:2 7:0:1:4",
            "8:0:1:1 8:1:5:1 8:2:4:2 9:0:8:2 9:2:7:2 10:0:6:1 10:1:5:1 10:2:4:2 11:0:5:4 "
            "12:0:6:2 12:2:5:2 13:0:4:2 13:2:3:2 14:0:2:2 14:2:#7:2 15:0:1:4"),
    "L09": ("0:0:1:1 0:1:5:1 0:2:4:2 1:0:5:.5 1:.5:6:.5 1:1:7:.5 1:1.5:8:1.5 1:3:9:1 2:0:8:2 2:2:7:1 2:3:5:1 3:0:8:4 "
            "4:0:1:1 4:1:5:1 4:2:4:2 5:0:6:.5 5:.5:7:.5 5:1:8:2 5:3:10:1 6:0:9:2 6:2:8:2 7:0:7:4",
            "8:0:1:1 8:1:5:1 8:2:4:2 9:0:5:1 9:1:7:1 9:2:9:2 10:0:10:2 10:2:9:1 10:3:8:1 11:0:7:4 "
            "12:0:8:1 12:1:9:1 12:2:10:2 13:0:11:2 13:2:12:2 14:0:10:2 14:2:#7:2 15:0:8:4"),
    "L10": ("0:0:1:1 0:1:5:1 0:2:4:2 1:0:1:.5 1:.5:1:.5 1:1:3:.5 1:1.5:4:.5 1:2:5:2 2:0:6:1 2:1:5:1 2:2:3:2 3:0:1:4 "
            "4:0:1:1 4:1:5:1 4:2:4:2 5:0:5:.5 5:.5:5:.5 5:1:6:.5 5:1.5:7:.5 5:2:8:2 6:0:7:1 6:1:6:1 6:2:5:2 7:0:#7:4",
            "8:0:1:1 8:1:5:1 8:2:4:2 9:0:3:1 9:1:3:.5 9:1.5:4:.5 9:2:5:2 10:0:8:2 10:2:7:2 11:0:6:4 "
            "12:0:5:1 12:1:6:1 12:2:7:1 12:3:8:1 13:0:9:2 13:2:8:2 14:0:7:2 14:2:#7:2 15:0:8:4"),
    "L11": ("0:0:1:1 0:1:5:1 0:2:4:2 1:1:3:2 2:0:2:1 2:1:3:1 2:2:5:1 3:0:4:3 "
            "4:0:1:1 4:1:5:1 4:2:4:2 5:1:6:2 6:0:5:1 6:1:4:1 6:2:3:1 7:0:2:3",
            "8:0:1:1 8:1:5:1 8:2:4:2 9:1:8:2 10:0:7:1 10:1:6:1 10:2:5:1 11:0:4:3 "
            "12:0:5:1 12:1:6:1 12:2:7:1 13:0:8:3 14:0:7:1.5 14:1.5:#7:1.5 15:0:8:3"),
}
# 용등(L06)·오르시엘(L12): 앞 전설 주제 조각을 차례로
L06_OWN = ("0:0:1:2 0:2:5:2 1:0:4:4 2:0:3:1 2:1:4:1 2:2:5:2 3:0:#7:4 "
           "4:0:1:2 4:2:5:2 5:0:4:4 6:0:6:2 6:2:5:2 7:0:#7:4",
           "8:0:8:2 8:2:12:2 9:0:11:4 10:0:10:2 10:2:9:2 11:0:8:4 "
           "12:0:6:2 12:2:5:2 13:0:4:2 13:2:3:2 14:0:2:2 14:2:#7:2 15:0:8:4")
L12_OWN = ("0:0:1:2 0:2:5:2 1:0:4:4 2:0:5:2 2:2:6:2 3:0:7:2 3:2:5:2 "
           "4:0:1:2 4:2:5:2 5:0:4:4 6:0:3:2 6:2:2:2 7:0:1:4",
           "8:0:8:2 8:2:12:2 9:0:11:4 10:0:12:2 10:2:13:2 11:0:14:4 "
           "12:0:12:2 12:2:11:2 13:0:10:2 13:2:9:2 14:0:8:2 14:2:12:2 15:0:15:4")


def frag(sid: str, bars: int, to_bar: int) -> list:
    """다른 전설 주제 A 의 앞 bars 마디를 to_bar 마디로 옮긴 조각 (같은 도수 = 이 곡 조성으로)."""
    return [[b - 0 + to_bar, at, d, ln] for b, at, d, ln in mel(THEMES[sid][0]) if b < bars]


def ab(sid: str, shift: int = 0) -> list:
    a, b = THEMES[sid]
    return mel(a, shift) + mel(b, shift)


def ba(sid: str) -> list:
    a, b = THEMES[sid]
    return mel(b, 0, -8) + mel(a, 0, 8)


def drums(**kw) -> dict:
    return kw


P16 = {"timp": "x.......x.......", "timp2": "x...x...x...x...", "timp8": "x.x.x.x.x.x.x.x.", "timp16": "xxxxxxxxxxxxxxxx",
       "snare": "....x.......x...", "snare2": "..x.x...x.x.x.x.", "snare16": "x.xxx.xxx.xxx.xx", "hat": "x.x.x.x.x.x.x.x.",
       "big": "x...............", "big2": "x.......x.......", "big4": "x...x...x...x..."}

STR = part("strings", "hold", 0.42)
BASS8 = part("bass", "bass", 0.6, pattern="x.x.x.x.x.x.x.x.")
CHOIR = part("choir", "hold", 0.4)


def legend_songs() -> dict:
    S = {}
    # L01 동네 저수지 — D단조 128: 맑은 피리풍 주선율, 장구 같은 엇박 북
    jang = "x..x..x.x..x..x."
    S["L01"] = dict(kind="legend", root=62, scale="minor", bpm=128, meter=[4, 4], fish="golden_carp",
                    intro=dict(chords=[1, "5M"], hit_inst="horn"),
                    phases=[
                        dict(chords=[1, 1, 6, 6, 7, 7, 1, 1, 4, 4, 6, 6, "5M", "5M", 1, 1],
                             base=[STR, part("pizz", "pizz", 0.3, pattern="x...x...x...x..."), part("bass", "bass", 0.55, pattern="x......x..x.....")],
                             perc=dict(pattern=drums(janggu=jang, timp=P16["timp"]), crisis=drums(janggu="x.xx.xx.xx.xx.xx", timp=P16["timp2"], snare=P16["snare"])),
                             lead=[lead("flute", ab("L01"), 0.55, 1)], choir=[]),
                        dict(chords=[1, 1, 6, 6, 4, 4, "5M", "5M", 1, 1, 7, 7, 6, 6, "5M", "5M"],
                             base=[STR, part("brass", "hits", 0.4, oct=-1, pattern="X.......x.....x."), part("spiccato", "ostinato", 0.28, pattern="x.x.x.x.x.x.x.x."), BASS8],
                             perc=dict(pattern=drums(janggu=jang, timp=P16["timp2"], snare=P16["snare"]), crisis=drums(janggu="xxx.xxx.xxx.xxx.", timp=P16["timp8"], snare=P16["snare2"])),
                             lead=[lead("flute", ba("L01"), 0.5, 1), lead("horn", ba("L01"), 0.32, 0)], choir=[]),
                        dict(chords=[1, 1, 6, 6, 7, 7, 3, 3, 4, 4, 6, 6, "5M", "5M", 1, 1],
                             base=[STR, part("brass", "hold", 0.36, oct=-1), part("spiccato", "ostinato", 0.3), BASS8],
                             perc=dict(pattern=drums(janggu=jang, bigdrum=P16["big4"], timp=P16["timp2"], snare=P16["snare2"], cymbal="x..............."),
                                       crisis=drums(janggu="xxxxxxxxxxxxxxxx", bigdrum=P16["timp8"], timp=P16["timp8"], snare=P16["snare16"])),
                             lead=[lead("flute", ab("L01"), 0.5, 1), lead("trumpet", ab("L01"), 0.34, 0)], choir=[CHOIR]),
                    ])
    # L02 계곡 — E단조 140: 빠른 현악 오스티나토(물살), 날카로운 플루트
    S["L02"] = dict(kind="legend", root=64, scale="minor", bpm=140, meter=[4, 4], fish="tiger_mandarin",
                    intro=dict(chords=[1, "5M"]),
                    phases=[
                        dict(chords=[1, 1, 6, 6, 3, 3, 7, 7, 1, 1, 4, 4, 6, 6, "5M", "5M"],
                             base=[part("spiccato", "ostinato", 0.42, pattern="xxxxxxxxxxxxxxxx", seq="updown"), part("strings", "hold", 0.3), part("bass", "bass", 0.6, pattern="x...x...x...x...")],
                             perc=dict(pattern=drums(timp=P16["timp"], hat="..x...x...x...x."), crisis=drums(timp=P16["timp2"], snare=P16["snare2"], hat=P16["hat"])),
                             lead=[lead("flute", ab("L02"), 0.5, 1)], choir=[]),
                        dict(chords=[1, 1, 6, 6, 4, 4, 7, 7, 1, 1, 6, 6, 4, 4, "5M", "5M"],
                             base=[part("spiccato", "ostinato", 0.4, pattern="xxxxxxxxxxxxxxxx"), part("brass", "hits", 0.42, oct=-1, pattern="x.x...x.x...x.x.", len=1.2), BASS8],
                             perc=dict(pattern=drums(timp=P16["timp2"], snare=P16["snare"], hat=P16["hat"]), crisis=drums(timp=P16["timp8"], snare=P16["snare16"], hat=P16["hat"])),
                             lead=[lead("flute", ba("L02"), 0.48, 1), lead("trumpet", ba("L02"), 0.3, 0)], choir=[]),
                        dict(chords=[1, 1, 6, 6, 3, 3, 7, 7, 4, 4, 6, 6, "5M", "5M", 1, 1],
                             base=[part("spiccato", "ostinato", 0.4, pattern="xxxxxxxxxxxxxxxx"), part("brass", "hold", 0.34, oct=-1), STR, BASS8],
                             perc=dict(pattern=drums(timp="x.xxx.xxx.xxx.xx", bigdrum=P16["big2"], snare=P16["snare2"], cymbal="x..............."),
                                       crisis=drums(timp=P16["timp16"], bigdrum=P16["big4"], snare=P16["snare16"])),
                             lead=[lead("flute", ab("L02"), 0.48, 1), lead("horn", ab("L02"), 0.32, 0)], choir=[CHOIR]),
                    ])
    # L03 바다 방파제 — C단조 132: 파도처럼 밀려오는 금관 크레센도, 부서지는 심벌즈
    S["L03"] = dict(kind="legend", root=60, scale="minor", bpm=132, meter=[4, 4], fish="silver_bass",
                    intro=dict(chords=[1, "5M"], hit_inst="brass"),
                    phases=[
                        dict(chords=[1, 1, 1, 1, 6, 6, 6, 6, 4, 4, 4, 4, "5M", "5M", "5M", "5M"],
                             base=[part("brass", "hold", 0.42, oct=-1), part("strings", "hold", 0.32), part("bass", "bass", 0.6, pattern="x.....x.x.......")],
                             perc=dict(pattern=drums(cymbal="x...............", bigdrum=P16["big2"], timp=P16["timp"]), crisis=drums(cymbal="x.......x.......", bigdrum=P16["big4"], timp=P16["timp2"], snare=P16["snare"])),
                             lead=[lead("brass", ab("L03"), 0.42, 0)], choir=[]),
                        dict(chords=[1, 1, 6, 6, 7, 7, 3, 3, 4, 4, 6, 6, "5M", "5M", 1, 1],
                             base=[part("brass", "hold", 0.38, oct=-1), part("spiccato", "ostinato", 0.25, pattern="x.x.x.x.x.x.x.x."), STR, BASS8],
                             perc=dict(pattern=drums(cymbal="x.......x.......", bigdrum=P16["big4"], timp=P16["timp2"], snare=P16["snare"]),
                                       crisis=drums(cymbal="x...x...x...x...", bigdrum=P16["timp8"], timp=P16["timp8"], snare=P16["snare2"])),
                             lead=[lead("trumpet", ba("L03"), 0.46, 0)], choir=[]),
                        dict(chords=[1, 1, 6, 6, 3, 3, 7, 7, 4, 4, 6, 6, "5M", "5M", 1, 1],
                             base=[part("brass", "hold", 0.38, oct=-1), part("tremolo", "hold", 0.3, oct=1), STR, BASS8],
                             perc=dict(pattern=drums(cymbal="x...x...x...x...", bigdrum=P16["big4"], timp=P16["timp8"], snare=P16["snare2"]),
                                       crisis=drums(cymbal="x.x.x.x.x.x.x.x.", bigdrum=P16["timp8"], timp=P16["timp16"], snare=P16["snare16"])),
                             lead=[lead("trumpet", ab("L03"), 0.44, 0), lead("horn", ab("L03"), 0.3, -1)], choir=[CHOIR]),
                    ])
    # L04 먼바다 — G단조 120 6/8: 넓은 바다의 뱃노래풍 3박, 웅장한 현악 (6/8 = 마디 12칸)
    sh = "x.....x....."
    S["L04"] = dict(kind="legend", root=55, scale="minor", bpm=120, meter=[6, 8], fish="marlin",
                    intro=dict(chords=[1, "5M"]),
                    phases=[
                        dict(chords=[1, 1, 6, 6, 3, 3, 7, 7, 1, 1, 4, 4, "5M", "5M", 1, 1],
                             base=[part("strings", "hold", 0.45, oct=1), part("spiccato", "ostinato", 0.32, oct=1, pattern="x.x.x.x.x.x."), part("bass", "bass", 0.6, pattern="x.....x.....")],
                             perc=dict(pattern=drums(bigdrum=sh, timp="......x....."), crisis=drums(bigdrum="x..x..x..x..", timp="x.....x.....", snare="...x.....x..")),
                             lead=[lead("strings", ab("L04"), 0.4, 2)], choir=[]),
                        dict(chords=[1, 1, 6, 6, 4, 4, "5M", "5M", 1, 1, 7, 7, 6, 6, "5M", "5M"],
                             base=[part("strings", "hold", 0.42, oct=1), part("spiccato", "ostinato", 0.3, oct=1, pattern="x.x.x.x.x.x."), part("bass", "bass", 0.6, pattern="x..x..x..x..")],
                             perc=dict(pattern=drums(bigdrum=sh, timp="x.....x.....", snare="...x.....x.."), crisis=drums(bigdrum="x..x..x..x..", timp="x..x..x..x..", snare="x..x.xx..x.x")),
                             lead=[lead("horn", ba("L04"), 0.48, 1)], choir=[]),
                        dict(chords=[1, 1, 6, 6, 3, 3, 7, 7, 4, 4, 6, 6, "5M", "5M", 1, 1],
                             base=[part("strings", "hold", 0.42, oct=1), part("brass", "hold", 0.32), part("spiccato", "ostinato", 0.28, oct=1, pattern="x.x.x.x.x.x."), part("bass", "bass", 0.6, pattern="x..x..x..x..")],
                             perc=dict(pattern=drums(bigdrum="x..x..x..x..", timp="x.....x.....", snare="...x.....x..", cymbal="x..........."),
                                       crisis=drums(bigdrum="x.xx.xx.xx.x", timp="x..x..x..x..", snare="x.xx.xx.xx.x")),
                             lead=[lead("horn", ab("L04"), 0.44, 1), lead("strings", ab("L04"), 0.3, 2)], choir=[CHOIR]),
                    ])
    # L05 심해 — B♭단조 96: 아주 낮은 지속음, 심장 같은 북, 깊은 금관
    heart = "x..x............"
    S["L05"] = dict(kind="legend", root=58, scale="minor", bpm=96, meter=[4, 4], fish="coelacanth", reverb=[0.32, 3.2],
                    intro=dict(chords=[1, 1], hit_inst="brass"),
                    phases=[
                        dict(chords=[1, 1, 1, 1, 6, 6, 6, 6, 4, 4, 4, 4, "5M", "5M", 1, 1],
                             base=[part("drone", "drone", 0.5), part("pad", "hold", 0.3, oct=-1)],
                             perc=dict(pattern=drums(bigdrum=heart), crisis=drums(bigdrum="x..x....x..x....", timp=P16["timp"])),
                             lead=[lead("horn", ab("L05"), 0.42, 0)], choir=[]),
                        dict(chords=[1, 1, 6, 6, 4, 4, "5M", "5M", 1, 1, 6, 6, 4, 4, "5M", "5M"],
                             base=[part("drone", "drone", 0.45), part("brass", "hold", 0.42, oct=-1), part("bass", "bass", 0.55, pattern="x.......x.......")],
                             perc=dict(pattern=drums(bigdrum=heart, timp=P16["timp"]), crisis=drums(bigdrum="x..x....x..x....", timp=P16["timp2"], snare=P16["snare"])),
                             lead=[lead("brass", ba("L05"), 0.42, 0)], choir=[]),
                        dict(chords=[1, 1, 6, 6, 3, 3, 7, 7, 4, 4, 6, 6, "5M", "5M", 1, 1],
                             base=[part("drone", "drone", 0.42), part("brass", "hold", 0.38, oct=-1), STR, part("bass", "bass", 0.55, pattern="x.......x.......")],
                             perc=dict(pattern=drums(bigdrum="x..x....x..x....", timp=P16["timp2"], cymbal="x..............."),
                                       crisis=drums(bigdrum="x..x..x.x..x..x.", timp=P16["timp8"], snare=P16["snare2"])),
                             lead=[lead("horn", ab("L05"), 0.42, 0), lead("trumpet", ab("L05"), 0.26, 1)], choir=[CHOIR]),
                    ])
    # L06 용등 (샤르미온 최종) — D 화성단음계 136: L01~L05 조각, 용의 포효 같은 낮은 금관, 가장 큰 북
    own_a, own_b = L06_OWN
    frags = frag("L01", 3, 0) + frag("L02", 3, 3) + frag("L03", 3, 6) + frag("L04", 3, 9) + frag("L05", 2, 12) + motif(14, 0, 1, 1.0)
    S["L06"] = dict(kind="legend", root=62, scale="harmonic", bpm=136, meter=[4, 4], fish="dragon_carp", reverb=[0.3, 3.0],
                    intro=dict(chords=[1, "b2M"], hit_inst="roar"),
                    phases=[
                        dict(chords=[1, 1, 6, 6, 4, 4, 5, 5, 1, 1, 6, 6, "b2M", "b2M", 5, 5],
                             base=[part("roar", "hold", 0.4, oct=-1), STR, part("spiccato", "ostinato", 0.3), BASS8],
                             perc=dict(pattern=drums(taiko="x..x..x...x..x..", bigdrum=P16["big2"], timp=P16["timp2"]),
                                       crisis=drums(taiko="x.xx.xx.x.xx.xx.", bigdrum=P16["big4"], timp=P16["timp8"], snare=P16["snare2"])),
                             lead=[lead("brass", mel(own_a) + mel(own_b), 0.42, 0), lead("trumpet", motif(0) + motif(8), 0.3, 1)], choir=[]),
                        dict(chords=[1, 1, 1, 6, 6, 6, 4, 4, 4, "b7M", "b7M", "b7M", 1, 1, 5, 5],
                             base=[part("roar", "hold", 0.36, oct=-1), STR, part("spiccato", "ostinato", 0.3), BASS8],
                             perc=dict(pattern=drums(taiko="x..x..x...x..x..", bigdrum=P16["big4"], timp=P16["timp2"], snare=P16["snare"]),
                                       crisis=drums(taiko="xxx.xxx.xxx.xxx.", bigdrum=P16["timp8"], timp=P16["timp8"], snare=P16["snare16"])),
                             lead=[lead("flute", frags, 0.4, 1), lead("horn", frags, 0.32, 0)], choir=[]),
                        dict(chords=[1, 1, 6, 6, 4, 4, 5, 5, 1, 1, 6, 6, "b2M", "b2M", 5, 5],
                             base=[part("roar", "hold", 0.38, oct=-1), part("brass", "hits", 0.36, pattern="X.....x.....x...", len=2), part("tremolo", "hold", 0.28, oct=1), BASS8],
                             perc=dict(pattern=drums(taiko="x.xx.xx.x.xx.xx.", bigdrum=P16["big4"], timp=P16["timp8"], snare=P16["snare2"], cymbal="x.......x......."),
                                       crisis=drums(taiko=P16["timp16"], bigdrum=P16["timp8"], timp=P16["timp16"], snare=P16["snare16"])),
                             lead=[lead("trumpet", motif(0, 0, 1, 2.0) + motif(4, 0, 1, 2.0) + motif(8, 0, 1, 2.0) + motif(12, 0, 1, 2.0), 0.5, 1),
                                   lead("brass", motif(0, 0, 1, 2.0) + motif(4, 0, 1, 2.0) + motif(8, 0, 1, 2.0) + motif(12, 0, 1, 2.0), 0.4, 0)],
                             choir=[part("choir", "hold", 0.45)]),
                    ])
    # L07 갈대왕 실바 — F 도리안 124: 숨소리 섞인 갈대 피리, 바람 같은 현악 트레몰로
    S["L07"] = dict(kind="legend", root=65, scale="dorian", bpm=124, meter=[4, 4], fish="silva",
                    intro=dict(chords=[1, 4]),
                    phases=[
                        dict(chords=[1, 1, 4, 4, 1, 1, 7, 7, 1, 1, 4, 4, "b6M", "b6M", 7, 7],
                             base=[part("tremolo", "hold", 0.38), part("bass", "bass", 0.55, pattern="x.....x.........")],
                             perc=dict(pattern=drums(timp=P16["timp"], shaker="..x...x...x...x."), crisis=drums(timp=P16["timp2"], snare=P16["snare"], shaker=P16["hat"])),
                             lead=[lead("reed", ab("L07"), 0.55, 0)], choir=[]),
                        dict(chords=[1, 1, 4, 4, "b6M", "b6M", 7, 7, 1, 1, 4, 4, 3, 3, 7, 7],
                             base=[part("tremolo", "hold", 0.34), part("brass", "hold", 0.34, oct=-1), part("spiccato", "ostinato", 0.25, pattern="x.x.x.x.x.x.x.x."), BASS8],
                             perc=dict(pattern=drums(timp=P16["timp2"], snare=P16["snare"], shaker=P16["hat"]), crisis=drums(timp=P16["timp8"], snare=P16["snare2"], bigdrum=P16["big4"])),
                             lead=[lead("reed", ba("L07"), 0.48, 0), lead("strings", ba("L07"), 0.3, 1)], choir=[]),
                        dict(chords=[1, 1, 4, 4, 1, 1, 7, 7, "b6M", "b6M", 4, 4, 5, 5, 1, 1],
                             base=[part("tremolo", "hold", 0.32), part("brass", "hold", 0.34, oct=-1), STR, BASS8],
                             perc=dict(pattern=drums(timp=P16["timp2"], bigdrum=P16["big2"], snare=P16["snare2"], cymbal="x..............."),
                                       crisis=drums(timp=P16["timp8"], bigdrum=P16["big4"], snare=P16["snare16"])),
                             lead=[lead("reed", ab("L07"), 0.48, 0), lead("horn", ab("L07"), 0.3, -1)], choir=[CHOIR]),
                    ])
    # L08 결정어왕 프리시아 — A단조 130: 수정이 부딪치는 금속 타악, 차가운 현악
    S["L08"] = dict(kind="legend", root=57, scale="minor", bpm=130, meter=[4, 4], fish="prisia",
                    intro=dict(chords=[1, "5M"]),
                    phases=[
                        dict(chords=[1, 1, 6, 6, 7, 7, 3, 3, 4, 4, 1, 1, "5M", "5M", 1, 1],
                             base=[part("strings", "hold", 0.4, oct=1), part("spiccato", "ostinato", 0.32, oct=1, pattern="x.xxx.xxx.xxx.xx"), part("bass", "bass", 0.55, pattern="x.......x.......")],
                             perc=dict(pattern=drums(metal="x..x..x...x..x..", timp=P16["timp"]), crisis=drums(metal="x.xxx.xxx.xxx.xx", timp=P16["timp2"], snare=P16["snare"])),
                             lead=[lead("strings", ab("L08"), 0.4, 2), lead("crystal", motif(0, 0, 8) + motif(8, 0, 8), 0.25, 1)], choir=[]),
                        dict(chords=[1, 1, 6, 6, 4, 4, "5M", "5M", 1, 1, 7, 7, 6, 6, "5M", "5M"],
                             base=[part("strings", "hold", 0.38, oct=1), part("brass", "hold", 0.36), part("spiccato", "ostinato", 0.28, oct=1), BASS8],
                             perc=dict(pattern=drums(metal="x..x..x...x..x..", timp=P16["timp2"], snare=P16["snare"]), crisis=drums(metal=P16["timp16"], timp=P16["timp8"], snare=P16["snare2"])),
                             lead=[lead("trumpet", ba("L08"), 0.42, 1)], choir=[]),
                        dict(chords=[1, 1, 6, 6, 3, 3, 7, 7, 4, 4, 6, 6, "5M", "5M", 1, 1],
                             base=[part("strings", "hold", 0.36, oct=1), part("brass", "hold", 0.34), part("spiccato", "ostinato", 0.26, oct=1), BASS8],
                             perc=dict(pattern=drums(metal="x..x..x...x..x..", timp="x.x.x...x.x.x...", bigdrum=P16["big2"], cymbal="x..............."),
                                       crisis=drums(metal=P16["timp16"], timp=P16["timp16"], bigdrum=P16["big4"], snare=P16["snare16"])),
                             lead=[lead("horn", ab("L08"), 0.42, 1), lead("strings", ab("L08"), 0.28, 2)], choir=[CHOIR]),
                    ])
    # L09 천공어 에어리스 — E♭단조 156: 하늘로 치솟는 금관, 빠른 현악 상승 음형
    S["L09"] = dict(kind="legend", root=63, scale="minor", bpm=156, meter=[4, 4], fish="aeris",
                    intro=dict(chords=[1, "5M"]),
                    phases=[
                        dict(chords=[1, 1, 6, 6, 7, 7, 1, 1, 4, 4, 6, 6, "5M", "5M", "5M", "5M"],
                             base=[part("spiccato", "arp", 0.4, pattern="xxxxxxxxxxxxxxxx", seq="up"), part("strings", "hold", 0.3), part("bass", "bass", 0.55, pattern="x...x...x...x...")],
                             perc=dict(pattern=drums(timp=P16["timp"], snare=P16["snare"], hat=P16["hat"]), crisis=drums(timp=P16["timp2"], snare=P16["snare2"], hat="xxxxxxxxxxxxxxxx")),
                             lead=[lead("strings", ab("L09", -7), 0.4, 1)], choir=[]),
                        dict(chords=[1, 1, 6, 6, 7, 7, 3, 3, 4, 4, 6, 6, "5M", "5M", 1, 1],
                             base=[part("spiccato", "arp", 0.36, pattern="xxxxxxxxxxxxxxxx", seq="up"), part("brass", "hits", 0.38, oct=-1, pattern="X.......X.....x."), BASS8],
                             perc=dict(pattern=drums(timp=P16["timp2"], snare=P16["snare2"], hat=P16["hat"]), crisis=drums(timp=P16["timp8"], snare=P16["snare16"], bigdrum=P16["big4"])),
                             lead=[lead("trumpet", ba("L09"), 0.42, 0), lead("horn", ba("L09"), 0.28, -1)], choir=[]),
                        dict(chords=[1, 1, 6, 6, 3, 3, 7, 7, 4, 4, 6, 6, "5M", "5M", 1, 1],
                             base=[part("spiccato", "arp", 0.34, pattern="xxxxxxxxxxxxxxxx", seq="up"), part("brass", "hold", 0.34, oct=-1), STR, BASS8],
                             perc=dict(pattern=drums(timp="x.x.x...x.x.x...", bigdrum=P16["big4"], snare=P16["snare2"], cymbal="x.......x......."),
                                       crisis=drums(timp=P16["timp16"], bigdrum=P16["timp8"], snare=P16["snare16"])),
                             lead=[lead("trumpet", ab("L09"), 0.42, 0), lead("strings", ab("L09"), 0.26, 1)], choir=[CHOIR]),
                    ])
    # L10 불꽃상어 이그니스 — C#단조 148: 공격적인 큰북 연타, 거칠게 찌그러진 낮은 신스, 금관
    S["L10"] = dict(kind="legend", root=61, scale="minor", bpm=148, meter=[4, 4], fish="ignis",
                    intro=dict(chords=[1, "b2M"], hit_inst="roar"),
                    phases=[
                        dict(chords=[1, 1, 1, 1, 6, 6, 7, 7, 1, 1, 1, 1, 6, 6, "5M", "5M"],
                             base=[part("grit", "bass", 0.5, pattern="x.x.xx.xx.x.xx.x"), part("strings", "hold", 0.3)],
                             perc=dict(pattern=drums(taiko="x..x..x.x..x..x.", bigdrum=P16["big2"]), crisis=drums(taiko="x.xxx.xxx.xxx.xx", bigdrum=P16["big4"], snare=P16["snare2"])),
                             lead=[lead("brass", ab("L10"), 0.4, 0)], choir=[]),
                        dict(chords=[1, 1, 6, 6, 7, 7, 1, 1, 4, 4, "b2M", "b2M", "5M", "5M", 1, 1],
                             base=[part("grit", "bass", 0.45, pattern="x.x.xx.xx.x.xx.x"), part("brass", "hits", 0.4, pattern="X..X..X...X..X..", len=1.5), STR],
                             perc=dict(pattern=drums(taiko="x.xx.xx.x.xx.xx.", bigdrum=P16["big4"], snare=P16["snare"]), crisis=drums(taiko=P16["timp16"], bigdrum=P16["timp8"], snare=P16["snare16"])),
                             lead=[lead("trumpet", ba("L10"), 0.44, 0)], choir=[]),
                        dict(chords=[1, 1, 6, 6, 7, 7, 3, 3, 4, 4, "b2M", "b2M", "5M", "5M", 1, 1],
                             base=[part("grit", "bass", 0.45, pattern="xxxxxxxxxxxxxxxx", len=0.9), part("brass", "hold", 0.36, oct=-1), part("brass", "hits", 0.32, pattern="X..X..X...X..X..", len=1.5), STR],
                             perc=dict(pattern=drums(taiko="x.xx.xx.x.xx.xx.", bigdrum=P16["big4"], timp=P16["timp8"], snare=P16["snare2"], cymbal="x...x...x...x..."),
                                       crisis=drums(taiko=P16["timp16"], bigdrum=P16["timp8"], timp=P16["timp16"], snare=P16["snare16"])),
                             lead=[lead("trumpet", ab("L10"), 0.44, 0), lead("brass", ab("L10"), 0.32, -1)], choir=[CHOIR]),
                    ])
    # L11 극광어 보레알리스 — B단조 118 3/4: 얼음 같은 첼레스타 + 현악 트레몰로, 장엄한 왈츠 (3/4 = 마디 12칸)
    waltz_bass, waltz_ch = "x...........", "....x...x..."
    S["L11"] = dict(kind="legend", root=59, scale="minor", bpm=118, meter=[3, 4], fish="borealis", reverb=[0.3, 3.0],
                    intro=dict(chords=[1, "5M"]),
                    phases=[
                        dict(chords=[1, 1, 6, 6, 4, 4, "5M", "5M", 1, 1, 7, 7, 6, 6, "5M", "5M"],
                             base=[part("tremolo", "hold", 0.36), part("bass", "bass", 0.55, pattern=waltz_bass), part("pizz", "hits", 0.3, pattern=waltz_ch, len=1.5)],
                             perc=dict(pattern=drums(timp=waltz_bass), crisis=drums(timp="x...x...x...", snare="....x...x...")),
                             lead=[lead("celesta", ab("L11"), 0.5, 1)], choir=[]),
                        dict(chords=[1, 1, 6, 6, 3, 3, 7, 7, 4, 4, 6, 6, "5M", "5M", 1, 1],
                             base=[part("tremolo", "hold", 0.32), part("brass", "hits", 0.34, oct=-1, pattern=waltz_ch, len=2), part("bass", "bass", 0.55, pattern=waltz_bass)],
                             perc=dict(pattern=drums(timp=waltz_bass, bigdrum=waltz_bass), crisis=drums(timp="x...x...x...", bigdrum="x...x...x...", snare="....x...x...")),
                             lead=[lead("horn", ba("L11"), 0.44, 0), lead("celesta", ba("L11"), 0.3, 1)], choir=[]),
                        dict(chords=[1, 1, 6, 6, 4, 4, "5M", "5M", 1, 1, 7, 7, 6, 6, "5M", "5M"],
                             base=[part("tremolo", "hold", 0.32), part("brass", "hold", 0.32, oct=-1), STR, part("bass", "bass", 0.55, pattern=waltz_bass)],
                             perc=dict(pattern=drums(timp="x...x...x...", bigdrum=waltz_bass, cymbal="x..........."),
                                       crisis=drums(timp="x.x.x.x.x.x.", bigdrum="x...x...x...", snare="x.x.x.x.x.x.")),
                             lead=[lead("trumpet", ab("L11"), 0.42, 0), lead("celesta", ab("L11"), 0.28, 1)], choir=[CHOIR]),
                    ])
    # L12 천해왕 오르시엘 (최종) — D단조 → 4페이즈 D장조 132: 엘드라시온 동기 + 용등 동기, 대합창
    o_a, o_b = L12_OWN
    eld = frag("L07", 3, 0) + frag("L08", 3, 3) + frag("L09", 3, 6) + frag("L10", 3, 9) + frag("L11", 3, 12) + motif(15, 0, 1, 1.0)[:2]
    drg = mel(L06_OWN[0]) + motif(8, 0, 1, 2.0) + motif(12, 0, 1, 2.0)
    epic = [1, 1, 6, 6, 7, 7, 1, 1, 4, 4, 6, 6, "5M", "5M", 1, 1]
    S["L12"] = dict(kind="legend", root=62, scale="minor", bpm=132, meter=[4, 4], fish="orsiel", reverb=[0.3, 3.2],
                    intro=dict(chords=[1, "5M"], hit_inst="roar"),
                    phases=[
                        dict(chords=epic, base=[part("brass", "hold", 0.4, oct=-1), STR, part("spiccato", "ostinato", 0.28), BASS8],
                             perc=dict(pattern=drums(timp=P16["timp2"], bigdrum=P16["big2"], snare=P16["snare"]),
                                       crisis=drums(timp=P16["timp8"], bigdrum=P16["big4"], snare=P16["snare2"])),
                             lead=[lead("horn", mel(o_a) + mel(o_b), 0.44, 0)], choir=[]),
                        dict(chords=[1, 1, 1, 6, 6, 6, 4, 4, 4, 7, 7, 7, 3, 3, 3, "5M"],
                             base=[part("tremolo", "hold", 0.3, oct=1), STR, part("spiccato", "ostinato", 0.28), BASS8],
                             perc=dict(pattern=drums(timp=P16["timp2"], bigdrum=P16["big2"], metal="x...........x...", snare=P16["snare"]),
                                       crisis=drums(timp=P16["timp8"], bigdrum=P16["big4"], metal="x..x..x..x..x..x", snare=P16["snare2"])),
                             lead=[lead("reed", eld, 0.4, 0), lead("celesta", eld, 0.24, 1), lead("trumpet", eld, 0.26, 0)], choir=[part("choir", "hold", 0.3)]),
                        dict(chords=[1, 1, 6, 6, 4, 4, "5M", "5M", 1, 1, 6, 6, "b2M", "b2M", "5M", "5M"],
                             base=[part("roar", "hold", 0.36, oct=-1), part("brass", "hits", 0.32, pattern="X.....x.....x...", len=2), STR, BASS8],
                             perc=dict(pattern=drums(taiko="x..x..x...x..x..", bigdrum=P16["big4"], timp=P16["timp8"], snare=P16["snare2"], cymbal="x..............."),
                                       crisis=drums(taiko="x.xx.xx.x.xx.xx.", bigdrum=P16["timp8"], timp=P16["timp16"], snare=P16["snare16"])),
                             lead=[lead("brass", drg, 0.42, 0), lead("trumpet", drg, 0.32, 1)], choir=[part("choir", "hold", 0.42)]),
                        dict(chords=[1, 1, 4, 4, 6, 6, 5, 5, 1, 1, 4, 4, 2, 2, 5, 5], scale="major",
                             base=[part("brass", "hold", 0.4, oct=-1), part("strings", "hold", 0.42), part("spiccato", "ostinato", 0.3), part("harp", "arp", 0.25, oct=1, pattern="x.x.x.x.x.x.x.x."), BASS8],
                             perc=dict(pattern=drums(timp=P16["timp8"], bigdrum=P16["big4"], snare=P16["snare2"], cymbal="x.......x......."),
                                       crisis=drums(timp=P16["timp16"], bigdrum=P16["timp8"], snare=P16["snare16"], cymbal="x...x...x...x...")),
                             lead=[lead("trumpet", mel(o_a) + mel(o_b), 0.46, 1), lead("horn", mel(o_a) + mel(o_b), 0.36, 0), lead("strings", mel(o_a) + mel(o_b), 0.26, 1)],
                             choir=[part("choir", "hold", 0.48), part("choir_a", "hold", 0.26, oct=1)]),
                    ])
    for sid, sp in S.items():
        sp["_설명"] = f"{sid} — BOSS_BGM.md 전설 표 (B3, tools/audio/boss_songs.py 가 씀)"
    return S


# ───────────────────────── 검사 ─────────────────────────

def has_owner_motif(notes) -> bool:
    """주선율에 으뜸음 → 5도 → 4도 (4분·4분·2분 비율) 가 있는가."""
    ns = sorted(([b, at, d, ln] for b, at, d, ln in notes if isinstance(d, int)), key=lambda n: (n[0], n[1]))
    for i in range(len(ns) - 2):
        a, b, c = ns[i], ns[i + 1], ns[i + 2]
        if (a[2] - 1) % 7 == 0 and b[2] - a[2] == 4 and c[2] - a[2] == 3 and abs(b[3] - a[3]) < 1e-6 and abs(c[3] - 2 * a[3]) < 1e-6:
            return True
    return False


def check(songs: dict) -> int:
    bad = 0
    for sid, sp in songs.items():
        if sp.get("kind") != "legend" or sp.get("test"):
            continue
        sc = {sp.get("scale")} | {p.get("scale") for p in sp["phases"] if p.get("scale")}
        if "lydian" in sc or "whole" in sc:
            print(sid, "전설에 리디안·전음음계"); bad += 1
        txt = json.dumps(sp)
        if '"#4"' in txt:
            print(sid, "전설에 #4 (환상 동기 재료)"); bad += 1
        motif_ok = any(has_owner_motif(l["notes"]) for p in sp["phases"] for l in p.get("lead", []))
        if not motif_ok:
            print(sid, "주인의 동기 없음"); bad += 1
        for i, p in enumerate(sp["phases"]):
            if len(p["chords"]) != 16:
                print(sid, i + 1, "페이즈 화성이 16마디가 아님", len(p["chords"])); bad += 1
    print("서명 검사:", "ok" if not bad else f"{bad}개 문제")
    return bad


def main(argv) -> int:
    songs = legend_songs()
    if check(songs):
        return 1
    if "--check" in argv:
        return 0
    s = open(PAT, encoding="utf-8").read()
    data = json.loads(s)
    cur = data["boss"]["songs"]
    for k in list(cur):
        if k.startswith("L") and k not in songs:
            del cur[k]
    cur.update(songs)
    blk = json.dumps(data["boss"], ensure_ascii=False)
    i = s.rindex('"boss": {')
    s = s[:i] + '"boss": ' + blk + "\n}\n"
    json.loads(s)
    open(PAT, "w", encoding="utf-8").write(s)
    print("썼음:", ", ".join(songs))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
