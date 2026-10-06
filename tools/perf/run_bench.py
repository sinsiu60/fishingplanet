"""벤치마크 B1~B6 을 화면 없이 돌린다 (OPTIMIZATION.md O1) — 게임 안 '테스트: 벤치마크' 와 같은 대본(src/core/perf.py).

사용: python tools/perf/run_bench.py [--mobile] [--secs 30] [--prof] [--out 결과.json]
  --mobile  폰 캔버스(600x270) · 모바일 설정
  --prof    장면마다 cProfile 로 느린 함수 상위 20개 (자기 시간 기준)
PC 숫자는 폰보다 5~10배 빠르므로 비율로 본다.
"""
import cProfile
import json
import os
import pstats
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
SAVE = os.path.join(ROOT, "build", "perf_save")
os.makedirs(SAVE, exist_ok=True)
os.environ["FISHING_SAVE_DIR"] = SAVE
if "--mobile" in sys.argv and "--mobile-preview" not in sys.argv:
    sys.argv.append("--mobile-preview")

import pygame  # noqa: E402


def main() -> int:
    secs = float(sys.argv[sys.argv.index("--secs") + 1]) if "--secs" in sys.argv else 30.0
    prof = "--prof" in sys.argv
    from src.core.game import Game
    from src.scene.menu import TitleScene
    g = Game(start_scene=TitleScene)
    g._acc, g._frames = 0.0, 0
    err = g.perf.start_bench(secs)
    if err:
        print("시작 실패:", err)
        return 1
    runner = g.perf.bench
    print(f"pygame {pygame.version.ver} · 캔버스 {g.screen.canvas.get_size()} · 각 {secs:.0f}초")
    profs = {}
    cur = None
    last = time.perf_counter()
    while g.perf.bench is not None and g.running:
        tag = runner.tag()
        if prof and tag != cur:
            cur = tag
            profs[tag] = cProfile.Profile()
        if prof:
            profs[tag].enable()
        now = time.perf_counter()
        g._frame(min(0.25, max(1e-3, now - last)))   # 실제 걸린 시간 (상한 없이 — fps = 이 기계가 낼 수 있는 최대)
        last = now
        if prof:
            profs[tag].disable()
    for r in runner.results:
        line = (f"{r['bench']} {r['name']:28} fps {r['fps']:5.1f} · 프레임 평균 {r['frame_ms']:5.2f} 상위5% {r['frame_p95']:5.2f} "
                f"최대 {r['frame_max']:6.2f} · 로직 {r['logic_ms']:5.2f} 그리기 {r['draw_ms']:5.2f} 출력 {r['present_ms']:4.2f} ms"
                f" · 파티클 최대 {r['particles_max']} · {r['rss_mb']:.0f}MB" + (f" · 멈칫 {r['stall_ms']:.1f}ms" if "stall_ms" in r else ""))
        print(line)
        if prof and r["bench"] in profs:
            st = pstats.Stats(profs[r["bench"]]).stats
            n = max(1, r.get("frames", 1))
            rows = sorted(st.items(), key=lambda kv: -kv[1][2])[:20]
            r["top"] = [f"{v[2] / n * 1000:6.2f}ms {v[1] / n:6.1f}회 {os.path.relpath(k[0], ROOT) if k[0].startswith(ROOT) else k[0]}:{k[1]} {k[2]}"
                        for k, v in rows]
            for ln in r["top"]:
                print("      ", ln)
    if "--out" in sys.argv:
        json.dump({"secs": secs, "results": runner.results, "pygame": pygame.version.ver,
                   "canvas": g.screen.canvas.get_size()}, open(sys.argv[sys.argv.index("--out") + 1], "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
