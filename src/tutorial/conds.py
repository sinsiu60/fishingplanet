"""가이드 조건: 시작 조건(need_cond)·단계 조건(cond:/input:)·정지 단계에서 통과시킬 조작·조작 그림 (TUTORIAL.md 3·4번)."""
import math

# 스토리 장면 (이게 떠 있으면 튜토리얼은 대기열에서 기다림)
STORY_SCENES = {"CutsceneScene", "SubtitleScene", "ChoiceScene", "EpilogueScene", "PaperScene", "NameInputScene",
                "PhantomIntroScene", "TravelScene", "EndingScene", "VoyageScene", "StoryDebugScene"}
# 잠깐 끼어드는 화면 (가이드가 숨고 입력도 그대로 통과)
ASIDE_SCENES = {"PauseScene", "SettingsScene", "ConfirmScene", "SaveTransferScene", "TutorialReplayScene",
                "TutorialDebugScene"}

INPUT_DELAY = 0.45   # 정지 직후 이미 누르고 있던 입력으로 바로 넘어가지 않게


def _cur_name(game) -> str:
    cur = game.scenes.current
    return type(cur).__name__ if cur is not None else ""


def story_busy(game) -> bool:
    name = _cur_name(game)
    if name in STORY_SCENES:
        return True
    cur = game.scenes.current
    if cur is not None and hasattr(cur, "tut_busy") and cur.tut_busy():
        return True   # 건물 안 대화 진행 중 · 전설·환상 포획 연출 등
    return False


def aside(game) -> bool:
    return _cur_name(game) in ASIDE_SCENES or story_busy(game)


def _fishing(game):
    for sc in reversed(game.scenes.stack):
        if type(sc).__name__ == "FishingScene":
            return sc
    return None


# ── 조건 ──
def check(game, name: str, run) -> bool:
    save = game.save
    if save is None:
        return False
    d = save.data
    if name == "new_game":
        return d["stats"]["catches"] == 0 and not d["dex"]
    if name == "any_pattern_done":
        return any(t.startswith("TG-P") for t in d.get("tutorial", {}).get("done", []))
    if name == "has_fish":
        return bool(d["keepnet"])
    if name == "has_materials":
        return sum(d.get("materials", {}).values()) > 0
    if name == "second_fishing":
        return d["stats"]["catches"] >= 1
    if name == "c402_done":
        from src.story import story
        return story.seen(save, "C4-02")
    if name == "float_owned":
        return bool(d.get("float", {}).get("owned"))
    if name == "float_equipped":
        return bool(d.get("float", {}).get("equipped"))
    # 화면 상태 (도감·상점이 tut_cond 로 대답)
    for sc in reversed(game.scenes.stack):
        if hasattr(sc, "tut_cond"):
            v = sc.tut_cond(name)
            if v is not None:
                return bool(v)
    return False


# ── 정지 단계 조작 ──
ALLOWED = {
    "hook": ["primary"],
    "jerk": ["primary", "reel_tap"],
    "reel": ["primary", "reel_tap"],
    "release": [],
    "lower": ["secondary"],
    "drag_down": ["drag:-1"],
    "drag_min": ["drag:-1"],
    "mash": ["primary", "reel_tap"],
    "up": [], "down": [], "turn": ["flick"], "circle": [],
}


def allowed_actions(until: str, run) -> list[str]:
    kind, _, arg = until.partition(":")
    if kind == "input":
        return ALLOWED.get(arg, [])
    ex = (run or {}).get("ctx", {}).get("allow")
    return list(ex) if ex else []


def passed(run, *names) -> bool:
    return any(n in run["ctx"].get("passed", []) for n in names)


def input_ok(game, arg: str, run) -> bool:
    if run["t"] < INPUT_DELAY:
        return False
    inp = game.input
    if arg in ("hook",):
        return passed(run, "primary")
    if arg == "jerk":
        return passed(run, "primary", "reel_tap")
    if arg == "reel":
        return inp.held("reel")
    if arg == "release":
        return not inp.held("reel") and not inp.held("press")
    if arg == "lower":
        return passed(run, "secondary")
    if arg == "drag_down":
        return passed(run, "drag:-1")
    if arg == "drag_min":
        return inp.held("drag_min")
    if arg in ("up", "down"):
        p = inp.rod_pitch()
        return p is not None and (p > 0.45 if arg == "up" else p < -0.45)
    if arg == "turn":
        want = run["ctx"].get("dir", 0)
        if passed(run, "flick:-1") and want <= 0 or passed(run, "flick:1") and want >= 0:
            return True
        aim = inp.aim_override(True)
        if aim is None:
            w = game.screen.width
            aim = (inp.pointer[0] - w / 2) / (w * 0.3)
        return aim * (want or (1 if aim > 0 else -1)) > 0.55
    if arg == "mash":
        need = run["ctx"].get("mash_need", 6)
        n = sum(1 for p in run["ctx"].get("passed", []) if p in ("primary", "reel_tap"))
        run["ctx"]["mash_n"] = n
        return n >= need
    if arg == "circle":
        return _circle(game, run)
    return False


def _circle(game, run) -> bool:
    """손가락·마우스가 한 바퀴(누적 각도 2π) 돌면 성공."""
    smp = game.input.circle_sample(10)
    ctx = run["ctx"]
    if smp is None:
        return False
    pos, center, min_r = smp
    if center is None:   # PC: 최근 위치들의 평균을 중심으로
        hist = ctx.setdefault("c_hist", [])
        hist.append(pos)
        del hist[:-40]
        center = (sum(p[0] for p in hist) / len(hist), sum(p[1] for p in hist) / len(hist))
    dx, dy = pos[0] - center[0], pos[1] - center[1]
    if math.hypot(dx, dy) < min_r:
        return False
    a = math.atan2(dy, dx)
    prev = ctx.get("c_prev")
    ctx["c_prev"] = a
    if prev is not None:
        d = (a - prev + math.pi) % math.tau - math.pi
        ctx["c_acc"] = ctx.get("c_acc", 0.0) + d
    ctx["circle_k"] = min(1.0, abs(ctx.get("c_acc", 0.0)) / math.tau)
    return abs(ctx.get("c_acc", 0.0)) >= math.tau


# ── 그림 ──
ANIM = {"hook": "tap", "jerk": "tap", "reel": "hold", "release": "release", "lower": "right", "drag_down": "key_q",
        "drag_min": "key_shift", "up": "swipe_u", "down": "swipe_d", "mash": "mash", "circle": "circle"}


def anim_of(game, until: str, run) -> str | None:
    over = run["ctx"].get("anim")
    if over:
        return over
    kind, _, arg = until.partition(":")
    if kind != "input":
        return None
    if arg == "turn":
        return "swipe_l" if run["ctx"].get("dir", -1) < 0 else "swipe_r"
    return ANIM.get(arg)


# 터치에서 조작 그림을 올릴 버튼 (touch_ui 의 버튼 id)
TOUCH_BTN = {"right": ("dip", "retrieve"), "key_q": ("drag_down",), "key_shift": ("drag_down",), "hold": ("pad",),
             "mash": ("pad",), "circle": ("pad",), "swipe_l": ("pad",), "swipe_r": ("pad",), "swipe_u": ("pad",),
             "swipe_d": ("pad",), "release": ("pad",)}


def anim_pos(game, s: dict, run, rects) -> tuple[int, int]:
    how = anim_of(game, s["until"], run)
    if game.input.kind == "touch":
        fs = _fishing(game)
        if fs is not None and how in TOUCH_BTN and fs.fight is not None:
            for c in getattr(game.input, "controls", []):
                if c.id in TOUCH_BTN[how]:
                    return c.rect.center
    W = game.screen.width
    if rects:   # 대상 옆 (안내 상자는 위·아래에 놓이므로)
        r = rects[0]
        x = r.right + 18 if r.right + 30 < W else r.left - 18
        return x, r.centery
    return W // 2, game.screen.height // 2


def dynamic_text(game, s: dict, run) -> str | None:
    if run is None:
        return None
    return run["ctx"].get("text")
