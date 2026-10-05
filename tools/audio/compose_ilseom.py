"""청새치 '일섬' 전투 곡 — 새 작곡 (음 하나하나를 직접 적은 데이터, DESIGN.md 43-28)

예전 L04-MUHYEOP 은 공통 연주법 + 다른 전설과 같은 틀의 주선율이라 여우비 · 산군과 모양이 겹쳤다 (유사도 52% · 49%).
이 곡은 처음부터 새로: 계면조 느낌의 D단조(D F G A C + 꺾는 E♭), 길게 뻗다 떨어지는 소리, 옥타브 도약, 점4분 3박 자리의 긴 음,
끝에서 위로 치켜 올렸다 내려앉는 꼬리 — 계단식 순차 진행은 줄임.

D단조 · 1·2페이즈 12/8 (점4분 = 100, 4분 = 150) → 3페이즈 4/4 · 168
  인트로  1마디(12/8)  넓은 바다 바람 → 칼 뽑는 '스릉—'
  1페이즈 16마디 (먼바다 질주)  대금 주선율 + 가야금 · 거문고 + 장구 굿거리풍 + 대고 · 4마디마다 징, 1마디 주인의 동기 (D → A → G)
  2페이즈 16마디 (방향 전환)   대금 ↔ 해금 2마디씩 주고받기, 4마디마다 칼 부딪침 '챙'
  3페이즈 16마디 (일섬)  4/4 · 168 로 바뀌며 태평소가 앞에 + 대금이 한 옥타브 아래 같이, 장구 휘모리 16분, 대고 · 징
  위기   대고 8분 몰아치기 + 해금 떨림 (작곡된 그대로)
  전환   징 + 장구 덕 16분 점점 세게 + 끝 대고 (2→3 은 4/4 · 168 로)
  실패   칼이 부러지는 '쨍' → 징 여운
사용: python tools/audio/compose_ilseom.py  →  data/music/ilseom_notes.json
"""
from notes_compose import Score, m

S = Score("청새치 '일섬'", 150)
B12, B4 = 6, 4                       # 12/8 한 마디 = 4분 6박, 4/4 = 4박
INTRO = B12
P1 = INTRO
P2 = P1 + 16 * B12
P3 = P2 + 16 * B12
END = P3 + 16 * B4
S.sigs = [(0, "12/8"), (P3, "4/4")]
S.tempos = [(0, 150), (P3, 168)]
S.markers = [(0, "intro"), (P1, "phase1"), (P2, "phase2"), (P3, "phase3"), (END, "end")]
S.loops = {"phase1": [P1, P2], "phase2": [P2, P3], "phase3": [P3, END]}
S.layers = {"gayageum": "base", "geomungo": "base", "wind": "base", "daegeum": "lead", "haegeum": "lead", "taepyeongso": "lead",
            "daegeum2": "choir", "haegeum_hold": "choir",
            "daego": "perc", "kung": "perc", "deok": "perc", "jing": "perc", "chaeng": "perc", "seureung": "perc",
            "c_daego": "perc", "c_trem": "perc"}
S.voices = {"gayageum": "kr_gayageum", "geomungo": "kr_geomungo", "wind": "kr_wind", "daegeum": "kr_daegeum", "haegeum": "kr_haegeum",
            "taepyeongso": "kr_taepyeongso", "daegeum2": "kr_daegeum", "haegeum_hold": "kr_haegeum", "daego": "daego", "kung": "kung",
            "deok": "deok", "jing": "jing", "chaeng": "kr_chaeng", "seureung": "kr_seureung", "c_daego": "daego", "c_trem": "kr_haegeum_trem",
            "jjaeng": "kr_jjaeng"}
S.gains = {"gayageum": 0.55, "geomungo": 0.55, "wind": 0.45, "daegeum": 0.6, "haegeum": 0.5, "taepyeongso": 0.62, "daegeum2": 0.3,
           "haegeum_hold": 0.3, "daego": 0.95, "kung": 0.55, "deok": 0.38, "jing": 0.42, "chaeng": 0.5, "seureung": 1.2,
           "c_daego": 0.75, "c_trem": 0.25, "jjaeng": 1.0}
S.pans = {"gayageum": -0.3, "geomungo": 0.2, "haegeum": 0.25, "daegeum2": -0.25, "haegeum_hold": 0.3, "kung": -0.2, "deok": 0.25,
          "chaeng": 0.35, "c_trem": 0.35}
S.rings = {"jing": 0.0, "seureung": 0.2, "chaeng": 0.4, "jjaeng": 0.5}


def strings(start, roots, bar, pat12=True, vel=86):
    """가야금 8분 뜯기 (뿌리 · 5도 · 옥타브 오르내림) + 거문고 낮은 뿌리음 (점4분 1 · 3 자리 / 4/4 는 1 · 3박)."""
    shape = [0, 7, 12, 7, 0, 5, 12, 5, 0, 7, 10, 12] if pat12 else [0, 7, 12, 7, 0, 7, 10, 12]
    for b, r in enumerate(roots):
        rt = m(f"{r}4") if r in ("C", "D") else m(f"{r}3")
        t0 = start + b * bar
        for i, iv in enumerate(shape):
            S.add("gayageum", t0 + i * 0.5, 0.9, rt + iv, vel if i % (3 if pat12 else 2) == 0 else vel - 18)
        for k in ((0, 3) if pat12 else (0, 2)):
            S.add("geomungo", t0 + k, 1.4, rt - 12, vel + 6)


def janggu12(start, bars, daego=(0,), jing_every=4, vel=100):
    """12/8 굿거리풍: 덩(궁+채) . 기덕 쿵 . 덕 / 덩 . 기덕 쿵 . 덕 — 8분 자리."""
    for b in range(bars):
        t0 = start + b * B12
        for e in (0, 6):
            S.add("kung", t0 + e * 0.5, 0.4, "C3", vel)
        for e in (0, 2, 3, 5, 6, 8, 9, 11):
            S.add("deok", t0 + e * 0.5, 0.2, "C4", vel - (0 if e in (0, 6) else 25))
        for e in (4, 10):
            S.add("kung", t0 + e * 0.5, 0.4, "C3", vel - 20)
        for k in daego:
            S.add("daego", t0 + k, 0.8, "C2", 110)
        if b % jing_every == 0:
            S.add("jing", t0, 3.0, "C3", 100)


# ================================================================ 인트로 (12/8 한 마디)
S.add("wind", 0, 6.2, "C4", 100)
S.add("seureung", 3.5, 2.0, "C4", 110)

# ================================================================ 1페이즈 (대금)
R1 = ["D", "D", "G", "D", "F", "C", "G", "D", "D", "A", "F", "C", "A", "D", "C", "D"]
M1 = [
    [("D5", 1.5), ("A5", 1.5), ("G5", 3)],                                           # 주인의 동기 (점4분 · 점4분 · 점2분)
    [("F5", 1), ("G5", .5), ("A5", 1.5), ("C6", 1.5), ("A5", 1.5)],
    [("G5", 3), ("F5", .5), ("Eb5", .5), ("D5", 2)],                                  # 꺾는 음 E♭
    [("r", 1.5), ("A4", 1), ("C5", .5), ("D5", 3)],
    [("F5", 1.5), ("D5", .5), ("F5", .5), ("G5", .5), ("A5", 3)],
    [("C6", 1), ("A5", .5), ("G5", 1.5), ("F5", 1.5), ("D5", 1.5)],
    [("G5", 1.5), ("A5", .5), ("G5", .5), ("F5", .5), ("D5", 1.5), ("C5", 1.5)],
    [("D5", 4.5), ("r", 1.5)],
    [("A5", 1.5), ("D6", 1.5), ("C6", 1), ("A5", .5), ("G5", 1.5)],
    [("A5", 3), ("G5", .5), ("F5", .5), ("D5", 2)],
    [("F5", 1), ("G5", .5), ("A5", 1), ("C6", .5), ("D6", 3)],
    [("C6", 1.5), ("A5", 1.5), ("G5", 1), ("F5", .5), ("G5", 1.5)],
    [("A5", 4.5), ("G5", .5), ("F5", 1)],
    [("D5", 1.5), ("F5", 1.5), ("Eb5", .5), ("D5", 2.5)],
    [("C5", 1.5), ("D5", .5), ("F5", 1), ("G5", 1.5), ("A5", 1.5)],
    [("D5", 4.5), ("r", 1.5)]]
for b, bar in enumerate(M1):
    S.bar_check(bar, B12, f"1페이즈 {b + 1}마디")
    S.seq("daegeum", P1 + b * B12, bar, 82)
strings(P1, R1, B12)
janggu12(P1, 16)

# ================================================================ 2페이즈 (대금 ↔ 해금 2마디씩)
R2 = ["D", "F", "A", "D", "C", "D", "G", "G", "F", "G", "D", "D", "F", "A", "D", "D"]
M2 = [
    ("daegeum", [("D6", 1), ("C6", .5), ("A5", 1), ("G5", .5), ("A5", 1.5), ("D5", 1.5)]),
    ("daegeum", [("F5", .5), ("G5", .5), ("A5", .5), ("C6", 1.5), ("A5", 3)]),
    ("haegeum", [("A4", 1.5), ("D5", 1.5), ("C5", 1), ("A4", .5), ("G4", 1.5)]),
    ("haegeum", [("F4", 1), ("G4", .5), ("A4", 3), ("r", 1.5)]),
    ("daegeum", [("C6", 1.5), ("D6", 1.5), ("F6", 1), ("D6", .5), ("C6", 1.5)]),
    ("daegeum", [("A5", 1.5), ("G5", .5), ("Eb5", .5), ("D5", 3.5)]),
    ("haegeum", [("G4", 1), ("A4", .5), ("C5", 1.5), ("D5", 1), ("C5", .5), ("A4", 1.5)]),
    ("haegeum", [("G4", 4.5), ("r", 1.5)]),
    ("daegeum", [("F5", 1.5), ("C6", 1.5), ("A5", 3)]),
    ("daegeum", [("G5", 1), ("F5", .5), ("D5", 1.5), ("F5", 1), ("G5", .5), ("A5", 1.5)]),
    ("haegeum", [("D5", 1.5), ("F5", 1), ("G5", .5), ("A5", 1.5), ("G5", 1.5)]),
    ("haegeum", [("F5", 1), ("Eb5", .5), ("D5", 4.5)]),
    ("daegeum", [("A5", .5), ("C6", .5), ("D6", .5), ("F6", 1.5), ("D6", 1.5), ("C6", 1.5)]),
    ("daegeum", [("A5", 3), ("G5", 1.5), ("A5", 1.5)]),
    ("haegeum", [("D5", 1), ("C5", .5), ("A4", 1.5), ("C5", 1), ("D5", .5), ("F5", 1.5)]),
    ("haegeum", [("D5", 4.5), ("r", 1.5)])]
for b, (inst, bar) in enumerate(M2):
    S.bar_check(bar, B12, f"2페이즈 {b + 1}마디")
    S.seq(inst, P2 + b * B12, bar, 98)
for b in range(0, 16, 2):   # 해금이 쉬는 동안 낮게 받치는 긴 음 (합창 자리)
    S.add("haegeum_hold", P2 + b * B12, B12 * 1.9, m(f"{R2[b]}4"), 70)
strings(P2, R2, B12, vel=92)
janggu12(P2, 16, daego=(0, 3))
for b in range(0, 16, 4):
    S.add("chaeng", P2 + b * B12, 0.5, "C4", 110)

# ================================================================ 3페이즈 (4/4 · 168, 태평소)
R3 = ["D", "F", "D", "A", "F", "D", "C", "D", "A", "F", "D", "A", "G", "F", "D", "D"]
M3 = [
    [("D5", 1), ("A5", 1), ("G5", 2)],                                              # 주인의 동기 (태평소)
    [("F5", .5), ("G5", .5), ("A5", 1), ("C6", 1.5), ("A5", .5)],
    [("D6", 2), ("C6", .5), ("A5", .5), ("G5", 1)],
    [("A5", 3), ("r", 1)],
    [("F5", .75), ("G5", .25), ("A5", .5), ("C6", .5), ("D6", 1), ("C6", 1)],
    [("A5", 1), ("G5", .5), ("F5", .5), ("Eb5", .5), ("D5", 1.5)],
    [("C5", .5), ("F5", .5), ("D5", 1), ("G5", .5), ("A5", .5), ("C6", 1)],
    [("D6", 3), ("r", 1)],
    [("A5", .5), ("D6", .5), ("C6", .5), ("A5", .5), ("G5", 1), ("A5", 1)],
    [("F5", 1.5), ("G5", .5), ("D5", 2)],
    [("D6", 1), ("F6", 1), ("D6", 1), ("C6", 1)],
    [("A5", 3), ("r", 1)],
    [("G5", .5), ("A5", .5), ("C6", 1), ("A5", .5), ("G5", .5), ("F5", 1)],
    [("D5", .5), ("F5", .5), ("G5", 1), ("A5", 2)],
    [("C6", 1), ("A5", .5), ("G5", .5), ("F5", .5), ("Eb5", .5), ("D5", 1)],
    [("D5", 3), ("r", 1)]]
for b, bar in enumerate(M3):
    S.bar_check(bar, B4, f"3페이즈 {b + 1}마디")
    S.seq("taepyeongso", P3 + b * B4, bar, 110)
    S.seq("daegeum2", P3 + b * B4, [(m(p) - 12 if p != "r" else "r", d) for p, d in bar], 80)   # 대금이 한 옥타브 아래 같이
strings(P3, R3, B4, pat12=False, vel=96)
for b in range(16):                                                                 # 장구 휘모리 16분 + 대고 · 징
    t0 = P3 + b * B4
    for i in range(16):
        S.add("deok", t0 + i * 0.25, 0.15, "C4", 96 if i % 4 == 0 else 62)
    for k in (0, 1.5, 2, 3):
        S.add("kung", t0 + k, 0.4, "C3", 100)
    for k in (0, 2):
        S.add("daego", t0 + k, 0.8, "C2", 115)
    if b % 4 == 0:
        S.add("jing", t0, 3.0, "C3", 105)

# ================================================================ 위기 (대고 8분 + 해금 떨림)
for name, (a, b) in S.loops.items():
    lst = S.crisis.setdefault(name, [])
    span = b - a
    t = 0.0
    while t < span - 1e-6:
        S.add("c_daego", t, 0.4, "C2", 100 if int(round(t * 2)) % 2 == 0 else 78, into=lst)
        t += 0.5
    bar = B4 if name == "phase3" else B12
    for k in range(16):
        S.add("c_trem", k * bar, bar * 0.95, "D5", 80, into=lst)

# ================================================================ 전환 (징 + 장구 덕 몰아치기 + 끝 대고)
for k, beats in (("1", B12), ("2", B4)):
    notes = []
    S.add("jing", 0, 3.0, "C3", 110, into=notes)
    n16 = int(beats * 4)
    for i in range(n16 - 1):
        S.add("deok", i * 0.25, 0.15, "C4", 50 + int(60 * i / n16), into=notes)
        if i % 4 == 0:
            S.add("kung", i * 0.25, 0.4, "C3", 70 + int(40 * i / n16), into=notes)
    S.add("daego", beats - 0.5, 0.5, "C2", 110, into=notes)
    S.transitions[k] = {"beats": beats, "notes": notes}

# ================================================================ 실패 (칼이 부러지는 '쨍' → 징 여운)
S.layers["jjaeng"] = "perc"
notes = []
S.add("jjaeng", 0, 1.2, "C4", 120, into=notes)
S.add("jing", 0.3, 3.5, "C3", 100, into=notes)
S.fail = {"beats": 5, "notes": notes}

S.ornament({"daegeum", "haegeum", "taepyeongso", "daegeum2"}, "DFGAC", P1, END, side=1)   # 시김새: 긴 음은 위 이웃음에서 꺾어 내려 들어감
S.save("ilseom")
