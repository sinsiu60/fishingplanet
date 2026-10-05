"""전설·환상 전용 파이팅 곡 스펙 만들기 (DESIGN.md 43, BOSS_BGM.md B3·B4).

곡마다 주제 A·B(각 8마디)와 화성·악기·타악을 여기서 적고, data/music_patterns.json 의 "boss.songs" 에 써 넣는다
(시험곡 T00 등 다른 곡은 그대로). 그 뒤 python tools/bake_boss.py --preview 로 굽는다.

  python tools/audio/boss_songs.py          스펙 다시 쓰기
  python tools/audio/boss_songs.py --check  서명 검사만 (전설: 주인의 동기 1→5→4 · 단조 · #4·리디안·4음 동기 없음 /
                                            환상: 이름 없는 것의 동기 1→#4→5→3 · 리디안 · 2페이즈 온음 올림 · 금관·행진 북·3음 동기 없음)

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


# ───────────────────────── 환상 12곡 ─────────────────────────
# 주제 A·B 는 모두 0마디(B는 8마디)에서 '이름 없는 것의 동기'(1 → #4 → 5 → 3, 8분·8분·4분·2분)로 시작한다.
# 음계는 리디안 (도수 4 = #4). 금관·찌그러진 소리·북 행진 없음 — 층을 두껍게 쌓아 풍성함으로 크기를 만든다.
NM = "0:0:1:.5 0:.5:4:.5 0:1:5:1 0:2:3:2 "
NM8 = "8:0:1:.5 8:.5:4:.5 8:1:5:1 8:2:3:2 "
NM4 = "4:0:1:.5 4:.5:4:.5 4:1:5:1 4:2:3:2 "
PH_THEMES = {
    "P01": (NM + "1:0:5:1 1:1:6:1 1:2:8:2 2:0:7:1 2:1:6:1 2:2:5:2 3:0:3:4 " + NM4 + "5:0:2:1 5:1:3:1 5:2:5:2 6:0:6:2 6:2:7:2 7:0:8:4",
            NM8 + "9:0:8:2 9:2:9:2 10:0:10:2 10:2:9:1 10:3:8:1 11:0:7:4 12:0:6:1 12:1:7:1 12:2:8:2 13:0:9:2 13:2:11:2 14:0:10:2 14:2:9:2 15:0:8:4"),
    "P02": (NM + "1:0:2:2 1:2:3:2 2:0:5:3 2:3:4:1 3:0:3:4 " + NM4 + "5:0:6:2 5:2:5:2 6:0:4:2 6:2:2:2 7:0:1:4",
            NM8 + "9:0:5:2 9:2:7:2 10:0:8:3 10:3:7:1 11:0:5:4 12:0:6:2 12:2:8:2 13:0:9:4 14:0:7:2 14:2:6:2 15:0:5:4"),
    "P03": (NM + "1:0:5:1.5 1:1.5:6:.5 1:2:5:2 2:0:3:1 2:1:2:1 2:2:1:2 3:0:2:4 " + NM4 + "5:0:6:1.5 5:1.5:7:.5 5:2:8:2 6:0:7:2 6:2:5:2 7:0:6:4",
            NM8 + "9:0:4:2 9:2:5:2 10:0:6:2 10:2:5:1 10:3:4:1 11:0:3:4 12:0:5:2 12:2:7:2 13:0:8:2 13:2:9:2 14:0:7:2 14:2:6:2 15:0:5:4"),
    "P04": (NM + "1:0:8:.5 1:.5:7:.5 1:1:6:.5 1:1.5:5:.5 1:2:4:1 1:3:3:1 2:0:5:2 2:2:8:2 3:0:7:4 " + NM4
            + "5:0:9:.5 5:.5:8:.5 5:1:7:.5 5:1.5:6:.5 5:2:5:2 6:0:6:2 6:2:7:2 7:0:8:4",
            NM8 + "9:0:10:1 9:1:9:1 9:2:8:2 10:0:9:1 10:1:8:1 10:2:7:2 11:0:5:4 12:0:8:1 12:1:9:1 12:2:10:2 13:0:12:2 13:2:11:2 14:0:9:2 14:2:7:2 15:0:8:4"),
    "P05": (NM + "1:0:2:4 2:0:1:2 2:2:-1:2 3:0:1:4 " + NM4 + "5:0:5:4 6:0:6:2 6:2:5:2 7:0:3:4",
            NM8 + "9:0:4:2 9:2:3:2 10:0:2:4 11:0:1:4 12:0:3:2 12:2:5:2 13:0:8:4 14:0:7:2 14:2:5:2 15:0:8:4"),
    "P06": (NM + "2:0:5:1 2:1:6:1 2:2:5:2 " + NM4 + "6:0:2:1 6:1:3:1 6:2:1:2",
            NM8 + "10:0:6:1 10:1:7:1 10:2:8:2 12:0:5:.5 12:.5:4:.5 12:1:3:1 12:2:2:2 14:0:1:4"),
    "P07": (NM + "1:0:3:1.5 1:1.5:2:.5 1:2:1:2 2:0:2:1 2:1:3:1 2:2:5:2 3:0:6:4 " + NM4 + "5:0:5:1.5 5:1.5:6:.5 5:2:8:2 6:0:7:2 6:2:6:2 7:0:5:4",
            NM8 + "9:0:2:2 9:2:1:2 10:0:-2:2 10:2:1:2 11:0:2:4 12:0:3:2 12:2:5:2 13:0:6:2 13:2:5:2 14:0:3:2 14:2:2:2 15:0:1:4"),
    "P08": (NM + "2:0:5:2 2:2:3:2 3:0:2:4 " + NM4 + "6:0:6:2 6:2:5:2 7:0:3:4",
            NM8 + "9:0:5:4 10:0:8:2 10:2:7:2 11:0:5:4 12:0:6:4 13:0:7:4 14:0:9:2 14:2:7:2 15:0:8:4"),
    "P09": (NM + "1:1:5:.5 1:1.5:6:1.5 2:0:8:1.5 2:1.5:7:1.5 3:0:5:3 " + NM4 + "5:1:2:.5 5:1.5:3:1.5 6:0:5:1.5 6:1.5:6:1.5 7:0:5:3",
            NM8 + "9:1:8:.5 9:1.5:9:1.5 10:0:10:1.5 10:1.5:9:1.5 11:0:8:3 12:0:6:1.5 12:1.5:7:1.5 13:0:8:3 14:0:9:1.5 14:1.5:7:1.5 15:0:8:3"),
    "P10": (NM + "1:0:5:1 1:1:3:1 1:2:2:2 2:0:3:1 2:1:5:1 2:2:6:2 3:0:5:4 " + NM4 + "5:0:6:1 5:1:8:1 5:2:7:2 6:0:6:1 6:1:5:1 6:2:3:2 7:0:2:4",
            NM8 + "9:0:8:2 9:2:7:2 10:0:6:2 10:2:5:2 11:0:3:4 12:0:5:1 12:1:6:1 12:2:8:2 13:0:10:2 13:2:9:2 14:0:8:2 14:2:7:2 15:0:8:4"),
    "P11": (NM + "1:1:5:2 2:0:6:1 2:1:5:1 2:2:3:1 3:0:2:3 " + NM4 + "5:1:6:2 6:0:8:1 6:1:7:1 6:2:6:1 7:0:5:3",
            NM8 + "9:1:8:2 10:0:9:1 10:1:8:1 10:2:7:1 11:0:6:3 12:0:5:1 12:1:6:1 12:2:7:1 13:0:8:3 14:0:9:1.5 14:1.5:7:1.5 15:0:8:3"),
}


def nameless(bar: int, beat: float = 0.0, base: int = 1, big: float = 1.0) -> list:
    """이름 없는 것의 동기: 1 → #4 → 5 → 3 (8분 · 8분 · 4분 · 2분)."""
    return [[bar, beat, base, 0.5 * big], [bar, beat + 0.5 * big, base + 3, 0.5 * big], [bar, beat + 1.0 * big, base + 4, 1.0 * big],
            [bar, beat + 2.0 * big, base + 2, 2.0 * big]]


def pab(sid: str, shift: int = 0) -> list:
    a, b = PH_THEMES[sid]
    return mel(a, shift) + mel(b, shift)


def pba(sid: str) -> list:
    a, b = PH_THEMES[sid]
    return mel(b, 0, -8) + mel(a, 0, 8)


def pfrag(sid: str, src_bar: int, to_bar: int, bars: int = 1) -> list:
    """환상 주제 A 의 src_bar 마디부터 bars 마디를 to_bar 로 옮긴 조각."""
    return [[b - src_bar + to_bar, at, d, ln] for b, at, d, ln in mel(PH_THEMES[sid][0]) if src_bar <= b < src_bar + bars]


LYD1 = [1, 1, 2, 2, 1, 1, 2, 2, 6, 6, 5, 5, 3, 3, 2, 2]
LYD2 = [1, 1, 2, 2, 3, 3, 2, 2, 1, 1, 2, 2, 6, 6, 5, 5]
PULSE = dict(pattern=dict(pulse="x.......x.......", shaker="..x...x...x...x."),
             crisis=dict(pulse="x...x...x...x...", shaker="xxxxxxxxxxxxxxxx"))
PULSE2 = dict(pattern=dict(pulse="x...x...x...x...", shaker="..x...x...x...x."),
              crisis=dict(pulse="x.x.x.x.x.x.x.x.", shaker="xxxxxxxxxxxxxxxx"))
CHOIR_A = part("choir_a", "hold", 0.42)


def phantom_songs() -> dict:
    S = {}

    def song(sid, fish, root, bpm, p1, p2, meter=(4, 4), reverb=(0.34, 3.4), intro=None):
        S[sid] = dict(kind="phantom", root=root, scale="lydian", bpm=bpm, meter=list(meter), fish=fish, reverb=list(reverb),
                      intro=intro or dict(chords=[1, 2], hit_inst="choir_a"), phases=[p1, dict(p2, transpose=2)])

    harp_arp = part("harp", "arp", 0.3, oct=1, pattern="x.x.x.x.x.x.x.x.")
    pad = part("pad", "hold", 0.36)
    pulse_bass = part("synbass", "bass", 0.5, pattern="x.......x.x.....")
    # P01 달그림자 잉어 — C 리디안 104: 달빛 아래 오르골풍 주선율, 느린 하프 아르페지오 → D 리디안 + 합창 "아—"
    song("P01", "moon_shadow_carp", 60, 104,
         dict(chords=LYD1, base=[pad, part("harp", "arp", 0.32, oct=0, pattern="x...x...x...x..."), pulse_bass], perc=PULSE,
              lead=[lead("celesta", pab("P01"), 0.5, 1)], choir=[]),
         dict(chords=LYD2, base=[pad, harp_arp, part("strings", "hold", 0.3), pulse_bass], perc=PULSE2,
              lead=[lead("celesta", pba("P01"), 0.46, 1), lead("glass", pba("P01"), 0.22, 2)], choir=[CHOIR_A]))
    # P02 안개비늘 쏘가리 — E♭ 리디안 112: 안개처럼 번지는 패드, 흐릿한 벨 → 안개가 걷히듯 고음 반짝임
    song("P02", "mist_mandarin", 63, 112,
         dict(chords=LYD1, base=[part("pad", "hold", 0.44), part("glass", "sparkle", 0.16, per_bar=2), pulse_bass], perc=PULSE,
              lead=[lead("glass", pab("P02"), 0.36, 1), lead("pad", pab("P02"), 0.2, 0)], choir=[]),
         dict(chords=LYD2, base=[pad, part("glass", "sparkle", 0.26, oct=1, per_bar=8), part("celesta", "sparkle", 0.2, oct=1, per_bar=6), pulse_bass], perc=PULSE2,
              lead=[lead("celesta", pba("P02"), 0.44, 1)], choir=[CHOIR_A]))
    # P03 노을빛 농어 — G 리디안 116: 따뜻한 기타 하모닉스풍 음, 붉게 물드는 현악 → 현악이 크게 부풀며 합창
    song("P03", "dusk_bass", 55, 116,
         dict(chords=LYD1, base=[part("strings", "hold", 0.34, oct=1), part("harp", "arp", 0.24, oct=1, pattern="x..x..x.x..x..x."), pulse_bass], perc=PULSE,
              lead=[lead("harmonics", pab("P03"), 0.55, 1)], choir=[]),
         dict(chords=LYD2, base=[part("strings", "hold", 0.46, oct=1), part("tremolo", "hold", 0.22, oct=2), harp_arp, pulse_bass], perc=PULSE2,
              lead=[lead("harmonics", pba("P03"), 0.45, 1), lead("strings", pba("P03"), 0.24, 2)], choir=[CHOIR_A]))
    # P04 유성 다랑어 — A 리디안 128: 쏟아지는 별 같은 빠른 하강 아르페지오, 반짝이는 고음 → 아르페지오 2배 속도 + 별똥별 상승
    song("P04", "meteor_tuna", 57, 128,
         dict(chords=LYD1, base=[part("celesta", "fall", 0.3, oct=1, per_bar=8), pad, pulse_bass], perc=PULSE,
              lead=[lead("glass", pab("P04"), 0.4, 1)], choir=[]),
         dict(chords=LYD2, base=[part("celesta", "fall", 0.3, oct=1, per_bar=16), part("harp", "arp", 0.26, oct=1, pattern="xxxxxxxxxxxxxxxx", seq="up"), pad, pulse_bass],
              perc=PULSE2, lead=[lead("glass", pba("P04"), 0.36, 1), lead("celesta", pba("P04"), 0.3, 2)], choir=[CHOIR_A]))
    # P05 심연의 등불고기 — F 리디안 100: 깊은 맥박 같은 신스 베이스, 어둠 속 빛나는 벨 → 벨이 하나씩 켜지듯 늘어나며 합창
    song("P05", "abyss_lantern", 53, 100,
         dict(chords=LYD1, base=[part("synbass", "pulse", 0.5, oct=-1, pattern="x.x.x.x.x.x.x.x.", seq="root"), part("pad", "hold", 0.3), part("glass", "sparkle", 0.16, oct=1, per_bar=1)],
              perc=dict(pattern=dict(pulse="x.......x......."), crisis=dict(pulse="x...x...x...x...", shaker="..x...x...x...x.")),
              lead=[lead("glass", pab("P05"), 0.4, 1)], choir=[]),
         dict(chords=LYD2, base=[part("synbass", "pulse", 0.5, oct=-1, pattern="x.x.x.x.x.x.x.x.", seq="root"), part("pad", "hold", 0.34),
                                 part("glass", "sparkle", 0.22, oct=1, per_bar=6), part("celesta", "sparkle", 0.18, oct=2, per_bar=4)],
              perc=PULSE2, lead=[lead("glass", pba("P05"), 0.38, 1), lead("strings", pba("P05"), 0.22, 1)], choir=[CHOIR_A]))
    # P06 잔향어 — D 리디안 108: 같은 선율이 메아리처럼 겹겹이 (돌림노래) → 메아리 4겹
    song("P06", "echo_fish", 62, 108,
         dict(chords=LYD1, base=[pad, part("harp", "arp", 0.24, pattern="x...x...x...x..."), pulse_bass], perc=PULSE,
              lead=[lead("celesta", pab("P06"), 0.46, 1, canon=[[1.0, 0.6], [2.0, 0.4]])], choir=[]),
         dict(chords=LYD2, base=[pad, harp_arp, part("strings", "hold", 0.26), pulse_bass], perc=PULSE2,
              lead=[lead("celesta", pab("P06"), 0.42, 1, canon=[[1.0, 0.65], [2.0, 0.48], [3.0, 0.34]]), lead("glass", pab("P06"), 0.18, 2, canon=[[1.5, 0.6]])],
              choir=[CHOIR_A]))
    # P07 보랏빛 갈대잉어 — B♭ 리디안 110: 숨결 섞인 갈대 피리, 바람 같은 패드 → 피리가 합창과 겹쳐 노래함
    song("P07", "violet_reed_carp", 58, 110,
         dict(chords=LYD1, base=[part("pad", "hold", 0.4), part("tremolo", "hold", 0.16, oct=1), pulse_bass], perc=PULSE,
              lead=[lead("reed", pab("P07"), 0.55, 1)], choir=[]),
         dict(chords=LYD2, base=[pad, harp_arp, part("tremolo", "hold", 0.2, oct=1), pulse_bass], perc=PULSE2,
              lead=[lead("reed", pba("P07"), 0.5, 1), lead("choir_a", pba("P07"), 0.3, 0)], choir=[CHOIR_A]))
    # P08 자수정 장님어 — E 리디안 102: 어둠 속 수정 공명음, 아주 고요한 시작 → 수정 공명이 화음으로 피어남
    song("P08", "amethyst_blindfish", 64, 102,
         dict(chords=LYD1, base=[part("pad", "hold", 0.24), part("synbass", "bass", 0.36, pattern="x...............")],
              perc=dict(pattern=dict(pulse="x..............."), crisis=dict(pulse="x.......x.......", shaker="..x...x...x...x.")),
              lead=[lead("crystal", pab("P08"), 0.46, 0)], choir=[]),
         dict(chords=LYD2, base=[part("crystal", "hold", 0.3), pad, part("harp", "arp", 0.22, oct=1, pattern="x.x.x.x.x.x.x.x."), pulse_bass], perc=PULSE2,
              lead=[lead("crystal", pba("P08"), 0.42, 0), lead("celesta", pba("P08"), 0.22, 1)], choir=[CHOIR_A]))
    # P09 천공의 나비고기 — C 리디안 132 6/8: 날갯짓 같은 현악 피치카토, 하늘을 나는 플루트 → 하늘이 열리듯 합창과 하프
    wing = "x.xx.xx.xx.x"
    song("P09", "sky_butterfly", 60, 132, meter=(6, 8),
         p1=dict(chords=LYD1, base=[part("pizz", "ostinato", 0.32, pattern=wing), pad, part("synbass", "bass", 0.45, pattern="x.....x.....")],
                 perc=dict(pattern=dict(pulse="x.....x.....", shaker="..x..x..x..x"), crisis=dict(pulse="x..x..x..x..", shaker="xxxxxxxxxxxx")),
                 lead=[lead("flute", pab("P09"), 0.5, 1)], choir=[]),
         p2=dict(chords=LYD2, base=[part("pizz", "ostinato", 0.3, pattern=wing), part("harp", "arp", 0.3, oct=1, pattern="x.x.x.x.x.x."), pad, part("synbass", "bass", 0.45, pattern="x.....x.....")],
                 perc=dict(pattern=dict(pulse="x..x..x..x..", shaker="..x..x..x..x"), crisis=dict(pulse="x.x.x.x.x.x.", shaker="xxxxxxxxxxxx")),
                 lead=[lead("flute", pba("P09"), 0.46, 1), lead("harp", pba("P09"), 0.26, 1)], choir=[CHOIR_A]))
    # P10 잿불 곰치 — F# 리디안 120: 타닥이는 불씨 같은 타악, 따뜻한 합창 → 불씨가 날아오르듯 고음 반짝임
    song("P10", "ember_moray", 54, 120,
         dict(chords=LYD1, base=[part("choir", "hold", 0.32), pad, pulse_bass],
              perc=dict(pattern=dict(crackle="x..x.x..x..x.x..", pulse="x.......x......."), crisis=dict(crackle="xxxxxxxxxxxxxxxx", pulse="x...x...x...x...")),
              lead=[lead("celesta", pab("P10"), 0.44, 1), lead("harp", pab("P10"), 0.2, 1)], choir=[]),
         dict(chords=LYD2, base=[pad, part("glass", "sparkle", 0.22, oct=2, per_bar=8), harp_arp, pulse_bass],
              perc=dict(pattern=dict(crackle="x.xx.xx.x.xx.xx.", pulse="x...x...x...x..."), crisis=dict(crackle="xxxxxxxxxxxxxxxx", pulse="x.x.x.x.x.x.x.x.")),
              lead=[lead("celesta", pba("P10"), 0.42, 1)], choir=[part("choir", "hold", 0.36), CHOIR_A]))
    # P11 오로라 은빙어 — A♭ 리디안 106 3/4: 유리 같은 반짝임, 느린 왈츠 → 왈츠가 커지며 합창
    wb, wc = "x...........", "....x...x..."
    song("P11", "aurora_smelt", 56, 106, meter=(3, 4),
         p1=dict(chords=LYD1, base=[part("synbass", "bass", 0.45, pattern=wb), part("harp", "hits", 0.26, pattern=wc, len=1.5), part("glass", "sparkle", 0.16, oct=1, per_bar=2)],
                 perc=dict(pattern=dict(pulse=wb), crisis=dict(pulse="x...x...x...", shaker="xxxxxxxxxxxx")),
                 lead=[lead("glass", pab("P11"), 0.42, 1)], choir=[]),
         p2=dict(chords=LYD2, base=[part("synbass", "bass", 0.45, pattern=wb), part("strings", "hits", 0.3, pattern=wc, len=2), part("harp", "arp", 0.24, oct=1, pattern="x.x.x.x.x.x."), pad],
                 perc=dict(pattern=dict(pulse=wb, shaker="..x...x...x."), crisis=dict(pulse="x...x...x...", shaker="xxxxxxxxxxxx")),
                 lead=[lead("glass", pba("P11"), 0.4, 1), lead("celesta", pba("P11"), 0.24, 1)], choir=[CHOIR_A]))
    # P12 정령의 꿈잉어 (세계수) — D 리디안 114: P01~P11 동기 조각이 꿈처럼 차례로, 가장 큰 합창 → 모든 동기가 한꺼번에
    dream = sum((pfrag(f"P{i:02d}", 1, i - 1) for i in range(1, 12)), []) + nameless(12) + nameless(14, 0, 1, 1.0)
    stack1 = sum((pfrag(f"P{i:02d}", 1, b) for i, b in ((1, 0), (4, 2), (7, 4), (10, 6), (2, 8), (5, 10), (8, 12), (11, 14))), [])
    stack2 = sum((pfrag(f"P{i:02d}", 2, b) for i, b in ((3, 0), (6, 2), (9, 4), (1, 6), (4, 8), (7, 10), (10, 12), (2, 14))), [])
    song("P12", "dream_carp", 62, 114, reverb=(0.38, 3.8),
         p1=dict(chords=LYD1, base=[pad, harp_arp, part("strings", "hold", 0.28), pulse_bass], perc=PULSE,
                 lead=[lead("celesta", dream, 0.46, 1), lead("flute", dream, 0.22, 1)], choir=[part("choir_a", "hold", 0.34)]),
         p2=dict(chords=LYD2, base=[pad, harp_arp, part("strings", "hold", 0.34), part("glass", "sparkle", 0.2, oct=2, per_bar=6), pulse_bass], perc=PULSE2,
                 lead=[lead("celesta", stack1 + nameless(0) + nameless(8), 0.38, 1), lead("glass", stack2, 0.3, 1), lead("flute", nameless(4) + nameless(12), 0.3, 1),
                       lead("reed", stack2, 0.18, 0)],
                 choir=[part("choir_a", "hold", 0.46), part("choir", "hold", 0.28, oct=-1)]))
    S["P01"]["master"] = {"tp": -2.5}   # 오르골·킥 어택이 OGG 압축 뒤 피크를 1dB 넘게 키움 → 여유 더
    for sid, sp in S.items():
        sp["_설명"] = f"{sid} — BOSS_BGM.md 환상 표 (B4, tools/audio/boss_songs.py 가 씀)"
    return S


PHANTOM_BAN = {"brass", "horn", "trumpet", "roar", "grit"}


def has_nameless_motif(notes) -> bool:
    ns = sorted(([b, at, d, ln] for b, at, d, ln in notes if isinstance(d, int)), key=lambda n: (n[0], n[1]))
    for i in range(len(ns) - 3):
        a, b, c, d = ns[i:i + 4]
        if (a[2] - 1) % 7 == 0 and (b[2] - a[2], c[2] - a[2], d[2] - a[2]) == (3, 4, 2) and \
                abs(b[3] - a[3]) < 1e-6 and abs(c[3] - 2 * a[3]) < 1e-6 and abs(d[3] - 4 * a[3]) < 1e-6:
            return True
    return False


def check_phantom(songs: dict) -> int:
    bad = 0
    for sid, sp in songs.items():
        if sp.get("kind") != "phantom" or sp.get("test"):
            continue
        if sp.get("scale") != "lydian":
            print(sid, "환상인데 리디안 아님"); bad += 1
        if len(sp["phases"]) != 2 or sp["phases"][1].get("transpose") != 2:
            print(sid, "2페이즈·온음 올림 아님"); bad += 1
        insts = {p["inst"] for ph in sp["phases"] for k in ("base", "lead", "choir") for p in ph.get(k, [])}
        if insts & PHANTOM_BAN:
            print(sid, "금관·찌그러진 소리:", insts & PHANTOM_BAN); bad += 1
        if any(k in ("taiko", "snare", "bigdrum", "timp") for ph in sp["phases"] for k in list(ph.get("perc", {}).get("pattern", {})) + list(ph.get("perc", {}).get("crisis", {}))):
            print(sid, "행진 북"); bad += 1
        leads = [l["notes"] for ph in sp["phases"] for l in ph.get("lead", [])]
        if not any(has_nameless_motif(n) for n in leads):
            print(sid, "이름 없는 것의 동기 없음"); bad += 1
        if any(has_owner_motif(n) for n in leads):
            print(sid, "전설의 3음 동기가 들어 있음"); bad += 1
    print("환상 서명 검사:", "ok" if not bad else f"{bad}개 문제")
    return bad


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
        if any(has_nameless_motif(l["notes"]) for p in sp["phases"] for l in p.get("lead", [])):
            print(sid, "전설에 환상의 4음 동기"); bad += 1
        if not motif_ok:
            print(sid, "주인의 동기 없음"); bad += 1
        for i, p in enumerate(sp["phases"]):
            if len(p["chords"]) != 16:
                print(sid, i + 1, "페이즈 화성이 16마디가 아님", len(p["chords"])); bad += 1
    print("서명 검사:", "ok" if not bad else f"{bad}개 문제")
    return bad


# ───────────────────────── 락: 은빛 농어 '일렉트로' (ELECTRO.md, DESIGN.md 43-14) ─────────────────────────
# E단조 168 · 4/4. 일렉 기타 2대 + 베이스 기타 + 드럼 (src/audio/boss_rock.py). 오케스트라 L03 은 남겨 두고 게임은 이 곡을 씀.
RIFF = {"1": "MmmMmmMmMmmM3-4-", "*": "MmmMmmMmMmmMmmp-"}   # 16분 손바닥 뮤트 '둥둥둥둥', 마디 끝 G-A 파워 코드
LICKS = ["{b}:2:5:.5 {b}:2.5:7:.5 {b}:3:8:1",
         "{b}:2:8:.25 {b}:2.25:7:.25 {b}:2.5:5:.25 {b}:2.75:4:.25 {b}:3:5:1",
         "{b}:2.5:3:.5 {b}:3:4:.5 {b}:3.5:5:.5",
         "{b}:2:10:.5 {b}:2.5:8:.5 {b}:3:7:.5 {b}:3.5:8:.5"]
PENT = [1, 3, 4, 5, 7, 8, 10, 11, 12, 14, 15]   # E단조 5음 (+옥타브)


def solo(b0: int, b1: int) -> list:
    """3페이즈 기타 솔로: 4마디마다 (16분 내림 → 큰 벤딩 → 16분 오름 → 벤딩 + 떨기)."""
    out = []
    for b in range(b0, b1):
        k = (b - b0) % 4
        if k == 0:     # 16분 내려오기
            seq = [15, 14, 12, 11, 12, 11, 10, 8, 11, 10, 8, 7, 8, 7, 5, 4]
            out += [[b, i * 0.25, d, 0.25] for i, d in enumerate(seq)]
        elif k == 1:   # 큰 벤딩 2박 + 짧게 두 번
            out += [[b, 0.0, 8, 2.0], [b, 2.0, 10, 0.5], [b, 2.5, 11, 0.5], [b, 3.0, 12, 1.0]]
        elif k == 2:   # 16분 올라가기
            seq = [5, 7, 8, 10, 7, 8, 10, 11, 8, 10, 11, 12, 10, 11, 12, 14]
            out += [[b, i * 0.25, d, 0.25] for i, d in enumerate(seq)]
        else:          # 벤딩 + 떨기 (트릴)
            out += [[b, 0.0, 15, 2.0]] + [[b, 2.0 + i * 0.25, (14, 15)[i % 2], 0.25] for i in range(8)]
    return out


def rock_songs() -> dict:
    base = [part("gtr", "riff", 1.8, riff=RIFF), part("bass_gtr", "bassriff", 0.4, riff=RIFF)]
    licks = []
    for i, b in enumerate((1, 3, 5, 7, 9, 11)):
        licks += mel(LICKS[i % len(LICKS)].format(b=b))
    p1_lead = licks + mel("12:0:8:.5 12:.5:7:.5 12:1:5:.5 12:1.5:4:.5 12:2:5:1 12:3:7:1 13:0:5:2 13:2:4:.5 13:2.5:3:.5 13:3:2:1") \
        + motif(14, 0, 8, 1.0) + mel("15:0:8:4")              # 1페이즈 끝: 주인의 동기 (리드 기타, 크게)
    p3 = motif(0, 0, 8, 2.0) + solo(2, 14) + mel("14:0:12:1 14:1:11:1 14:2:#7:2 15:0:8:4")   # 3페이즈 시작: 동기 크게 → 솔로
    harm = [[b, at, (d + 2) if isinstance(d, int) else "#9", ln] for b, at, d, ln in p3]  # 두 번째 기타: 3도 위
    rock = dict(kind="legend", rock=True, replaces="L03", root=52, scale="minor", bpm=168, meter=[4, 4], fish="silver_bass", reverb=[0.1, 0.7],
                master={"mid_cut_db": -3.0},
                phases=[dict(chords=[1, 1, 6, 7, 1, 1, 6, 7, 1, 1, 4, 4, 6, 7, 1, 1], base=base,
                             lead=[lead("gtr_lead", p1_lead, 0.75, 1)], choir=[]),
                        dict(chords=[1, 1, 6, 6, 3, 3, 7, 7, 1, 1, 6, 6, 4, 4, 5, 5], base=base,
                             lead=[lead("gtr_lead", ab("L03"), 1.0, 1)], choir=[]),
                        dict(chords=[1, 1, 6, 7, 1, 1, 6, 7, 4, 4, 1, 1, 6, 7, 5, 5], base=base,
                             lead=[lead("gtr_lead", p3, 0.8, 1)], choir=[lead("gtr_harm", harm, 0.5, 1, pan=0.45)])])
    return {"L03-ROCK": rock}


# ───────────────────────── 국악 무협: 청새치 '일섬' (ILSEOM.md, DESIGN.md 43-15) ─────────────────────────
# D 계면조(D·F·G·A·C 중심), 1·2페이즈 12/8 점4분 = 100 (엔진 bpm = 4분 150) → 3페이즈 4/4 168. src/audio/boss_muhyeop.py.
# 선율 도수는 D단조로 적되 계면조 다섯 음(1·3·4·5·7)만. 12/8 한 마디 = 4분 6박 (점4분 4개).
IL_P1 = [[0, 0, 1, 1.5], [0, 1.5, 5, 1.5], [0, 3, 4, 3],                       # 주인의 동기 (대금, 점4분·점4분·점2분)
         [1, 0, 3, 1.5], [1, 1.5, 4, .5], [1, 2, 3, 1], [1, 3, 1, 3],
         [2, 0, 5, 1.5], [2, 1.5, 7, 1.5], [2, 3, 8, 3],
         [3, 0, 7, 1], [3, 1, 5, .5], [3, 1.5, 4, 1.5], [3, 3, 5, 3],
         [4, 0, 1, 1.5], [4, 1.5, 5, 1.5], [4, 3, 4, 3],
         [5, 0, 7, 1.5], [5, 1.5, 8, 1.5], [5, 3, 10, 3],
         [6, 0, 8, 1], [6, 1, 7, .5], [6, 1.5, 5, 1.5], [6, 3, 4, 1.5], [6, 4.5, 3, 1.5],
         [7, 0, 1, 6],
         [8, 0, 8, 1.5], [8, 1.5, 12, 1.5], [8, 3, 11, 3],
         [9, 0, 10, 1.5], [9, 1.5, 11, .5], [9, 2, 10, 1], [9, 3, 8, 3],
         [10, 0, 7, 1.5], [10, 1.5, 8, 1.5], [10, 3, 10, 1.5], [10, 4.5, 11, 1.5],
         [11, 0, 12, 6],
         [12, 0, 11, 1], [12, 1, 10, .5], [12, 1.5, 8, 1.5], [12, 3, 7, 1.5], [12, 4.5, 5, 1.5],
         [13, 0, 4, 1.5], [13, 1.5, 5, 1.5], [13, 3, 7, 3],
         [14, 0, 5, 1.5], [14, 1.5, 4, 1.5], [14, 3, 3, 1.5], [14, 4.5, 4, 1.5],
         [15, 0, 1, 6]]
IL_P3 = [[0, 0, 8, 1], [0, 1, 12, 1], [0, 2, 11, 2],                           # 주인의 동기 (태평소, 4/4)
         [1, 0, 10, .5], [1, .5, 11, .5], [1, 1, 12, 1], [1, 2, 11, .5], [1, 2.5, 10, .5], [1, 3, 8, 1],
         [2, 0, 7, .5], [2, .5, 8, .5], [2, 1, 10, 1], [2, 2, 8, 1], [2, 3, 7, 1],
         [3, 0, 8, 4],
         [4, 0, 8, 1], [4, 1, 12, 1], [4, 2, 11, 2],
         [5, 0, 10, .5], [5, .5, 11, .5], [5, 1, 12, 1], [5, 2, 14, 1], [5, 3, 12, 1],
         [6, 0, 11, .5], [6, .5, 10, .5], [6, 1, 8, 1], [6, 2, 7, 1], [6, 3, 5, 1],
         [7, 0, 5, 2], [7, 2, 7, 2],
         [8, 0, 12, 1], [8, 1, 11, .5], [8, 1.5, 10, .5], [8, 2, 11, 2],
         [9, 0, 12, .5], [9, .5, 14, .5], [9, 1, 12, 1], [9, 2, 11, 1], [9, 3, 10, 1],
         [10, 0, 11, .5], [10, .5, 12, .5], [10, 1, 14, 1], [10, 2, 15, 2],
         [11, 0, 12, 4],
         [12, 0, 8, 1], [12, 1, 12, 1], [12, 2, 11, 2],
         [13, 0, 10, .5], [13, .5, 11, .5], [13, 1, 12, 1], [13, 2, 11, .5], [13, 2.5, 10, .5], [13, 3, 8, 1],
         [14, 0, 7, .5], [14, .5, 8, .5], [14, 1, 10, 1], [14, 2, 11, 1], [14, 3, 7, 1],
         [15, 0, 8, 4]]


def muhyeop_songs() -> dict:
    base = [part("gayageum", "gaya", 0.62), part("geomungo", "geomungo", 0.6)]
    p2 = [[b - 8 if b >= 8 else b + 8, at, d, ln] for b, at, d, ln in IL_P1]    # 2페이즈: 둘째 가락부터
    dae2 = [n for n in p2 if (n[0] // 2) % 2 == 0]                              # 대금 ↔ 해금 2마디씩 주고받기
    hae2 = [n for n in p2 if (n[0] // 2) % 2 == 1]
    harm3 = [[b, at, d - 3, ln] for b, at, d, ln in IL_P3]                       # 대금 화음 (4도 아래)
    k12 = dict(daego="x.....x.....", kung="...x.....x..", deok="..x..x..x..x", jing=16)
    k16 = dict(daego="x..x..x.x..x..x.", kung="x...x...x...x...", deok="xxxxxxxxxxxxxxxx", jing=4)
    song = dict(kind="legend", muhyeop=True, replaces="L04", root=62, scale="minor", bpm=150, meter=[12, 8], fish="marlin",
                reverb=[0.15, 1.0], master={"mid_cut_db": -3.0},
                phases=[dict(chords=[1, 1, 3, 1, 4, 4, 5, 1, 1, 7, 3, 4, 5, 5, 1, 1], base=base,
                             perc=dict(pattern=k12, crisis=dict(daego="x.x.x.x.x.x.")),
                             lead=[lead("daegeum", IL_P1, 0.55, 1)], choir=[]),
                        dict(chords=[1, 1, 7, 3, 4, 4, 5, 1, 1, 1, 3, 1, 4, 4, 5, 1], base=base,
                             perc=dict(pattern=dict(k12, clash=True), crisis=dict(daego="x.x.x.x.x.x.")),
                             lead=[lead("daegeum", dae2, 0.55, 1), lead("haegeum", hae2, 0.5, 1, pan=0.2)],
                             choir=[part("haegeum", "hold_hae", 0.45, oct=1, pan=-0.3)]),
                        dict(chords=[1, 1, 7, 7, 3, 3, 4, 5, 1, 1, 7, 3, 4, 4, 5, 1], bpm=168, meter=[4, 4],
                             base=[part("gayageum", "gaya", 0.62), part("geomungo", "geomungo", 0.6)],
                             perc=dict(pattern=k16, crisis=dict(daego="x.x.x.x.x.x.x.x.")),
                             lead=[lead("taepyeongso", IL_P3, 0.72, 1), lead("daegeum", harm3, 0.26, 1, pan=-0.25)],
                             choir=[lead("haegeum", IL_P3, 0.4, 0, pan=0.3)])])
    return {"L04-MUHYEOP": song}


# 전투감 곡 (BOSS_BGM_FIX.md, DESIGN.md 43-13): 빠르기표 + src/audio/boss_battle.py 연주법 (리듬 뼈대 · 소리 정리)
# F2 시범 = L02 · P04. 나머지 22곡은 사용자가 들어 보고 승인한 뒤 (F3)
BATTLE = {"L02": 168, "P04": 160}


def main(argv) -> int:
    songs = legend_songs()
    songs.update(phantom_songs())
    songs.update(rock_songs())
    songs.update(muhyeop_songs())
    for sid, bpm in BATTLE.items():
        songs[sid].update(bpm=bpm, battle=True)
    if check(songs) or check_phantom(songs):
        return 1
    if "--check" in argv:
        return 0
    s = open(PAT, encoding="utf-8").read()
    data = json.loads(s)
    cur = data["boss"]["songs"]
    for k in list(cur):
        if k[:1] in ("L", "P") and k not in songs:
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
