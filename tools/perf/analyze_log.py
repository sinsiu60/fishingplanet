"""구형 기기 성능 로그(perf_logs/*.csv) 분석 (OPTIMIZATION.md O1): 벤치마크 · 장면별 fps, 프레임 시간 상위 5%, 가장 느린 1초.

사용: python tools/perf/analyze_log.py tools/perf/logs/perf_xxx.csv [더 많은 파일...]
      (파일마다 표 하나 — 수정 전후 로그를 나란히 비교)
"""
import csv
import sys
from collections import defaultdict


def summarize(path: str) -> None:
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    if not rows:
        print(path, "비어 있음")
        return
    groups = defaultdict(list)
    for r in rows:
        key = r.get("bench") or r.get("scene") or "-"
        groups[key].append(r)
    print(f"== {path} ({len(rows)}초)")
    print(f"{'장면':22} {'초':>4} {'fps':>5} {'프레임':>6} {'상위5%':>6} {'최악':>7} {'로직':>5} {'그리기':>6} {'출력':>5} {'파티클':>6} {'MB':>5}")
    for key, rs in groups.items():
        f = lambda k: [float(r[k]) for r in rs]   # noqa: E731
        p95 = sorted(f("frame_p95"))[min(len(rs) - 1, int(len(rs) * 0.95))]
        print(f"{key[:22]:22} {len(rs):4d} {sum(f('fps')) / len(rs):5.1f} {sum(f('frame_ms')) / len(rs):6.1f} {p95:6.1f} "
              f"{max(f('frame_max')):7.1f} {sum(f('logic_ms')) / len(rs):5.1f} {sum(f('draw_ms')) / len(rs):6.1f} "
              f"{sum(f('present_ms')) / len(rs):5.1f} {max(f('particles')):6.0f} {max(f('rss_mb')):5.0f}")
    worst = max(rows, key=lambda r: float(r["frame_max"]))
    print(f"가장 느린 1초: {worst.get('bench') or worst['scene']} 최대 프레임 {worst['frame_max']}ms (그리기 {worst['draw_ms']} · 로직 {worst['logic_ms']} · 출력 {worst['present_ms']})")


if __name__ == "__main__":
    for p in sys.argv[1:]:
        summarize(p)
