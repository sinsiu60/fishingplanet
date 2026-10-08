"""성능 측정 (OPTIMIZATION.md O1): 성능 로그 CSV · 벤치마크 장면 B1~B6.

성능 로그: 켜면 1초마다 한 줄 (fps · 프레임 시간 평균/상위 5%/최대 · 로직/오디오/그리기/출력(창 복사·flip) ms · 틱 수 ·
           파티클 수 · 재생 중 채널 수 · 메모리 MB · 장면 · 벤치마크 번호) → <저장 폴더>/perf_logs/perf_<시각>.csv
           (PC = 내 문서/FishingPlanet, 안드로이드 = 앱 저장소. '로그 내보내기' = 안드로이드 공유 창 + Android/data/<패키지>/files/perf_logs 복사)
벤치마크: 설정 → 테스트: 벤치마크 — 6개 장면을 각 30초 자동 재생하며 로그를 남기고, 끝나면 요약(perf_logs/bench_<시각>.json)을 화면에.
  B1 동네 저수지 낮 맑음 대기 / B2 방파제 밤 폭풍 일반 파이팅 / B3 환상 파장 → 파이팅 → 포획 연출 / B4 전설 파이팅 시작 (멈칫함)
  B5 윤슬 마을 좌우 이동 + 건물 출입 / B6 상점 · 도감 열고 스크롤
게임이 느린 구형 기기에서 같은 장면으로 수정 전후를 비교하는 것이 목적 — 로그 파일을 tools/perf/logs/ 에 올리면 tools/perf/analyze_log.py 로 표.
"""
import copy
import json
import math
import os
import time

import pygame

BENCHES = [("B1", "동네 저수지 낮 · 맑음 · 대기 (물결)"), ("B2", "바다 방파제 밤 · 폭풍 · 일반 파이팅"),
           ("B3", "환상 등장: 파장 → 파이팅 → 포획 연출"), ("B4", "전설 파이팅 시작 (음악 불러오기 멈칫함)"),
           ("B5", "윤슬 마을 좌우 이동 + 건물 출입"), ("B6", "상점 · 도감 열고 스크롤")]
CSV_HEAD = ["time", "scene", "bench", "fps", "frame_ms", "frame_p95", "frame_max", "logic_ms", "audio_ms", "draw_ms",
            "present_ms", "blit_ms", "flip_ms", "ticks", "particles", "channels", "rss_mb"]


def _p95(xs: list) -> float:
    if not xs:
        return 0.0
    s = sorted(xs)
    return s[min(len(s) - 1, int(len(s) * 0.95))]


def rss_mb() -> float:
    try:
        with open("/proc/self/statm") as f:
            return int(f.read().split()[1]) * os.sysconf("SC_PAGE_SIZE") / 1e6
    except Exception:
        return 0.0


def busy_channels() -> int:
    try:
        return sum(1 for i in range(pygame.mixer.get_num_channels()) if pygame.mixer.Channel(i).get_busy())
    except Exception:
        return 0


class PerfMonitor:
    def __init__(self, game):
        self.game = game
        self.logging = False
        self.file = None
        self.path = None
        self.last_path = None
        self.bench = None          # BenchRunner
        self._acc = []             # 이번 1초의 프레임 시간(ms)
        self._sum = [0.0] * 6      # logic, audio, draw, present, blit, flip (ms 합)
        self._ticks = 0
        self._t = 0.0
        self.last_row = None       # 성능 표시용 (파티클 · 채널 수)

    def active(self) -> bool:
        return self.logging or self.bench is not None or bool(self.game.settings.get("perf_overlay"))

    # ── 매 프레임 (game._frame) ──
    def frame(self, frame_time: float, ticks: int, logic: float, audio: float, draw: float, present: float, parts) -> None:
        self._acc.append(frame_time * 1000)
        for i, v in enumerate((logic, audio, draw, present, parts[0], parts[1])):
            self._sum[i] += v * 1000
        self._ticks += ticks
        self._t += frame_time
        if self.bench is not None:
            self.bench.frame(frame_time)
        if self._t >= 1.0:
            self._flush()

    def _flush(self) -> None:
        n = max(1, len(self._acc))
        sc = self.game.scenes.current
        row = {"time": round(time.time(), 1), "scene": type(sc).__name__ if sc else "-",
               "bench": self.bench.tag() if self.bench is not None else "",
               "fps": round(n / max(1e-6, self._t), 1), "frame_ms": round(sum(self._acc) / n, 2),
               "frame_p95": round(_p95(self._acc), 2), "frame_max": round(max(self._acc), 2),
               "logic_ms": round(self._sum[0] / n, 2), "audio_ms": round(self._sum[1] / n, 2),
               "draw_ms": round(self._sum[2] / n, 2), "present_ms": round(self._sum[3] / n, 2),
               "blit_ms": round(self._sum[4] / n, 2), "flip_ms": round(self._sum[5] / n, 2),
               "ticks": self._ticks, "particles": self.particles(), "channels": busy_channels(), "rss_mb": round(rss_mb(), 1)}
        self.last_row = row
        if self.file is not None:
            try:
                self.file.write(",".join(str(row[k]) for k in CSV_HEAD) + "\n")
                self.file.flush()
            except OSError:
                pass
        if self.bench is not None:
            self.bench.second(row)
        self._acc, self._sum, self._ticks, self._t = [], [0.0] * 6, 0, 0.0

    def particles(self) -> int:
        sc = self.game.scenes.current
        fn = getattr(sc, "perf_particles", None)
        try:
            return int(fn()) if fn else 0
        except Exception:
            return 0

    # ── 로그 파일 ──
    @staticmethod
    def log_dir():
        from src.core.paths import save_dir
        d = save_dir() / "perf_logs"
        os.makedirs(d, exist_ok=True)
        return d

    def start_log(self) -> None:
        if self.file is not None:
            return
        self.path = self.log_dir() / f"perf_{time.strftime('%Y%m%d_%H%M%S')}.csv"
        try:
            self.file = open(self.path, "w", encoding="utf-8")
            self.file.write(",".join(CSV_HEAD) + "\n")
            self.logging = True
        except OSError:
            self.file = None

    def stop_log(self) -> None:
        if self.file is not None:
            self._flush()
            self.file.close()
            self.file = None
            self.last_path = self.path
            self._copy_out(self.path)
        self.logging = False

    def _copy_out(self, path) -> None:
        """안드로이드: 다른 앱 · PC(USB) 에서 보이는 폴더(Android/data/<패키지>/files/perf_logs)에도 복사."""
        from src.platform.detect import IS_ANDROID
        if not IS_ANDROID or path is None:
            return
        try:
            from src.platform import android
            d = android.shared_dir()
            if d is not None:
                import shutil
                os.makedirs(d / "perf_logs", exist_ok=True)
                shutil.copy(str(path), str(d / "perf_logs" / os.path.basename(str(path))))
        except Exception:
            pass

    def export(self) -> str:
        """'로그 내보내기' — 안드로이드: 가장 최근 로그를 공유 창으로 (+ 외부 폴더 복사). PC: 폴더 위치."""
        from src.platform.detect import IS_ANDROID
        if self.file is not None:
            self.file.flush()
        path = self.path if self.file is not None else self.last_path
        if path is None:
            files = sorted(self.log_dir().glob("*.csv"))
            path = files[-1] if files else None
        if path is None:
            return "내보낼 로그가 없어요 (먼저 성능 로그를 켜세요)"
        if IS_ANDROID:
            self._copy_out(path)
            from src.platform import android
            try:
                text = open(path, encoding="utf-8").read()
            except OSError:
                return "로그를 읽지 못했어요"
            ok = android.share_text(text[-60000:], f"미니 피싱 성능 로그 {os.path.basename(str(path))}")
            return "공유 창을 열었어요 (Android/data/com.sinsiu.fishingplanet/files/perf_logs 에도 복사)" if ok \
                else "공유 창을 못 열었어요 — Android/data/com.sinsiu.fishingplanet/files/perf_logs 에 복사했어요"
        return f"로그 폴더: {self.log_dir()}"

    # ── 벤치마크 ──
    def start_bench(self, secs: float = 30.0) -> str | None:
        if self.bench is not None:
            return "이미 벤치마크 중"
        self.bench = BenchRunner(self.game, self, secs)
        err = self.bench.start()
        if err:
            self.bench = None
        return err


class BenchRunner:
    """B1~B6 을 차례로 (각 secs 초). 매 프레임 game._frame 이 update(dt) 를 부른다."""

    def __init__(self, game, perf: PerfMonitor, secs: float):
        self.game = game
        self.perf = perf
        self.secs = secs
        self.i = -1
        self.t = 0.0
        self.frames: list = []
        self.rows: list = []
        self.results: list = []
        self.fs = None
        self.marks: dict = {}
        self._guide = None
        self._held = None
        self._reel = False
        self._log_was_on = False
        self.done = False

    def tag(self) -> str:
        return BENCHES[self.i][0] if 0 <= self.i < len(BENCHES) else ""

    # ── 시작 · 끝 ──
    def start(self) -> str | None:
        from src.scene.fishing_scene import FishingScene
        g = self.game
        fs = next((s for s in g.scenes.stack if isinstance(s, FishingScene)), None)
        if fs is None:
            if g.save is None:
                from src.save.save_game import SaveGame
                g.save = SaveGame(1)
                g.no_save = True   # 타이틀에서 시작한 벤치마크: 슬롯 1을 덮어쓰지 않게
            fs = FishingScene(g)
        self.fs = fs
        from src.core.config import load_json
        g.save.data["unlocked_spots"] = sorted({s["id"] for s in load_json("spots.json")["spots"]})
        from src.ui import tutorial as tut
        for k in list(tut.CARDS) + list(tut.GUIDES):
            fs.tutorial.seen.add(k)
        self._guide = (g.guide.enabled, g.guide.frozen)
        g.guide.enabled = lambda: False
        g.guide.frozen = lambda: False
        g.guide.abort()   # 진행 중 튜토리얼을 '중단'으로 (run 만 지우면 패턴 튜토리얼이 비워 둔 물고기 행동 목록이 안 돌아옴)
        # 파이팅의 '감기' 는 장면이 매 틱 입력(input.held)에서 읽으므로, 벤치마크 동안은 입력을 대신한다
        self._held = g.input.held
        self._reel = False
        g.input.held = lambda name, _h=self._held: self._reel if name in ("reel", "press") else _h(name)
        self._log_was_on = self.perf.logging
        if not self.perf.logging:
            self.perf.start_log()
        self._next()
        return None

    def _finish(self) -> None:
        g = self.game
        self.done = True
        if self._guide:
            g.guide.enabled, g.guide.frozen = self._guide
        self._teardown()
        g.scenes.stack[:] = [self.fs]
        summary = {"when": time.strftime("%Y-%m-%d %H:%M:%S"), "secs": self.secs, "log": str(self.perf.path or ""),
                   "device": f"{pygame.version.ver} · {g.screen.fmt_note}", "results": self.results}
        try:
            p = self.perf.log_dir() / f"bench_{time.strftime('%Y%m%d_%H%M%S')}.json"
            json.dump(summary, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            self.perf._copy_out(p)
        except OSError:
            pass
        if not self._log_was_on:
            self.perf.stop_log()
        if self._held is not None:
            g.input.held = self._held
        self.perf.bench = None
        from src.scene.bench_result import BenchResultScene
        g.scenes.push(BenchResultScene(g, summary))

    # ── 매 프레임 ──
    def frame(self, frame_time: float) -> None:
        self.frames.append(frame_time * 1000)

    def second(self, row: dict) -> None:
        self.rows.append(row)

    def update(self, dt: float) -> None:
        if self.done:
            return
        self.t += dt
        self.game.guide.abort()   # 대본 중 튜토리얼(환상 첫 만남 등)이 떠서 화면을 어둡게 하지 않게 — abort 는 비워 둔 행동 목록도 되돌림
        try:
            self._step(dt)
        except Exception:   # 벤치마크 대본이 깨져도 게임은 계속 — 그 장면은 건너뜀
            import traceback
            print("bench:", self.tag(), "대본 오류")
            traceback.print_exc()
            self.t = self.secs
        if self.t >= self.secs:
            self._close_bench()
            self._next()

    def _close_bench(self) -> None:
        fr = self.frames
        n = max(1, len(fr))
        el = max(1e-6, sum(fr) / 1000)   # 실제로 프레임에 쓴 시간 (대본이 일찍 끝내도 fps 가 어긋나지 않게)
        r = {"bench": self.tag(), "name": BENCHES[self.i][1], "frames": len(fr), "secs": round(el, 1), "fps": round(n / el, 1),
             "frame_ms": round(sum(fr) / n, 2), "frame_p95": round(_p95(fr), 2), "frame_max": round(max(fr) if fr else 0, 2),
             "draw_ms": round(sum(x["draw_ms"] for x in self.rows) / max(1, len(self.rows)), 2),
             "logic_ms": round(sum(x["logic_ms"] for x in self.rows) / max(1, len(self.rows)), 2),
             "present_ms": round(sum(x["present_ms"] for x in self.rows) / max(1, len(self.rows)), 2),
             "particles_max": max((x["particles"] for x in self.rows), default=0),
             "rss_mb": max((x["rss_mb"] for x in self.rows), default=0)}
        if "stall_ms" in self.marks:
            r["stall_ms"] = round(self.marks["stall_ms"], 1)
        self.results.append(r)
        self._teardown()

    def _next(self) -> None:
        self.i += 1
        self.t, self.frames, self.rows, self.marks = 0.0, [], [], {}
        if self.i >= len(BENCHES):
            self._finish()
            return
        g, fs = self.game, self.fs
        g.scenes.stack[:] = [fs]
        fs.card = None
        fs.help = False
        self._fresh_spot("reservoir", 12.0, "clear")
        getattr(self, "_setup_" + self.tag())()

    def _teardown(self) -> None:
        fs = self.fs
        self._reel = False
        try:
            if fs.fight is not None:
                fs.fight = None
            fs.catch_show = None
            fs.landing = None
            fs.bite.stop()
            fs.cast.reset()
            fs.phantom_fx.clear()
            self.game.boss.stop(0)
        except Exception:
            pass

    # ── 공통 ──
    def _fresh_spot(self, spot: str, hour: float, weather: str) -> None:
        fs = self.fs
        fs._set_spot(spot)
        fs.clock.hour = hour
        ws = fs.weather_sys
        ws.set_spot(spot, fs.spot["weather"])
        now = ws.abs_time(fs.clock.day, hour)
        ws.set_override(weather, now, now + 24)   # 측정 동안 그 날씨로 고정
        ws.update(fs.clock.day, hour)
        ws.events.clear()
        fs.bite.stop()
        fs.cast.reset()

    def _fight_with(self, fish_id: str) -> None:
        from src.fishing.casting import CastState
        fs = self.fs
        fish = next(f for f in fs.all_fish if f["id"] == fish_id)
        fs.bite.fish = copy.deepcopy(fish)
        fs.bite.cast_distance = 20
        fs.cast.state = CastState.HOOKED
        fs._start_fight()

    def _common_of(self, spot: str) -> str:
        fs = self.fs
        lst = [f for f in fs.all_fish if f["spot"] == spot and f["rarity"] == "common"]
        return (lst or [f for f in fs.all_fish if f["spot"] == spot])[0]["id"]

    def _auto_reel(self) -> None:
        """입력 없이도 파이팅이 이어지게: 장력이 낮으면 감고, 빨강이면 놓는다."""
        f = self.fs.fight
        if f is None or f.phase != "fight":
            return
        self._reel = f.zone() != "red"

    def _step(self, dt: float) -> None:
        getattr(self, "_step_" + self.tag(), lambda dt: None)(dt)

    # ── B1 ──
    def _setup_B1(self) -> None:
        pass

    # ── B2 ──
    def _setup_B2(self) -> None:
        self._fresh_spot("breakwater", 22.0, "storm")
        self._fight_with(self._common_of("breakwater"))

    def _step_B2(self, dt: float) -> None:
        f = self.fs.fight
        if f is None or f.phase in ("caught", "lost"):
            self.marks["t_restart"] = self.marks.get("t_restart", 0.0) + dt
            if self.marks["t_restart"] > 1.5:
                self.marks["t_restart"] = 0.0
                self._teardown()
                self._fight_with(self._common_of("breakwater"))
            return
        self._auto_reel()

    # ── B3 ──
    def _setup_B3(self) -> None:
        from src.fishing.casting import CastState
        fs = self.fs
        fs.force_phantom = True
        fs.cast.state = CastState.LANDED
        fs.cast.bx, fs.cast.bz = 0.0, 18.0
        fs._splash()   # 착수 → 환상 파장 (33-5)
        self.marks["stage"] = "bloom"

    def _step_B3(self, dt: float) -> None:
        from src.fishing.bite import BiteState
        fs = self.fs
        st = self.marks.get("stage")
        if st == "bloom":
            if fs.bite.state == BiteState.BITE and not fs.phantom_fx.locked():
                fs._left_click()   # 챔질
                if fs.fight is not None:
                    self.marks["stage"] = "fight"
        elif st == "fight":
            self._auto_reel()
            f = fs.fight
            if f is None:
                self.marks["stage"] = "done"
            elif self.t >= self.secs * 0.6 and f.phase == "fight":
                f._caught()   # 포획 → 환상의 노래 · 연출
                self.marks["stage"] = "show"
        elif st == "show":
            if fs.catch_show is None and fs.fight is None:
                self.marks["stage"] = "done"

    # ── B4 ──
    def _setup_B4(self) -> None:
        from src.fishing.bite import BiteState
        fs = self.fs
        fish = next(f for f in fs.all_fish if f["id"] == "golden_carp")
        fs.bite.fish = copy.deepcopy(fish)
        fs.bite.legend = True
        fs.bite.state = BiteState.APPROACH   # 다가오는 동안 곡 미리 불러오기 시작
        self.marks["stage"] = "approach"

    def _step_B4(self, dt: float) -> None:
        fs = self.fs
        st = self.marks.get("stage")
        if st == "approach" and self.t >= 4.0:
            self.marks["win"] = []
            self._fight_with("golden_carp")
            self.marks["stage"] = "start"
            self.marks["t0"] = self.t
        elif st == "start":
            self.marks["win"].append(self.frames[-1] if self.frames else 0.0)
            if self.t - self.marks["t0"] >= 3.0:
                self.marks["stall_ms"] = max(self.marks["win"])
                self.marks["stage"] = "fight"
            self._auto_reel()
        elif st == "fight":
            self._auto_reel()
            if fs.fight is None or fs.fight.phase in ("caught", "lost"):
                self.marks["stage"] = "end"
                self.t = self.secs   # 파이팅이 끝나면 이 장면도 끝

    # ── B5 ──
    def _setup_B5(self) -> None:
        from src.scene.village import VillageScene
        sc = VillageScene(self.game, self.fs, "sharmion")
        self.game.scenes.push(sc)
        self.marks["village"] = sc

    def _step_B5(self, dt: float) -> None:
        sc = self.marks["village"]
        if self.game.scenes.current is sc:
            sc.ox = (sc.width - sc.game.screen.width) * (0.5 - 0.5 * math.cos(self.t * 0.6)) if sc.width > sc.game.screen.width else 0
            if 0.6 * self.secs <= self.t < 0.6 * self.secs + dt * 1.5 and not self.marks.get("entered"):
                self.marks["entered"] = True
                try:
                    sc.enter("haru")
                except Exception as e:
                    print("bench B5 enter:", e)
        elif self.t >= 0.85 * self.secs and not self.marks.get("left"):
            self.marks["left"] = True
            self.game.scenes.stack[:] = [self.fs, sc]

    # ── B6 ──
    def _setup_B6(self) -> None:
        from src.scene.shop import ShopScene
        self.game.scenes.push(ShopScene(self.game, self.fs))
        self.marks["t_scroll"] = 0.0

    def _step_B6(self, dt: float) -> None:
        from src.platform.input import Action
        g = self.game
        self.marks["t_scroll"] += dt
        if self.t >= self.secs / 2 and not self.marks.get("dex"):
            self.marks["dex"] = True
            from src.scene.dex import DexScene
            g.scenes.stack[:] = [self.fs]
            g.scenes.push(DexScene(g, self.fs))
        if self.marks["t_scroll"] >= 0.4:
            self.marks["t_scroll"] = 0.0
            sc = g.scenes.current
            n = self.marks.get("n", 0)
            self.marks["n"] = n + 1
            if self.marks.get("dex"):
                fishes = sc.spot_fish()
                if fishes:
                    sc.sel = n % len(fishes)
                if n % 12 == 0 and sc.tabs.labels:
                    sc.tabs.index = (sc.tabs.index + 1) % len(sc.tabs.labels)
                    sc.sel = 0
            else:
                sc.handle_action(Action("scroll", -1 if (n // 10) % 2 == 0 else 1))
