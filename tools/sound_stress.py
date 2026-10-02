"""최악 상황 사운드 점검 (DESIGN.md 32-14, Phase S8).

전설 파이팅(보스 층 3개) + 폭풍(빗소리·바람·천둥) + 이중 패턴 예고 + 퍼펙트·더블 퍼펙트 연타 + 릴 감기·빨강 장력을
실제 시간 속도로 N초 돌리고, 매 프레임 믹서 상태(재생 중 소리·채널 음량·위치)를 기록해 **실제 출력과 같은 합(mixdown)을
오프라인으로 다시 만들어** 찢어짐(1.0 넘는 샘플)·최대 음량·끊긴 소리(채널을 못 얻은 재생)를 잰다.

  python tools/sound_stress.py [초=20] [--wav 파일]     (오디오 장치 없이 돌아감: SDL_AUDIODRIVER=dummy)
"""
import os
import random
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("FISHING_SAVE_DIR", os.path.join(ROOT, "build", "stress_save"))

import numpy as np  # noqa: E402


def main(argv) -> int:
    sec = float(argv[0]) if argv and not argv[0].startswith("--") else 20.0
    wav = argv[argv.index("--wav") + 1] if "--wav" in argv else None
    import pygame
    from src.audio import sfx as sfxmod
    from src.audio.adaptive_music import GAIN
    from src.core.game import Game
    from src.save.save_game import SaveGame
    from src.scene.fishing_scene import FishingScene
    from src.fishing.casting import CastState
    from src.ui import tutorial as tut

    fails = {"sig": 0, "sfx": 0, "reward": 0, "amb": 0, "ui": 0, "mus": 0}
    asked = dict(fails)
    orig = sfxmod.Sfx._play

    def _play(self, name, volume, pan):
        ch = orig(self, name, volume, pan)
        if self.enabled and name in self.sounds:
            b = self.bus_of(name)
            asked[b] += 1
            if ch is None and self.clock - self.last_play.get(name, -9) >= 0.0 and name not in self.loops:
                fails[b] += 1
        return ch
    sfxmod.Sfx._play = _play

    os.makedirs(os.environ["FISHING_SAVE_DIR"], exist_ok=True)
    g = Game()
    g.save = SaveGame(1)
    g.scenes.stack.clear()
    sc = FishingScene(g)
    g.scenes.push(sc)
    for k in list(tut.CARDS) + list(tut.GUIDES):
        sc.tutorial.seen.add(k)
    legend = next(f for f in sc.all_fish if f["rarity"] == "legend" and f.get("phases"))
    sc._set_spot(legend["spot"])
    sc.weather_sys.current = "storm"
    sc.weather_sys.next_change = 9e9
    import copy
    sc.bite.fish = copy.deepcopy(legend)
    sc.bite.cast_distance = 20
    sc.cast.state = CastState.HOOKED
    sc._start_fight()
    f = sc.fight
    f.brain.phase = len(f.brain.phases) - 1   # 마지막 페이즈 = 보스 층 3개 모두
    sfx, am = g.sfx, g.adaptive
    rate = sfx.rate
    frames: list[tuple] = []   # (시계, [(소리 배열, 시작 샘플 위치, L, R, 반복)])
    arrays: dict[int, np.ndarray] = {}

    def arr(snd) -> np.ndarray:
        k = id(snd)
        if k not in arrays:
            a = pygame.sndarray.array(snd).astype(np.float32) / 32768
            arrays[k] = a if a.ndim == 2 else np.stack([a, a], axis=1)
        return arrays[k]

    started: dict[int, tuple] = {}
    dt = 1 / 60
    n = int(sec * 60)
    rnd = random.Random(4)
    t_real = time.perf_counter()
    held = g.input.held
    g.input.held = lambda name: True if name == "reel" else held(name)  # 손: 릴 감기 계속
    for i in range(n):
        sc.card = None   # 첫 만남 카드·도움말로 멈추지 않게
        sc.help = False
        f.stamina = f.stamina_max   # 끝까지 파이팅 (잡히지 않게)
        f.distance = max(f.distance, 12.0)
        f.tension = max(f.tension, f.green_high + 8)
        if i % 90 == 0:  # 1.5초마다 예고 (이중 패턴이 있으면 이중, 없으면 계열을 돌아가며)
            b = sc.fight.brain
            acts = ["dual"] if getattr(b, "dual_pairs", None) else []
            b._begin_telegraph((acts + ["rush", "jump", "turn", "shake"])[(i // 90) % (len(acts) + 4)])
        if i % 45 == 20:  # 신호 두 계열을 동시에 (이중 패턴처럼) — 뇌 상태와 상관없이 소리만
            pairs = [("turn", "direction", "shake", "endure"), ("twist", "gesture", "charge", "reel"), ("jump", "timing", "turn", "direction")]
            a1, f1, a2, f2 = pairs[(i // 45) % 3]
            sc.signal_audio.start(a1, f1, f)
            sc.signal_audio.start(a2, f2, f)
        if i % 70 == 10:
            sc._perfect_sound()
        if i % 200 == 50:
            sc._on_fight_event("double_perfect")
        if i % 150 == 30:
            sc.lightning.strike(sc.cam.horizon, sc.cam.width)
        if i % 40 == 0:
            sfx.play("sfx_thrash", 0.9)
            sfx.play("sfx_splash", rnd.uniform(0.5, 1.0))
        sc.update(dt)
        sfx.update(dt, slow=g.time_scale < 0.99)
        am.update(dt)
        g.haptics.update(dt)
        # 기록: 효과음·환경음 (재생 시각부터 위치 계산)
        snap = []
        for e in sfx.active:
            key = id(e)
            if key not in started:
                started[key] = (e["ch"].get_sound(), sfx.clock - dt)
            snd, t0 = started[key]
            if snd is None:
                continue
            a = arr(snd)
            pos = int((sfx.clock - t0) * rate)
            if not e["loop"] and pos >= len(a):
                continue
            v = min(1.0, e["vol"] * sfx.bus_gain(e["bus"]))
            if e["pan"] is None:
                L = R = v
            else:
                ang = (max(-1.0, min(1.0, e["pan"])) + 1) * np.pi / 4
                L, R = min(1.0, v * np.cos(ang) * 1.41), min(1.0, v * np.sin(ang) * 1.41)
            snap.append((a, pos, L, R, e["loop"]))
        for k, snd in am.sounds.items():
            v = am.ch[k].get_volume()
            if v > 0:
                snap.append((arr(snd), int((am.clock - am.t0) * rate), v, v, True))
        if am.ch_sting.get_busy() and am.ch_sting.get_sound() is not None:
            v = min(1.0, GAIN * sfx.bus_gain("mus"))
            snd = am.ch_sting.get_sound()
            snap.append((arr(snd), int((arr(snd).shape[0] / rate - am.sting_left) * rate), v, v, False))
        frames.append(snap)
        # 실제 시간 속도 (채널이 진짜로 끝나야 다음 소리가 채널을 얻는다)
        lag = (i + 1) * dt - (time.perf_counter() - t_real)
        if lag > 0:
            time.sleep(lag)
    # 오프라인 합: 프레임마다 735샘플
    step = int(rate * dt)
    out = np.zeros((len(frames) * step, 2), np.float32)
    for fi, snap in enumerate(frames):
        o = fi * step
        for a, pos, L, R, loop in snap:
            if loop:
                idx = (pos + np.arange(step)) % len(a)
                seg = a[idx]
            else:
                seg = a[pos:pos + step]
            out[o:o + len(seg), 0] += seg[:, 0] * L
            out[o:o + len(seg), 1] += seg[:, 1] * R
    peak = float(np.abs(out).max())
    clipped = int((np.abs(out) > 1.0).sum())
    rms = float(np.sqrt((out ** 2).mean()))
    busy = max(len(s) for s in frames)
    print(f"최악 상황 {sec:.0f}초 (전설 {legend['name']} 마지막 페이즈 · 폭풍 · 이중 패턴 · 퍼펙트 연타 · 빨강 장력)")
    print(f"  동시 재생 최대 {busy}개 (채널 {pygame.mixer.get_num_channels()}, 신호 예약 {sfx.n_sig}, 음악 예약 {sfx.n_mus})")
    print(f"  최대 {20 * np.log10(max(peak, 1e-9)):+.1f} dBFS · 평균 {20 * np.log10(max(rms, 1e-9)):.1f} dBFS · 찢어진 샘플 {clipped} ({clipped / out.size * 100:.3f}%)")
    print(f"  재생 요청 {asked} / 채널 못 얻음 {fails}")
    print(f"  리미터 최저 ×{min(1.0, sfx.limiter):.2f} · 실제 진행 {time.perf_counter() - t_real:.1f}초")
    if wav:
        from src.audio.synth import write_wav
        write_wav(wav, np.clip(out, -1, 1))
        print("  저장:", wav)
    ok = fails["sig"] == 0 and clipped / out.size < 0.001
    print("결과:", "통과" if ok else "문제 있음")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
