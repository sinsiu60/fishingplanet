"""보스 예고음 세트 확인 (BOSS_ARENA.md 🅱, DESIGN.md 51-3).

  python tools/boss_signal_set.py            실제 파이팅을 화면 없이 돌려 검사:
                                             보스전 = sig_boss_* 만 (모드 상관없이) · 일반 = 보스 소리 없음 · '쾅'/'챙'과 화면 임팩트가 같은 틱 ·
                                             보스 곡 덕킹 −4/−5dB · 숙련 '처음' 보조음 · '소리 신호' 끔 = 소리 없음 · 길이 = 일반 신호와 같음
  python tools/boss_signal_set.py --render   계열 6개 × (보스 / 일반) 5초 녹음을 SUNO 보스 곡 위에 게임 음량으로 섞어
                                             tools/audio/reference/boss_signals/ 에 wav 로 + 비교 표 (길이 · 시각 · LUFS)
"""
import copy
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
os.chdir(ROOT)

import numpy as np  # noqa: E402

REF = os.path.join(ROOT, "tools", "audio", "reference", "boss_signals")
FAILS: list[str] = []
FAMS = ("release", "reel", "timing", "direction", "endure", "gesture")
FAM_KO = {"release": "풀기", "reel": "감기", "timing": "타이밍", "direction": "방향", "endure": "참기", "gesture": "제스처"}


def check(ok: bool, msg: str) -> None:
    print(("  ok  " if ok else "  FAIL ") + msg)
    if not ok:
        FAILS.append(msg)


# ───────────────────────── 실제 파이팅 검사 ─────────────────────────
def run_fight(g, fid: str, sec: float, pre=None):
    import boss_arena_check as bc
    played = []
    orig = g.sfx.play

    def spy(name, *a, **k):
        played.append((round(sc.signal_audio.clock, 4), name))
        return orig(name, *a, **k)
    sc = bc.start(g, fid)
    g.sfx.play = spy
    sc.signal_audio.log.clear()
    ducks = []

    def pre2(s):
        if pre:
            pre(s)
        ducks.append(g.sfx.boss_duck_db)
    try:
        bc.step(g, sc, sec, draw=False, pre=pre2)
    finally:
        g.sfx.play = orig
    log = list(sc.signal_audio.log)
    sc._end_fight()
    return played, log, ducks


def checks():
    import boss_arena_check as bc
    g = bc.pb.make_game()
    print("보스전 (여우비 · 일렉트로 · 일섬 · 환상, 각 40초):")
    allp, alllog = [], []
    for fid in ("golden_carp", "silver_bass", "marlin", bc.PHANTOM):
        for mode in (0, 2):
            g.settings.set("signal_mode", mode)   # 자연음 / 강조 — 보스전이면 둘 다 보스 세트
            played, log, ducks = run_fight(g, fid, 40.0)
            sig = [n for _, n in played if n.startswith("sig_")]
            other = [n for n in sig if not n.startswith(("sig_boss_", "sig_aux_", "sig_bell"))]
            boss = [n for n in sig if n.startswith("sig_boss_")]
            check(boss and not other, f"{fid} 모드 {mode}: 신호 소리 {len(sig)}개 모두 보스 세트 (보스 {len(boss)} · 그 밖 {other[:3]})")
            allp += played
            alllog += log
            if boss:
                check(min(ducks) <= -3.9, f"{fid} 모드 {mode}: 보스 곡 덕킹 최저 {min(ducks):.1f}dB")
    g.settings.set("signal_mode", 0)
    fams = {n.split("#")[0] for _, n in allp if n.startswith("sig_boss_")}
    print("  나온 보스 소리:", sorted(fams))
    # 같은 틱: '쾅' · '챙' 바로 옆(같은 시계 값)에 화면 임팩트
    hits = [(t, n) for t, n in alllog if n in ("sig_boss_release_go", "sig_boss_timing_apex")]
    imps = {t for t, n in alllog if n.startswith("impact:")}
    same = sum(1 for t, _ in hits if t in imps)
    check(hits and same == len(hits), f"'쾅' · '챙' {len(hits)}번 중 같은 틱 화면 임팩트 {same}번")
    # 일반 파이팅
    played, _, ducks = run_fight(g, "lenok", 30.0)
    check(not any(n.startswith("sig_boss_") for _, n in played) and min(ducks) == 0.0,
          f"일반 파이팅(열목어): 보스 소리 · 보스 곡 덕킹 없음 (신호 {sum(1 for _, n in played if n.startswith('sig_'))}개)")
    unit()
    # 숙련 '처음' → 보조음 한 겹 (실제 파이팅)
    sv = g.save.data
    keep = copy.deepcopy(sv.get("pattern_mastery", {}))
    sv["pattern_mastery"] = {}
    played, _, _ = run_fight(g, "silver_bass", 30.0)
    aux = [n for _, n in played if n.startswith("sig_aux_")]
    boss_n = sum(1 for _, n in played if n.startswith("sig_boss_"))
    print(f"  (실제 파이팅 숙련 '처음': 보스 {boss_n} · 보조음 {len(aux)} — 돌진은 원래 보조음 없음)")
    sv["pattern_mastery"] = {k: 99 for k in ("rush", "bite", "hide", "charge", "reverse", "tired", "jump", "leap", "thrash",
                                              "pump", "turn", "dive", "surface", "shake", "twist")}
    played, _, _ = run_fight(g, "silver_bass", 30.0)
    check(not any(n.startswith("sig_aux_") for _, n in played), "숙련 충분: 보조음 없음")
    sv["pattern_mastery"] = keep
    # 소리 신호 끔
    g.settings.set("signal_sound", False)
    played, _, _ = run_fight(g, "golden_carp", 30.0)
    check(not any(n.startswith("sig_boss_") for _, n in played), "'소리 신호' 끔: 보스 예고음 없음 (진동만)")
    g.settings.set("signal_sound", True)
    # 길이 = 일반 신호와 같음 (레시피 len)
    rec = json.load(open(os.path.join(ROOT, "data", "sfx_recipes.json"), encoding="utf-8"))
    pairs = [("sig_boss_release_hum", "sig_nat_release_quiver"), ("sig_boss_release_go", "sig_nat_release_go"),
             ("sig_boss_reel", "sig_nat_reel"), ("sig_boss_timing_tick", "sig_timing_tick"),
             ("sig_boss_direction", "sig_nat_direction"), ("sig_boss_endure", "sig_nat_endure"),
             ("sig_boss_gesture", "sig_nat_gesture")]
    for b, n in pairs:
        check(abs(rec[b]["len"] - rec[n]["len"]) < 0.005, f"길이 {b} {rec[b]['len']}s = {n} {rec[n]['len']}s")


class _Brain:
    def __init__(self, action):
        self.state, self.pending, self.state_t, self.cur_telegraph = "telegraph", action, 0.0, 1.2
        self.turn_dir, self.apex = 1, 1.0

    def time_to_apex(self):
        return self.apex


class _Fight:
    def __init__(self, action, rarity="legend"):
        self.brain = _Brain(action)
        self.fish = {"rarity": rarity}
        self.size_cm, self.mutations = 200, []


class _Sfx:
    def __init__(self):
        self.played, self.haptics, self.offset_s = [], None, 0.0
        self.ducks = []

    def play(self, name, vol=1.0, pan=None, haptic=None, strength=1.0):
        self.played.append((name, round(vol, 3), pan))

    def boss_duck(self, db, hold):
        self.ducks.append((db, hold))


def unit():
    """6계열 × (보스 / 일반 자연음) — 신호음 모듈을 가짜 파이팅으로 직접 돌림 (실제 파이팅은 패턴이 운에 달려서)."""
    from src.audio.signal_audio import SignalAudio
    from src.ui import signal_slots
    acts = {"release": "bite", "reel": "charge", "timing": "jump", "direction": "turn", "endure": "shake", "gesture": "twist"}
    want = {"release": ["sig_boss_release_hum#", "sig_boss_release_go"], "reel": ["sig_boss_reel"],
            "timing": ["sig_boss_timing_tick#", "sig_boss_timing_apex"], "direction": ["sig_boss_direction"],
            "endure": ["sig_boss_endure"], "gesture": ["sig_boss_gesture"]}
    print("신호음 모듈 6계열:")
    for fam, act in acts.items():
        check(signal_slots.family_of(act) == fam, f"{act} = {fam} 계열")
        for boss, first in ((True, False), (True, True), (False, False)):
            sfx, hits = _Sfx(), []
            sa = SignalAudio(sfx, mastery=lambda f=first: {} if f else {act: 99}, boss=lambda fight, b=boss: b,
                             on_hit=hits.append)
            f = _Fight(act)
            sa.start(act, fam, f)
            for _ in range(90):   # 1.5초
                f.brain.state_t += 1 / 60
                sa.update(1 / 60, f)
            sa.on_event(f"action:{act}")
            names = [n for n, _, _ in sfx.played]
            if boss:
                ok = all(any(n.startswith(w) for n in names) for w in want[fam]) and \
                    all(n.startswith(("sig_boss_", "sig_aux_")) for n in names)
                aux = any(n.startswith("sig_aux_") for n in names)
                check(ok and aux == first, f"보스 {FAM_KO[fam]}{' (숙련 처음)' if first else ''}: {sorted(set(n.split('#')[0] for n in names))}")
                check(sfx.ducks and sfx.ducks[0] == (-4, 0.25), f"보스 {FAM_KO[fam]}: 예고 시작 보스 곡 −4dB 0.25초")
                if fam in ("release", "timing"):
                    check((-5, 0.2) in sfx.ducks, f"보스 {FAM_KO[fam]}: 행동 · 정점 −5dB 0.2초")
                if fam == "timing":
                    check(hits == ["apex"], "보스 타이밍: '챙' 순간 장면에 알림 (같은 틱 임팩트)")
                vols = [v for n, v, _ in sfx.played if n in ("sig_boss_reel", "sig_boss_endure", "sig_boss_gesture", "sig_boss_direction",
                                                             "sig_boss_release_go", "sig_boss_timing_apex")]
                check(all(abs(v - 0.9) < 1e-6 for v in vols), f"보스 {FAM_KO[fam]}: 기준 음량 0.9 ({vols})")
            else:
                check(not any(n.startswith("sig_boss_") for n in names) and not sfx.ducks,
                      f"일반 {FAM_KO[fam]}: 보스 소리 · 덕킹 없음 ({sorted(set(n.split('#')[0] for n in names))})")


# ───────────────────────── 기준 녹음 ─────────────────────────
RATE = 44100


def load(path):
    from boss_loudness import load as ld
    return ld(path)


def snd(name: str) -> np.ndarray:
    fn = name.replace("#", "__")
    for ext in (".ogg", ".wav"):
        p = os.path.join(ROOT, "assets", "sfx_generated", fn + ext)
        if os.path.exists(p):
            return load(p)
    raise FileNotFoundError(name)


def timeline(fam: str, boss: bool):
    """[(시각, 소리, 음량, pan)] · 예고 시작 1.0초 · 행동/정점 2.2초 (일반과 같은 시각)."""
    t0, act = 1.0, 2.2
    out = []
    v = 0.9 if boss else 0.8
    if fam == "release":
        if not boss:
            out.append((t0, "sig_nat_release_gulp", 0.7, None))
        silence = 0.1
        for i in range(8):
            q = i / 8
            t = t0 + q * (act - t0)
            if t > act - silence:
                break
            out.append((t, f"sig_boss_release_hum#{i}" if boss else f"sig_nat_release_quiver#{i}",
                        v * (0.8 + 0.2 * q) if boss else 0.45 + 0.4 * q, None))
        out.append((act, "sig_boss_release_go" if boss else "sig_nat_release_go", v if boss else 1.0, None))
    elif fam == "timing":
        total = act - t0
        n = max(3, min(7, int(total / 0.16)))
        for k in range(n):
            step = round(k / max(1, n - 1) * 5)
            out.append((t0 + total * (k / n) ** 0.7, f"sig_boss_timing_tick#{step}" if boss else f"sig_nat_timing_boil#{step}",
                        v * (0.75 + 0.25 * k / n) if boss else 0.55 + 0.3 * k / n, None))
        out.append((act, "sig_boss_timing_apex" if boss else "sig_nat_timing_apex", v if boss else 0.85, None))
    elif fam == "direction":
        out.append((t0, "sig_boss_direction" if boss else "sig_nat_direction", v if boss else 0.85, 0.85))
    else:
        out.append((t0, f"sig_boss_{fam}" if boss else f"sig_nat_{fam}", v if boss else 0.8, None))
    return out, t0, act


def write_ref(path: str, x: np.ndarray) -> None:
    """저장소 크기: 22.05kHz 스테레오 16비트 (두 샘플 평균 = 간단한 저역 통과 뒤 반으로)."""
    import wave
    n = len(x) // 2 * 2
    y = (x[:n:2] + x[1:n:2]) / 2
    pcm = (np.clip(y, -1, 1) * 32767).astype("<i2")
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(RATE // 2)
        w.writeframes(pcm.tobytes())


def render():
    import pyloudnorm
    from src.audio.boss_suno import SunoBoss
    cfg = json.load(open(os.path.join(ROOT, "data", "audio_config.json"), encoding="utf-8"))
    gains = json.load(open(os.path.join(ROOT, "data", "music", "boss_bgm_gain.json"), encoding="utf-8"))
    song = "yeoubi"
    mus = load(os.path.join(ROOT, "assets", "music", "boss", song, "phase2_loop.ogg"))[int(RATE * 8): int(RATE * 13)]
    master, vmus, vsfx = 0.8, 0.8, 1.0   # 설정 기본값
    mus_gain = SunoBoss.SUNO_GAIN * gains[song]["gain"] * master * vmus
    sig_gain = master * vsfx * 10 ** (cfg["boss"]["sig_db"] / 20)
    duck = json.load(open(os.path.join(ROOT, "data", "boss_arena.json"), encoding="utf-8"))["sound"]["duck"]
    os.makedirs(REF, exist_ok=True)
    meter = pyloudnorm.Meter(RATE)
    rows = []
    for fam in FAMS:
        res = {}
        for boss in (True, False):
            tl, t0, act = timeline(fam, boss)
            n = len(mus)
            sig = np.zeros((n, 2))
            first = last = None
            for t, name, vol, pan in tl:
                x = snd(name) * vol
                if pan is not None:
                    x = x * np.array([1 - max(0, pan) * 0.7, 1 + min(0, pan) * 0.7])
                i = int(t * RATE)
                m = min(n - i, len(x))
                sig[i:i + m] += x[:m]
                first = t if first is None else min(first, t)
                last = max(last or 0, t + len(x) / RATE)
            sig *= sig_gain
            env = np.zeros(n)   # 음악 덕킹 (dB)
            tt = np.arange(n) / RATE

            def dip(at, db, hold, rel=0.15):
                k = np.where(tt < at, 0.0, np.where(tt < at + hold, db, np.where(tt < at + hold + rel, db * (1 - (tt - at - hold) / rel), 0.0)))
                return k
            if boss:
                env = np.minimum(env, dip(t0, *duck["telegraph"]))
                if fam in ("release", "timing"):
                    env = np.minimum(env, dip(act, *duck["action"]))
            else:   # 지금: 신호 소리마다 음악 −2dB (보스 곡 동안 한도) 0.25초
                for t, *_ in tl:
                    env = np.minimum(env, dip(t, cfg["boss"]["duck_mus"], 0.25))
            music = mus * mus_gain * (10 ** (env / 20))[:, None]
            mix = np.clip(music + sig, -1, 1)
            tag = "boss" if boss else "normal"
            write_ref(os.path.join(REF, f"{fam}_{tag}.wav"), mix)
            # 신호만 · 같은 구간 음악의 LUFS (pyloudnorm: 400ms 블록 — 짧은 소리는 앞뒤 0.2초 포함 구간)
            a, b = int(max(0, first - 0.2) * RATE), int(min(5.0, last + 0.2) * RATE)
            if b - a < int(0.45 * RATE):
                b = a + int(0.45 * RATE)
            s_l = meter.integrated_loudness(sig[a:b])
            m_l = meter.integrated_loudness(music[a:b])
            res[boss] = {"len": round(last - first, 2), "key": round(act - t0, 2) if fam in ("release", "timing") else None,
                         "sig": s_l, "mus": m_l, "snr": s_l - m_l}
        rows.append((fam, res))
    print(f"\n{'계열':6} | {'길이(보스/일반)':14} | {'행동·정점 시각':12} | {'신호 LUFS 보스/일반':18} | {'음악 대비 dB 보스/일반':20}")
    for fam, r in rows:
        b, n = r[True], r[False]
        key = f"{b['key']}s / {n['key']}s" if b["key"] is not None else "-"
        print(f"{FAM_KO[fam]:6} | {b['len']:.2f}s / {n['len']:.2f}s | {key:12} | {b['sig']:6.1f} / {n['sig']:6.1f}"
              f"      | {b['snr']:+5.1f} / {n['snr']:+5.1f} ({b['snr'] - n['snr']:+.1f})")
    json.dump({fam: {("boss" if k else "normal"): v for k, v in r.items()} for fam, r in rows},
              open(os.path.join(REF, "table.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\n녹음: {REF}/<계열>_boss.wav · <계열>_normal.wav (곡 {song} phase2, 설정 기본 음량)")


if __name__ == "__main__":
    if "--render" in sys.argv:
        render()
    else:
        checks()
        print(f"\n실패 {len(FAILS)}개" if FAILS else "\n모두 통과")
        sys.exit(1 if FAILS else 0)
