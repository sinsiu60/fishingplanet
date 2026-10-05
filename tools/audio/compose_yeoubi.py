"""황금잉어 '여우비' 전투 곡 — 새 작곡 (음 하나하나를 직접 적은 데이터, DESIGN.md 43-28)

예전 L01-JAZZ 는 공통 연주법 + 다른 전설과 같은 틀의 주선율이라 일섬 · 산군과 선율 모양이 겹쳤다 (유사도 52% · 44%).
이 곡은 처음부터 새로: 능청스러운 '여우' 주제 = 반음으로 기어드는 접근음 · 6도 · 7도 도약 · 당김음 · 블루 노트, 계단식 순차 진행은 피함.

D단조 · 176 · 4/4 스윙 (뒷박 8분 2:1 — 데이터에 스윙된 위치로 적음)
  인트로  1마디  빗소리 → 브러시 '쓰윽' → 금관 '빠-밤!'
  1페이즈 16마디 (좌우로 휘젓기)   약음기 트럼펫 '여우' 주제 + 피아노 찰스턴 + 워킹 베이스 + 브러시
                   화음 Dm7 · Dm7 · E♭maj7#11(반음 위로 슬쩍) · Dm7 · Gm7 · C7♭9 · Fmaj7 · B♭maj7 · Em7♭5 · A7♭13 · Dm7 · B♭7 · Gm7 · A7♭9 · Dm7 · E♭7
                   5마디에 주인의 동기 (D → A → G)
  2페이즈 16마디 (방향 전환 두 번씩)  트럼펫이 2마디 묻고 → 색소폰이 2마디 대답 (두 번씩 주고받기), 2마디마다 화음 둘, 금관 섹션 찌르기
  3페이즈 16마디 (지친 척)  약음기 뺀 트럼펫 + 색소폰 한 옥타브 아래, 금관 섹션이 매 마디 펀치,
                   8 · 16마디 끝 2박은 밴드 전체가 뚝 멈춤(끝난 척) → 다음 첫 박 크래시와 함께 다시 터짐
  위기   킥 강세 셋 + 마디 끝 금관 찌르기 (작곡된 그대로 타악 층에 더함)
  전환   스네어 셋잇단 필인 점점 세게 + 트럼펫 높은 음 '삐이—'
  실패   트롬본 '와와와와—' 축 처지며 반음씩 내려감
사용: python tools/audio/compose_yeoubi.py  →  data/music/yeoubi_notes.json
"""
from notes_compose import Score, m

S = Score("황금잉어 '여우비'", 176)
S.swing_on = True
B = 4                       # 4/4
INTRO = 4
P1, P2, P3, END = INTRO, INTRO + 64, INTRO + 128, INTRO + 192
S.sigs = [(0, "4/4")]
S.markers = [(0, "intro"), (P1, "phase1"), (P2, "phase2"), (P3, "phase3"), (END, "end")]
S.loops = {"phase1": [P1, P2], "phase2": [P2, P3], "phase3": [P3, END]}
S.layers = {"upright": "base", "piano": "base", "rain": "base",
            "trumpet_mute": "lead", "trumpet": "lead", "sax": "lead",
            "sec_tp": "choir", "sec_sx": "choir", "sec_tb": "choir",
            "ride": "perc", "hat": "perc", "kick": "perc", "snare": "perc", "brush": "perc", "brush_tap": "perc", "crash": "perc",
            "stab_tb": "perc", "stab_tp": "perc"}
S.voices = {"upright": "jz_upright", "piano": "jz_piano", "rain": "jz_rain", "trumpet_mute": "jz_trumpet_mute", "trumpet": "jz_trumpet",
            "sax": "jz_sax", "sec_tp": "jz_trumpet", "sec_sx": "jz_sax", "sec_tb": "jz_trombone", "stab_tb": "jz_trombone", "stab_tp": "jz_trumpet",
            "ride": "ride", "hat": "hat", "kick": "kick", "snare": "snare", "brush": "brush", "brush_tap": "brush_tap", "crash": "crash"}
S.gains = {"upright": 0.85, "piano": 0.32, "rain": 0.35, "trumpet_mute": 0.6, "trumpet": 0.5, "sax": 0.42,
           "sec_tp": 0.2, "sec_sx": 0.2, "sec_tb": 0.26, "stab_tb": 0.24, "stab_tp": 0.18,
           "ride": 0.42, "hat": 0.3, "kick": 0.5, "snare": 0.36, "brush": 0.42, "brush_tap": 0.3, "crash": 0.42}
S.pans = {"piano": 0.25, "trumpet_mute": -0.1, "trumpet": -0.1, "sax": 0.25, "sec_tp": -0.35, "sec_sx": 0.35, "sec_tb": 0.0,
          "ride": -0.35, "hat": 0.3, "snare": 0.05, "brush": 0.05, "crash": 0.25}

# ── 화음 (피아노 · 금관 섹션 짜임 = 뿌리음 뺀 3·7·9·13도, 베이스 뿌리음) ──
V = {"Dm7": ["F4", "A4", "C5", "D5"], "Dm9": ["F4", "A4", "C5", "E5"], "Ebmaj7#11": ["G4", "A4", "Bb4", "D5"],
     "Gm7": ["F4", "Bb4", "D5"], "Gm9": ["F4", "A4", "Bb4", "D5"], "C7b9": ["E4", "Bb4", "Db5"], "C13": ["E4", "A4", "Bb4"],
     "C7": ["E4", "Bb4", "D5"], "Fmaj7": ["E4", "F4", "A4", "C5"], "Bbmaj7": ["D4", "F4", "A4", "Bb4"], "Em7b5": ["D4", "E4", "G4", "Bb4"],
     "A7b13": ["C#4", "F4", "G4"], "A7b9": ["C#4", "E4", "G4", "Bb4"], "A7alt": ["C#4", "F4", "G4", "C5"], "Bb7": ["D4", "Ab4", "C5"],
     "Eb7": ["Db4", "F4", "G4"], "G7": ["F4", "B4", "E5"], "G7#9": ["F4", "Bb4", "B4"], "Cm7": ["Eb4", "G4", "Bb4"],
     "F7": ["Eb4", "A4", "C5"], "Eb7#11": ["Db4", "G4", "A4"], "Dm": ["D4", "F4", "A4"]}
ROOT = {"D": "D2", "Eb": "Eb2", "E": "E2", "F": "F2", "G": "G2", "A": "A2", "Bb": "Bb1", "C": "C2"}


def root_of(ch):
    return ROOT[ch[:2] if len(ch) > 1 and ch[1] == "b" else ch[:1]]


def tones_of(ch):
    """워킹 베이스가 밟을 화음음 (뿌리 · 3 · 5 · 7, 베이스 음역)."""
    r = m(root_of(ch))
    third = 3 if "m" in ch[1:3] and "maj" not in ch else 4
    fifth = 6 if "b5" in ch else 7
    seventh = 11 if "maj" in ch else 10
    return [r, r + third, r + fifth, r + seventh]


def walk(start, chords, eighths=False, vel=96):
    """워킹 베이스: [(화음, 박 수)] — 첫 박 뿌리음, 가운데 화음음 · 경과음, 마지막 박은 다음 뿌리음으로 반음 접근 (직접 적은 걷기 규칙)."""
    t = start
    for k, (ch, beats) in enumerate(chords):
        nxt = chords[(k + 1) % len(chords)][0]
        tn = tones_of(ch)
        target = m(root_of(nxt))
        line = [tn[0], tn[1], tn[2], target + (1 if target < tn[2] else -1)] if beats == 4 else [tn[0], target + (-1 if (k % 2) else 1)]
        for j, p in enumerate(line):
            S.add("upright", t + j, 1.0, p, vel - (0 if j == 0 else 12))
            if eighths and j == 2 and beats == 4:   # 셋째 박 뒤 스킵 8분 (스윙)
                S.add("upright", t + j + 0.5, 0.5, p + 12, vel - 30)
        t += beats


def comp(start, chords, rhythm, vel=70, into=None):
    """피아노 찍기: rhythm = 마디 안 [(박, 길이)] — 화음 바뀌면 그 화음."""
    t = start
    for ch, beats in chords:
        for at, ln in rhythm:
            if at < beats:
                for p in V[ch]:
                    S.add("piano", t + at, ln, p, vel, into)
        t += beats


# ── 드럼 (스윙은 이미 적힌 위치: 0.667 = 뒷박 8분) ──
S.swing_on = False
RIDE = [0, 1, 1.667, 2, 3, 3.667]


def drums(start, bars, kick=(), snare=(), brush=False, crash=(), hat=True, fill_last=False, stops=()):
    for b in range(bars):
        t0 = start + b * B
        stop = b in stops
        for r in RIDE:
            if stop and r >= 2:
                continue
            S.add("ride", t0 + r, 0.5, "C4", 90 if r in (1, 3) else 70)
        if hat and not stop:
            for h in (1, 3):
                S.add("hat", t0 + h, 0.3, "C4", 85)
        if brush:
            for h in (1, 3):
                S.add("brush", t0 + h, 0.6, "C4", 80)               # '쓰윽'
            for h in (0.667, 2.667):
                S.add("brush_tap", t0 + h, 0.2, "C3", 50)
        for k in kick:
            if not (stop and k >= 2):
                S.add("kick", t0 + k, 0.4, "C2", 100)
        for s_ in snare:
            if not (stop and s_ >= 2):
                S.add("snare", t0 + s_, 0.3, "C3", 70)
        if b in crash:
            S.add("crash", t0, 2.0, "C4", 110)
        if fill_last and b == bars - 1:   # 마지막 마디 셋잇단 필인
            for j in range(6):
                S.add("snare", t0 + 2 + j / 3, 0.25, "C3", 60 + 8 * j)


# ================================================================ 인트로 (0~4박)
S.add("rain", 0, 4.2, "C4", 100)
S.add("brush", 0.9, 0.9, "C4", 100)                                  # 브러시 '쓰윽'
for p in V["A7b9"]:                                                   # 금관 '빠-밤!'
    S.add("sec_tp", 2.667, 0.25, m(p) + 12, 110); S.add("sec_sx", 2.667, 0.25, p, 105)
    S.add("sec_tp", 3.0, 0.8, m(p) + 12, 120); S.add("sec_sx", 3.0, 0.8, p, 115)
S.add("sec_tb", 2.667, 0.25, "A2", 110); S.add("sec_tb", 3.0, 0.8, "A2", 120)
S.add("kick", 3.0, 0.4, "C2", 110)

# ================================================================ 1페이즈 (능청스러운 '여우' 주제)
CH1 = ["Dm7", "Dm7", "Ebmaj7#11", "Dm7", "Gm7", "C7b9", "Fmaj7", "Bbmaj7", "Em7b5", "A7b13", "Dm7", "Bb7", "Gm7", "A7b9", "Dm7", "Eb7"]
FOX = [  # 약음기 트럼펫 (곧은 박으로 적고 스윙)
    [("r", .5), ("A4", .5), ("Ab4", .5), ("A4", .5), ("r", .5), ("D5", .5), ("F5", 1)],
    [("E5", .5), ("D5", .5), ("r", .5), ("C5", .5), ("A4", 1.5), ("r", .5)],
    [("r", .5), ("G4", .5), ("A4", .5), ("Bb4", .5), ("D5", 1), ("A4", 1)],
    [("r", 1), ("F5", .5), ("E5", .5), ("Eb5", .5), ("D5", .5), ("r", 1)],
    [("D5", 1), ("A5", 1), ("G5", 2)],                                               # 주인의 동기
    [("r", .5), ("E5", .5), ("Db5", .5), ("Bb4", .5), ("G4", 1), ("E4", 1)],
    [("F4", .5), ("A4", .5), ("C5", .5), ("E5", 1.5), ("r", 1)],
    [("r", .5), ("D5", .5), ("A4", .5), ("F4", .5), ("G4", 2)],
    [("r", .5), ("Bb4", .5), ("G4", .5), ("E4", .5), ("D5", 1), ("C5", 1)],
    [("C#5", 1.5), ("F5", .5), ("E5", .5), ("C#5", .5), ("A4", 1)],
    [("r", 1), ("D5", .5), ("F5", .5), ("A5", .5), ("G#5", .5), ("A5", 1)],
    [("Ab5", .5), ("F5", .5), ("D5", .5), ("Bb4", .5), ("C5", 2)],
    [("r", .5), ("Bb4", .5), ("D5", .5), ("F5", .5), ("E5", .5), ("F5", .5), ("G5", 1)],
    [("Bb5", 1), ("A5", .5), ("G5", .5), ("F5", .5), ("E5", .5), ("C#5", 1)],
    [("D5", 2.5), ("r", 1.5)],
    [("r", .5), ("Db5", .5), ("Bb4", .5), ("G4", .5), ("F4", 1), ("A4", 1)]]
S.swing_on = True
for b, bar in enumerate(FOX):
    S.bar_check(bar, B, f"1페이즈 {b + 1}마디")
    S.seq("trumpet_mute", P1 + b * B, bar, 92)
walk(P1, [(c, 4) for c in CH1])
comp(P1, [(c, 4) for c in CH1], [(0, 0.4), (1.5, 0.3)], 68)                          # 찰스턴
S.swing_on = False
drums(P1, 16, kick=(0, 2), brush=True, hat=True, crash=(0,), fill_last=True)

# ================================================================ 2페이즈 (트럼펫 ↔ 색소폰 두 번씩 주고받기)
CH2 = [[("Dm7", 2), ("G7", 2)], [("Dm7", 2), ("G7", 2)], [("Bbmaj7", 4)], [("A7alt", 4)],
       [("Dm7", 2), ("Cm7", 2)], [("F7", 2), ("Bbmaj7", 2)], [("Em7b5", 4)], [("A7b9", 4)],
       [("Gm7", 2), ("C7", 2)], [("Fmaj7", 2), ("Bbmaj7", 2)], [("Em7b5", 2), ("A7b9", 2)], [("Dm7", 4)],
       [("Bb7", 4)], [("A7alt", 4)], [("Dm7", 2), ("Eb7", 2)], [("A7b9", 4)]]
CALL = {  # 마디: (악기, 선율)
    0: ("trumpet_mute", [("F5", .5), ("F5", .5), ("r", .5), ("F5", .5), ("E5", .5), ("D5", .5), ("B4", 1)]),
    1: ("trumpet_mute", [("r", .5), ("A4", .5), ("C5", .5), ("E5", .5), ("G5", 1), ("F5", 1)]),
    2: ("sax", [("D5", 1), ("r", .5), ("Bb4", .5), ("A4", .5), ("F4", .5), ("D4", 1)]),
    3: ("sax", [("r", .5), ("E4", .5), ("F4", .5), ("G4", .5), ("Bb4", .5), ("C#5", .5), ("E5", 1)]),
    4: ("trumpet_mute", [("A5", .5), ("A5", .5), ("G5", .5), ("F5", .5), ("r", .5), ("Eb5", .5), ("D5", 1)]),
    5: ("trumpet_mute", [("r", .5), ("C5", .5), ("Eb5", .5), ("A5", .5), ("Bb5", 1.5), ("r", .5)]),
    6: ("sax", [("Bb4", 1), ("G4", .5), ("E4", .5), ("D4", 1), ("r", 1)]),
    7: ("sax", [("r", .5), ("C#4", .5), ("E4", .5), ("G4", .5), ("Bb4", .5), ("Bb4", .5), ("A4", 1)]),
    8: ("trumpet_mute", [("G5", .5), ("F5", .5), ("D5", .5), ("Bb4", .5), ("E5", .5), ("G5", .5), ("Bb5", 1)]),
    9: ("trumpet_mute", [("A5", 1.5), ("G5", .5), ("F5", 1), ("D5", 1)]),
    10: ("sax", [("Bb4", .5), ("G4", .5), ("E4", .5), ("C#4", .5), ("E4", .5), ("G4", .5), ("Bb4", 1)]),
    11: ("sax", [("A4", 2), ("F4", .5), ("E4", .5), ("D4", 1)]),
    12: ("trumpet_mute", [("Ab5", .5), ("F5", .5), ("D5", .5), ("C5", .5), ("Ab4", 1), ("r", 1)]),
    13: ("trumpet_mute", [("r", .5), ("C#5", .5), ("E5", .5), ("G5", .5), ("Bb5", 1), ("A5", 1)]),
    14: ("sax", [("D4", .5), ("F4", .5), ("A4", .5), ("C5", .5), ("Db5", 1), ("B4", 1)]),
    15: ("sax", [("A4", 3), ("r", 1)])}
S.swing_on = True
for b in range(16):
    inst, bar = CALL[b]
    S.bar_check(bar, B, f"2페이즈 {b + 1}마디")
    S.seq(inst, P2 + b * B, bar, 95)
walk(P2, [c for bar in CH2 for c in bar], eighths=True)
t = P2
for bar in CH2:
    comp(t, bar, [(0, 0.3), (1.5, 0.3)] if len(bar) == 2 else [(0, 0.3), (1.5, 0.3), (3.5, 0.3)], 66)
    t += 4
for b in range(0, 16, 2):   # 금관 섹션 찌르기: 대답이 끝나는 둘째 마디 4박 뒤
    ch = CH2[b + 1][-1][0]
    for p in V[ch]:
        S.add("sec_tp", P2 + (b + 1) * B + 3.5, 0.3, m(p) + 12, 100); S.add("sec_sx", P2 + (b + 1) * B + 3.5, 0.3, p, 95)
    S.add("sec_tb", P2 + (b + 1) * B + 3.5, 0.3, m(root_of(ch)) + 12, 100)
S.swing_on = False
drums(P2, 16, kick=(0, 2.667), snare=(1.667, 3.667), crash=(0, 8), fill_last=True)

# ================================================================ 3페이즈 (빅밴드 전체 + '끝난 척' 2박 멈춤)
CH3 = ["Dm9", "Gm9", "C13", "Fmaj7", "Bbmaj7", "Em7b5", "A7b9", "Dm7", "Dm9", "Eb7#11", "Dm9", "G7#9", "Gm7", "Bb7", "A7alt", "Dm"]
SHOUT = [
    [("D5", 1), ("A5", 1), ("G5", 2)],                                               # 주인의 동기 (크게)
    [("r", .5), ("Bb5", .5), ("A5", .5), ("G5", .5), ("F5", .5), ("D5", .5), ("E5", 1)],
    [("r", .5), ("G5", .5), ("A5", .5), ("Bb5", .5), ("C6", 1.5), ("r", .5)],
    [("A5", .5), ("G5", .5), ("F5", .5), ("E5", .5), ("C5", 2)],
    [("r", 1), ("D5", .5), ("F5", .5), ("A5", 1), ("G5", 1)],
    [("Bb5", 1.5), ("G5", .5), ("E5", 1), ("D5", 1)],
    [("C#5", .5), ("E5", .5), ("G5", .5), ("Bb5", .5), ("A5", .5), ("G5", .5), ("E5", 1)],
    [("D5", 1.5), ("r", 2.5)],                                                       # 끝난 척 (3 · 4박 멈춤)
    [("F5", .5), ("F5", .5), ("A5", .5), ("C6", .5), ("B5", .5), ("Bb5", .5), ("A5", 1)],
    [("G5", .5), ("F5", .5), ("Db5", .5), ("Bb4", .5), ("A4", 1), ("G4", 1)],
    [("r", .5), ("A4", .5), ("D5", .5), ("F5", .5), ("E5", 1.5), ("r", .5)],
    [("F5", .5), ("Bb5", .5), ("B5", 1), ("G5", .5), ("F5", .5), ("D5", 1)],
    [("Bb5", 2), ("A5", .5), ("G5", .5), ("F5", 1)],
    [("Ab5", 1), ("F5", .5), ("D5", .5), ("C5", 1), ("Bb4", 1)],
    [("C#5", .5), ("F5", .5), ("G5", .5), ("C6", .5), ("Bb5", 1), ("A5", 1)],
    [("D6", 1.5), ("r", 2.5)]]                                                       # 끝난 척
STOPS = (7, 15)
S.swing_on = True
for b, bar in enumerate(SHOUT):
    S.bar_check(bar, B, f"3페이즈 {b + 1}마디")
    S.seq("trumpet", P3 + b * B, bar, 88)
    S.seq("sax", P3 + b * B, [(m(p) - 12 if p != "r" else "r", d) for p, d in bar], 70)   # 색소폰 한 옥타브 아래 (같은 선율 두껍게)
for b, ch in enumerate(CH3):
    t0 = P3 + b * B
    S.add("upright", t0, 1.0, root_of(ch), 100)
    S.add("upright", t0 + 1, 1.0, tones_of(ch)[2], 88)
    if b not in STOPS:
        S.add("upright", t0 + 2, 1.0, tones_of(ch)[1] + 12, 86)
        S.add("upright", t0 + 3, 1.0, m(root_of(CH3[(b + 1) % 16])) - 1, 84)
    for at, ln in ([(0, 0.3), (1.5, 0.3)] if b in STOPS else [(0, 0.3), (1.5, 0.3), (2.5, 0.3)]):
        for p in V[ch]:
            S.add("piano", t0 + at, ln, p, 74)
    punches = [(0, 0.5), (1.5, 0.3)] if b in STOPS else [(0, 0.5), (1.5, 0.3), (3.5, 0.4)]
    for at, ln in punches:                                                           # 금관 섹션 펀치
        for p in V[ch]:
            S.add("sec_tp", t0 + at, ln, m(p) + 12, 108); S.add("sec_sx", t0 + at, ln, p, 100)
        S.add("sec_tb", t0 + at, ln, m(root_of(ch)) + 12, 104)
S.swing_on = False
drums(P3, 16, kick=(0, 1.667, 2.667), snare=(1, 3, 3.667), crash=(0, 4, 8, 12), stops=STOPS)

# ================================================================ 위기 (타악 층에 더함 — 작곡된 그대로)
for name, (a, b) in S.loops.items():
    lst = S.crisis.setdefault(name, [])
    for k in range(16):
        t0 = k * B
        if name == "phase3" and k in STOPS:
            continue
        for at in (0, 1.667, 2.667):
            S.add("kick", t0 + at, 0.4, "C2", 115, into=lst)
        S.add("stab_tb", t0 + 3.667, 0.3, "D3", 110, into=lst)
        S.add("stab_tp", t0 + 3.667, 0.3, "A5", 105, into=lst)

# ================================================================ 전환 (드럼 필인 + 트럼펫 높은 음 '삐이—')
for k in ("1", "2"):
    notes = []
    for j in range(12):
        S.add("snare", j / 3, 0.25, "C3", 50 + 6 * j, into=notes)
    S.add("kick", 0, 0.4, "C2", 100, into=notes); S.add("kick", 2, 0.4, "C2", 100, into=notes)
    S.add("trumpet", 0.5, 3.4, "A5" if k == "1" else "D6", 110, into=notes)
    S.add("crash", 3.667, 0.3, "C4", 70, into=notes)
    S.transitions[k] = {"beats": 4, "notes": notes}

# ================================================================ 실패 (트롬본 '와와와와—')
notes = []
for j, p in enumerate(["D3", "Db3", "C3", "B2"]):
    S.add("sec_tb", j * 0.75, 0.7 if j < 3 else 2.2, p, 110 - 8 * j, into=notes)
S.voices["fail_tb"] = "jz_trombone_wah"
for n in notes:
    n["track"] = "fail_tb"
S.layers["fail_tb"] = "choir"
S.gains["fail_tb"] = 0.6
S.fail = {"beats": 5, "notes": notes}

S.ornament({"trumpet", "sax"}, "C C# D D# E F F# G G# A A# B".split(), P1, END, side=-1, min_dur=1.0, grace=0.12, every=2)   # 스쿱: 긴 음 둘 중 하나는 반음 아래에서 밀어 올림
S.save("yeoubi")
