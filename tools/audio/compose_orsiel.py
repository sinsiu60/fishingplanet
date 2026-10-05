"""
천해왕 오르시엘 전용 파이팅 곡 — 음 하나하나를 직접 적은 작곡 데이터
다른 곡의 패턴을 바꿔 쓰는 방식이 아니라, 이 파일의 음표가 곧 악보입니다.

구성 (138 BPM)
  인트로   2마디  4/4   심해의 정적, 고래 울음, 거대한 종
  1페이즈 16마디  4/4   C 프리지안: 반음 긴장 오스티나토 위 호른 주제 A
  2페이즈 16마디  7/8   변박(2+2+3)으로 숨 막히는 긴장, 불협 합창, 트럼펫 찌르기
  3페이즈 16마디  4/4   반음씩 기어오르는 베이스 vs 내려오는 주제 A(2배로 늘림), 딸림음 위 합창 주제 B
  4페이즈 16마디  4/4   C 장조로 바뀌며 해방, 주제 A의 장조 변형 + 주인의 동기 1회

출력: orsiel_theme.mid, orsiel_notes.json, orsiel_preview.wav (구조 확인용 간이 합성)
"""
import os, json
import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, sosfilt, fftconvolve

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(_ROOT, "data", "music")                                    # 작곡 데이터 (게임이 이 json 을 그대로 연주)
OUT_PREVIEW = os.path.join(_ROOT, "tools", "audio", "reference", "boss_bgm")  # 구조 확인용 간이 미리듣기
BPM = 138
SPB = 60 / BPM  # 4분음표 1박 = 초

NOTE = {"C": 0, "C#": 1, "Db": 1, "D": 2, "D#": 3, "Eb": 3, "E": 4, "F": 5, "F#": 6, "Gb": 6,
        "G": 7, "G#": 8, "Ab": 8, "A": 9, "A#": 10, "Bb": 10, "B": 11}


def m(name):
    """'Ab4' → MIDI 번호"""
    p, o = (name[:2], name[2:]) if len(name) > 2 and name[1] in "b#" else (name[:1], name[1:])
    return 12 * (int(o) + 1) + NOTE[p]


notes = []      # (트랙, 시작 박, 길이 박, 음높이, 세기)
markers = []    # (박, 이름)


def add(track, start, dur, pitch, vel=96):
    notes.append((track, float(start), float(dur), m(pitch) if isinstance(pitch, str) else int(pitch), int(vel)))


def seq(track, start, items, vel=96):
    """items = [(음 또는 None(쉼표), 길이)] 를 이어서 배치, 끝 박 반환"""
    t = start
    for p, dur in items:
        if p is not None:
            if isinstance(p, (list, tuple)):
                for q in p:
                    add(track, t, dur, q, vel)
            else:
                add(track, t, dur, p, vel)
        t += dur
    return t


# ================================================================ 인트로 (0~8박)
markers.append((0, "intro"))
add("bass", 0, 8, "C1", 110); add("bass", 0, 8, "C2", 90)
add("bell", 0, 8, "C2", 120)                         # 천해의 종
add("whale", 0.5, 6, "G2", 80)                       # 고래 울음 (미끄러지는 낮은 소리)
for b, v in [(0, 120), (3, 90), (4, 120), (6, 95), (6.5, 100), (7, 105), (7.25, 110), (7.5, 115), (7.75, 127)]:
    add("taiko", b, 0.5, "C2", v)
add("riser", 4, 4, "C4", 100)

# ================================================================ 1페이즈 (8~72박)
P1 = 8
markers.append((P1, "phase1"))
roots1 = ["C", "Ab", "F", "G"]                        # 4마디씩
bass_oct = {"C": "C2", "Ab": "Ab1", "F": "F1", "G": "G1"}
for i, r in enumerate(roots1):
    for bar in range(4):
        t = P1 + (i * 4 + bar) * 4
        b = bass_oct[r]
        add("bass", t, 2, b, 104); add("bass", t + 2, 1.5, b, 96)
        add("bass", t + 3.5, 0.5, m(b) + 12, 100)
        # 현악 16분음표 오스티나토: 근음 · 근음 · 반음 위 · 근음 · 5도 · 근음 · 반음 위 · 근음 (×2)
        root3 = m((r if r != "G" else "G") + ("3" if r in ("C", "Ab", "G") else "3"))
        third_g = r == "G"
        pat = [0, 0, 1, 0, 7, 0, 1, 0]
        if third_g:
            pat = [0, 0, 1, 0, 4, 0, 1, 0]            # G에서는 장3도(B)로 딸림 긴장
        for k in range(16):
            add("strings", t + k * 0.25, 0.25, root3 + pat[k % 8], 88 if k % 4 == 0 else 72)
        add("timpani", t, 1, m(b) + 12, 110 if bar == 0 else 85)
        if i >= 2:
            add("lowbrass", t, 4, m(b) + 12, 92); add("lowbrass", t, 4, m(b) + 19, 84)
    if i in (0, 2):
        add("bell", P1 + i * 16, 8, "C2", 100)
# 호른 주제 A (5~16마디)
tA = P1 + 4 * 4
tA = seq("horn", tA, [("Eb5", 2), ("C5", 1), ("Db5", 1), ("C5", 2), ("Ab4", 2), ("Bb4", 3), ("Ab4", 1), ("G4", 4)], 100)
tA = seq("horn", tA, [("Ab4", 2), ("F4", 1), ("G4", 1), ("Ab4", 2), ("C5", 2), ("Db5", 3), ("C5", 1), ("Bb4", 2), ("Ab4", 2)], 104)
tA = seq("horn", tA, [("G4", 4), ("B4", 2), ("D5", 2), ("F5", 3), ("Eb5", 1), ("D5", 2), ("B4", 2)], 110)
for k in range(16):                                   # 16마디 팀파니 롤
    add("timpani", P1 + 15 * 4 + k * 0.25, 0.25, "G2", 70 + k * 3)

# ================================================================ 2페이즈 7/8 (72~128박)
P2 = P1 + 64
markers.append((P2, "phase2"))
BAR7 = 3.5
roots2 = ["C", "Db", "C", "Bb", "Ab", "G", "Ab", "G"]  # 2마디씩
low = {"C": "C2", "Db": "Db2", "Bb": "Bb1", "Ab": "Ab1", "G": "G1"}
for i, r in enumerate(roots2):
    for bar in range(2):
        t = P2 + (i * 2 + bar) * BAR7
        b = m(low[r])
        for e, d, off in [(0, 1, 0), (1, 1, 12), (2, 1.5, 0)]:       # 2+2+3 묶음
            add("bass", t + e, d, b + off, 108)
            add("taiko", t + e, 0.5, "C2", 120 if e == 0 else 95)
        for k in range(7):                                              # 8분음표 똑딱 (긴장)
            add("tick", t + k * 0.5, 0.25, "C6", 70)
        third = 4 if r == "G" else (4 if r in ("Db", "Ab", "Bb") else 3)
        if r == "Bb":
            third = 3
        for q in (0, third, 7):                                         # 현악 트레몰로 화음
            add("strings_trem", t, BAR7, b + 24 + q, 76)
        if i >= 2:                                                      # 트럼펫 찌르기
            for e in (0, 1, 2):
                for q in (0, third, 7):
                    add("trumpet", t + e, 0.25, b + 36 + q, 112)
        if i >= 4:                                                      # 불협 합창 (반음 겹침)
            for q in (0, 1, 3):
                add("choir", t, BAR7, b + 36 + q, 70 + (i - 4) * 8)
# 주제 A 조각 (호른)
seq("horn", P2 + 2 * BAR7, [("G4", 1), ("Ab4", 0.5), ("G4", 2)], 104)
seq("horn", P2 + 6 * BAR7, [("Ab4", 1), ("Bb4", 0.5), ("Ab4", 2)], 108)
seq("horn", P2 + 10 * BAR7, [("C5", 1), ("Db5", 0.5), ("C5", 2)], 112)
seq("horn", P2 + 14 * BAR7, [("D5", 1), ("Eb5", 0.5), ("D5", 1), ("B4", 1), ("G4", 0.5)], 118)
for k in range(14):                                   # 16마디 스네어 롤
    add("snare", P2 + 15 * BAR7 + k * 0.25, 0.25, "D2", 70 + k * 4)
add("whale", P2 + 8 * BAR7, 6, "Ab2", 85)

# ================================================================ 3페이즈 (128~192박)
P3 = P2 + 16 * BAR7
markers.append((P3, "phase3"))
chrom = ["C", "C#", "D", "Eb", "E", "F", "F#", "G"]
for i, r in enumerate(chrom):                          # 반음씩 오르는 베이스 (1~8마디)
    t = P3 + i * 4
    add("bass", t, 4, r + "1", 115); add("bass", t, 4, r + "2", 100)
    add("lowbrass", t, 4, r + "2", 90)
    add("kick", t, 1, "C1", 120); add("taiko", t + 2, 1, "C2", 125)   # 반박자 느낌의 묵직한 박
for i in range(8):                                     # 9~16마디 딸림음 G 페달
    t = P3 + (8 + i) * 4
    add("bass", t, 4, "G1", 115); add("bass", t, 4, "G2", 100)
    for k in range(16):
        add("strings", t + k * 0.25, 0.25, m("G3") + [0, 1, 0, -1][k % 4], 90 if k % 4 == 0 else 74)
    add("kick", t, 1, "C1", 120); add("taiko", t + 2, 1, "C2", 125)
    if i >= 4:
        for k in range(8):
            add("taiko", t + k * 0.5, 0.5, "C2", 90 + i * 5)
# 주제 A를 2배로 늘려 낮은 금관이 내려옴 (오르는 베이스와 반대 방향)
seq("lowbrass", P3, [("G3", 4), ("Ab3", 2), ("G3", 2), ("F3", 4), ("Eb3", 4), ("Db3", 4), ("Db3", 2), ("C3", 2), ("C3", 8)], 112)
seq("horn", P3, [("G4", 4), ("Ab4", 2), ("G4", 2), ("F4", 4), ("Eb4", 4), ("Db4", 4), ("Db4", 2), ("C4", 2), ("C4", 8)], 104)
# 합창 주제 B (9~16마디)
seq("choir", P3 + 32, [("D5", 4), ("Eb5", 4), ("F5", 2), ("G5", 2), ("Ab5", 4), ("G5", 4), ("F5", 2), ("Eb5", 2), ("D5", 4), ("B4", 4)], 105)
add("bell", P3, 8, "C2", 120); add("bell", P3 + 32, 8, "G1", 120)
add("riser", P3 + 56, 8, "C4", 115)
add("crash", P3 + 64 - 0.01, 0.01, "C#3", 1)

# ================================================================ 4페이즈 C 장조 (192~256박)
P4 = P3 + 64
markers.append((P4, "phase4"))
prog = [("C", "C2", [0, 4, 7]), ("G/B", "B1", [7, 11, 14]), ("Am", "A1", [9, 12, 16]), ("F", "F1", [5, 9, 12]),
        ("C/G", "G1", [0, 4, 7]), ("G", "G1", [7, 11, 14]), ("F", "F1", [5, 9, 12]), ("G", "G1", [7, 11, 14])]
for i, (name, bass, chord) in enumerate(prog):
    t = P4 + i * 8
    add("bass", t, 8, bass, 110); add("bass", t, 8, m(bass) + 12, 95)
    for q in chord:
        add("choir", t, 8, m("C4") + q, 92)
    for k in range(16):                                 # 현악 8분음표 상승 아르페지오
        add("strings", t + k * 0.5, 0.5, m("C4") + chord[k % 3] + (12 if (k // 3) % 2 else 0), 84)
    add("timpani", t, 1, m(bass) + 12, 115); add("timpani", t + 4, 1, m(bass) + 12, 100)
    add("kick", t, 1, "C1", 110); add("kick", t + 4, 1, "C1", 105)
add("crash", P4, 0.01, "C#3", 1); add("crash", P4 + 32, 0.01, "C#3", 1)
melody4 = [("G4", 2), ("A4", 1), ("G4", 1), ("E5", 4), ("D5", 2), ("C5", 1), ("D5", 1), ("E5", 4),
           ("C5", 2), ("B4", 1), ("A4", 1), ("F5", 4), ("E5", 2), ("D5", 2), ("D5", 4),
           ("C5", 2), ("D5", 1), ("E5", 1), ("G5", 4), ("E5", 2), ("C5", 2), ("D5", 4),
           ("C5", 2), ("A4", 2), ("F5", 3), ("E5", 1),
           ("C5", 1), ("G5", 1), ("F5", 2), ("D5", 2), ("B4", 2)]          # 마지막 2마디: 주인의 동기 1회
seq("horn", P4, melody4, 112)
seq("trumpet", P4 + 32, [(p, d) for p, d in melody4[15:]], 100)
END = P4 + 64
markers.append((END, "end"))

# ================================================================ 저장: JSON
json.dump({"title": "천해왕 오르시엘", "bpm": BPM,
           "time_signatures": [{"beat": 0, "sig": "4/4"}, {"beat": P2, "sig": "7/8"}, {"beat": P3, "sig": "4/4"}],
           "markers": [{"beat": b, "name": n} for b, n in markers],
           "loops": {"phase1": [P1, P2], "phase2": [P2, P3], "phase3": [P3, P4], "phase4": [P4, END]},
           "notes": [{"track": tr, "start": s, "dur": du, "pitch": p, "vel": v} for tr, s, du, p, v in notes]},
          open(os.path.join(OUT, "orsiel_notes.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)

# ================================================================ 저장: MIDI
import mido
TPB = 480
mid = mido.MidiFile(ticks_per_beat=TPB)
tracks = sorted(set(n[0] for n in notes))
GM = {"bass": 33, "strings": 48, "strings_trem": 44, "horn": 60, "lowbrass": 57, "trumpet": 56, "choir": 52,
      "bell": 14, "whale": 89, "riser": 92}
DRUM = {"taiko": 36, "timpani": None, "kick": 35, "snare": 38, "tick": 37, "crash": 49}
conductor = mido.MidiTrack(); mid.tracks.append(conductor)
conductor.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(BPM)))
conductor.append(mido.MetaMessage("time_signature", numerator=4, denominator=4))
conductor.append(mido.MetaMessage("time_signature", numerator=7, denominator=8, time=int(P2 * TPB)))
conductor.append(mido.MetaMessage("time_signature", numerator=4, denominator=4, time=int((P3 - P2) * TPB)))
ch = 0
for tr in tracks:
    trk = mido.MidiTrack(); mid.tracks.append(trk); trk.append(mido.MetaMessage("track_name", name=tr))
    is_drum = tr in DRUM and DRUM[tr] is not None
    c = 9 if is_drum else ch
    if not is_drum:
        prog = GM.get(tr, 47 if tr == "timpani" else 0)
        trk.append(mido.Message("program_change", program=prog, channel=c))
        ch += 1
        if ch == 9:
            ch = 10
    ev = []
    for t2, s, du, p, v in notes:
        if t2 != tr:
            continue
        pitch = DRUM[tr] if is_drum else p
        ev.append((int(s * TPB), 1, pitch, v)); ev.append((int((s + du) * TPB), 0, pitch, 0))
    ev.sort(key=lambda e: (e[0], e[1]))
    last = 0
    for t3, on, p, v in ev:
        trk.append(mido.Message("note_on" if on else "note_off", note=p, velocity=v, channel=c, time=t3 - last))
        last = t3
mid.save(os.path.join(OUT, "orsiel_theme.mid"))

# ================================================================ 미리듣기 (간이 합성, 구조 확인용)
SR = 22050
total = int((END * SPB + 4) * SR)
mix = np.zeros(total)
rng = np.random.default_rng(3)
hz = lambda p: 440 * 2 ** ((p - 69) / 12)


def env(n, a, r):
    e = np.ones(n); ai, ri = max(1, int(a * SR)), max(1, int(r * SR))
    e[:min(ai, n)] = np.linspace(0, 1, min(ai, n)); e[-min(ri, n):] *= np.linspace(1, 0, min(ri, n)); return e


def lp(x, f):
    return sosfilt(butter(2, f, "low", fs=SR, output="sos"), x)


def saw(f, n, det=(0,)):
    t = np.arange(n) / SR
    return sum(2 * ((t * f * 2 ** (d / 1200)) % 1) - 1 for d in det) / len(det)


def voice(tr, p, dur, vel):
    n = int(dur * SPB * SR) + int(0.3 * SR); f = hz(p); v = vel / 127; t = np.arange(n) / SR
    if tr in ("strings", "strings_trem"):
        x = lp(saw(f, n, (-7, 0, 7)), 2500) * env(n, 0.01 if tr == "strings" else 0.08, 0.12)
        if tr == "strings_trem":
            x *= 0.6 + 0.4 * np.sign(np.sin(2 * np.pi * 14 * t))
        return x * v * 0.22
    if tr in ("horn", "lowbrass", "trumpet"):
        bright = 900 if tr == "lowbrass" else (3000 if tr == "trumpet" else 1600)
        x = lp(saw(f, n, (-5, 5)), bright) * env(n, 0.04 if tr != "trumpet" else 0.005, 0.15)
        return x * v * (0.32 if tr != "trumpet" else 0.25)
    if tr == "choir":
        vib = 1 + 0.004 * np.sin(2 * np.pi * 5 * t)
        x = sum(np.sin(2 * np.pi * f * k * vib * t) / k for k in (1, 2, 3)) + 0.3 * np.sin(2 * np.pi * f * 1.003 * t)
        return lp(x, 1800) * env(n, 0.35, 0.4) * v * 0.16
    if tr == "bass":
        x = lp(saw(f, n), 400) + 0.6 * np.sin(2 * np.pi * f * t)
        return x * env(n, 0.01, 0.1) * v * 0.35
    if tr == "bell":
        x = sum(np.sin(2 * np.pi * f * r * t) * np.exp(-t / (2.5 / r)) for r in (1, 2.01, 2.76, 5.4))
        return x * v * 0.35
    if tr == "whale":
        ff = f * (1 + 0.25 * np.sin(np.pi * t / max(t[-1], 0.1)))
        return np.sin(2 * np.pi * np.cumsum(ff) / SR) * env(n, 0.8, 1.2) * v * 0.3
    if tr == "riser":
        x = rng.standard_normal(n) * np.linspace(0, 1, n) ** 2
        return sosfilt(butter(2, [800, 6000], "band", fs=SR, output="sos"), x) * v * 0.25
    if tr in ("timpani", "taiko", "kick"):
        n = int(0.6 * SR); t = np.arange(n) / SR
        base = {"timpani": f, "taiko": 70, "kick": 55}[tr]
        x = np.sin(2 * np.pi * np.cumsum(base * (1 + np.exp(-t / 0.03))) / SR) * np.exp(-t / (0.35 if tr != "kick" else 0.15))
        x += 0.3 * rng.standard_normal(n) * np.exp(-t / 0.01)
        return x * v * (0.55 if tr == "taiko" else 0.45)
    if tr in ("snare", "tick"):
        n = int(0.2 * SR); t = np.arange(n) / SR
        x = sosfilt(butter(2, 2000 if tr == "snare" else 5000, "high", fs=SR, output="sos"), rng.standard_normal(n))
        return x * np.exp(-t / (0.06 if tr == "snare" else 0.015)) * v * (0.3 if tr == "snare" else 0.12)
    if tr == "crash":
        n = int(2.5 * SR); t = np.arange(n) / SR
        return sosfilt(butter(2, 4000, "high", fs=SR, output="sos"), rng.standard_normal(n)) * np.exp(-t / 0.8) * 0.35
    return np.zeros(n)


for tr, s, du, p, v in notes:
    x = voice(tr, p, du, v); i = int(s * SPB * SR)
    end = min(total, i + len(x)); mix[i:end] += x[:end - i]
ir_n = int(1.8 * SR); ir = rng.standard_normal(ir_n) * np.exp(-np.arange(ir_n) / (0.45 * SR)); ir = lp(ir, 5000); ir /= np.sum(np.abs(ir))
mix = mix + 6 * fftconvolve(mix, ir)[:total] * 0.35
mix /= np.max(np.abs(mix)) + 1e-9
mix = np.tanh(mix * 1.4) / np.tanh(1.4) * 0.9
wavfile.write(os.path.join(OUT_PREVIEW, "orsiel_preview.wav"), SR, (mix * 32767).astype(np.int16))
print(f"notes {len(notes)}, length {END * SPB:.1f}s, markers {markers}")
