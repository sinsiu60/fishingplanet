"""TUTORIAL.md → data/tutorials.json · data/tutorial_inputs.json (DESIGN.md 40). 다시 만들기: python tools/tutorial_build.py

문구는 TUTORIAL.md 표의 '문구' 칸 / 큰따옴표 안 글자를 한 글자도 바꾸지 않고 옮긴다 (**굵게** = 노랑, {이름} = 조작 이름).
게임 쪽 정보(강조 대상 ID, 넘어가는 조건, 시작 조건, 대본 물고기)는 이 파일의 표(SPEC)에서 붙인다.

넘어가는 조건 (until)
  tap                       화면 아무 곳 (설명·정지 지시의 '탭')
  event:<이름>              게임이 알려 주는 일 (game.guide.event)
  scene:<장면 클래스>        그 화면이 맨 위에 열림
  closed:<장면 클래스>       그 화면이 닫힘
  input:<조작>              정지 지시에서 그 조작 (reel·release·hook·drag_down·drag_up·drag_min·lower·left·right·up·down·mash·circle·jerk·cast)
  cond:<이름>               src/tutorial/conds.py 의 판정
  auto:<초>                 그 시간이 지나면 (결과 문구)
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "TUTORIAL.md")
OUT = os.path.join(ROOT, "data", "tutorials.json")
OUT_IN = os.path.join(ROOT, "data", "tutorial_inputs.json")

KIND = {"설명": "info", "강조": "spotlight", "정지 지시": "freeze", "대기": "wait"}


def md() -> str:
    return open(SRC, encoding="utf-8").read()


def section(text: str, head: str) -> str:
    i = text.index(head)
    m = re.search(r"\n## |\n# |\n---", text[i + len(head):])
    return text[i: i + len(head) + (m.start() if m else len(text))]


def rows(block: str, header_start: str) -> list[list[str]]:
    out, on = [], False
    for ln in block.split("\n"):
        if ln.startswith(header_start):
            on = True
            continue
        if on:
            if not ln.startswith("|"):
                if out:
                    break
                continue
            cells = [c.strip() for c in ln.strip().strip("|").split("|")]
            if set(cells[0]) <= set("-: "):
                continue
            out.append(cells)
    return out


def quoted(cell: str) -> list[str]:
    """문구만 (바로 뒤에 '탭 강조'·'버튼 강조'·'강조' 가 붙은 것은 화면 이름이라 뺀다)."""
    out = []
    for m in re.finditer(r'"([^"]+)"', cell):
        if re.match(r"\s*(?:탭|버튼)?\s*강조", cell[m.end():]):
            continue
        out.append(m.group(1))
    return out


# ── 게임 쪽 정보 (단계 순서대로: (강조 대상, 넘어가는 조건[, 덧붙임])) ──
SPEC = {
    "TG-01": {"title": "첫 캐스팅 · 챔질", "who": "haru", "start": "event:spot_enter:reservoir", "need_cond": "new_game",
              "script": "tg01_bite", "next": "TG-02",
              # 물고기 행동: 착수 4초 뒤 가짜 입질(톡톡) 1번 → 3초 뒤 진짜 입질(쑥) — 대기 1.5 + 접근 2.0 + 0.5 = 4초
              "fish": {"bite": {"fish": "crucian", "wait": 1.5, "approach": 2.0, "first_nibble": 0.5, "nibbles": 1,
                                "gap": 3.0}},
              "steps": [("fish.water", "tap"), ("fish.water", "event:cast_landed", {"allow": "cast"}),
                        ("fish.bobber", "event:nibble"), ("fish.bobber", "tap"), ("fish.bobber", "event:bite"),
                        ("fish.bobber", "input:hook")]},
    "TG-02": {"title": "첫 파이팅", "who": "haru", "start": "event:fight_start", "after": ["TG-01"], "script": "tg02_fight",
              "next": "TG-03",
              # 물고기 행동: 붕어, 패턴 없이 시작 → 장력이 빨간 칸까지 오르게 조금 세게 → 지침 → 거리 0
              "fish": {"fight": {"fish": "crucian", "red_pull_max": 45, "red_pull_rate": 18, "tired_after_green": 1.5}},
              "steps": [(["fight.gauge.tension", "fight.gauge.line"], "tap"), ("fight.gauge.line", "tap"),
                        ("fight.reel", "input:reel"), ("fight.gauge.tension", "event:tension_red"),
                        ("fight.gauge.tension.red", "input:release"), ("fight.gauge.tension", "event:tired"),
                        (["fight.fish", "fight.slot.reel"], "input:reel"), ("fight.distance", "event:net_phase"),
                        (["fight.fish", "fight.net"], "input:hook")]},
    "TG-03": {"title": "첫 포획 결과", "who": "haru", "start": "event:catch_shown", "after": ["TG-02"], "next": "TG-04",
              "steps": [("catch.card", "tap"), ("catch.size", "tap"), ("catch.rank", "tap"),
                        ("catch.dex_new", "tap", {"on_done": "close_catch"})]},
    "TG-04": {"title": "도감", "who": "haru", "start": "event:tg_done:TG-03", "after": ["TG-03"],
              "on_done": "goal_sell",
              "steps": [("dex.open", "scene:DexScene", {"allow_keys": ["menu:dex"]}), ("dex.tabs", "tap"),
                        ("dex.cards.unknown", "tap"), ("dex.card.first", "cond:dex_sel_first"),
                        ("dex.detail.name", "tap"), ("dex.detail.habitat", "tap"), ("dex.detail.records", "tap"),
                        ("dex.detail.stars", "tap"), ("dex.detail.mastery", "tap"), ("dex.detail.unlocks", "tap"),
                        ("dex.boss", "tap"), (["dex.spot_stars", "dex.btn.stars"], "tap"), ("dex.close", "closed:DexScene")]},
    "TG-05": {"title": "패턴 사전", "who": "haru", "start": "event:dex_open", "need_cond": "any_pattern_done", "after": ["TG-04"],
              "steps": [("dex.btn.patterns", "cond:dex_patterns"), ("dex.patterns", "tap")]},
    "TG-06": {"title": "판매", "who": "haru", "start": "event:interior_ready:haru", "after": ["TG-04"], "need_cond": "has_fish",
              "next": "TG-07",
              "steps": [("interior.portrait", "tap"), ("interior.menu.sell", "cond:shop_sell"), ("shop.list", "tap"),
                        ("shop.row.first", "cond:shop_sel_first"), ("shop.detail.calc", "tap"), ("shop.btn.lock", "tap"),
                        ("shop.btn.sell", "event:sold"), ("shop.money", "tap"), ("shop.btn.bulk", "tap",
                                                                                  {"on_done": "shop_to_buy"})]},
    "TG-07": {"title": "구매", "who": "haru", "start": "event:tg_done:TG-06", "after": ["TG-06"], "on_done": "goal_baek",
              "steps": [("shop.tab.rod", "cond:shop_tab_rod"), ("shop.list.tier", "tap"), ("shop.row.glass", "cond:shop_sel_glass"),
                        ("shop.detail.compare", "tap"), ("shop.detail.price", "tap"), ("shop.tabs.gear", "tap"),
                        ("shop.close", "closed:ShopScene")]},
    # TG-12 비늘석 (SCALESTONE.md, DESIGN 46장 S5): 'TG-12 강화' 교체. 시작 = 비늘석을 얻은 뒤 하루네 낚시점 입장 (강화할 수 있을 때)
    "TG-12": {"title": "비늘석", "who": "haru", "start": "event:interior_ready:haru", "need_cond": "scalestone_tg12",
              "after": ["TG-07"],
              "steps": [("interior.menu.scalestone", "cond:shop_tab_scalestone"), ("ss.slots", "tap"),
                        ("ss.list.first", "cond:ss_sel"), ("ss.detail.opts", "tap"), ("ss.btn.enhance", "event:ss_enhanced"),
                        ("ss.detail.newopt", "tap"), (["ss.btn.equip", "ss.slots"], "event:ss_equipped"), ("ss.btn.totals", "tap")]},
}

# 패턴 튜토리얼: (패턴 키, ① 강조, ② 강조, ② 조작) — 문구는 TG-P 표 (①②③)
PATTERNS = {   # 시작 신호, 패턴(대본 키)
    "TG-P1": ("telegraph:rush", "rush"),
    "TG-P2": ("telegraph:jump", "jump"),
    "TG-P3": ("telegraph:turn", "turn"),
    "TG-P4": ("action:charge", "charge"),
    "TG-P5": ("pattern:shake", "shake"),
    "TG-P6": ("pattern:dive", "dive"),
    "TG-P7": ("pattern:surface", "surface"),
    "TG-P8": ("pattern:reverse", "reverse"),
    "TG-P9": ("pattern:twist", "twist"),
    "TG-P10": ("pattern:chain", "chain"),
    "TG-P11": ("pattern:hide", "hide"),
    "TG-P12": ("pattern:pump", "pump"),
    "TG-P13": ("pattern:thrash", "thrash"),
    "TG-P14": ("pattern:bite", "bite"),
    "TG-P15": ("fake_tired", "fake"),
    "TG-P16": ("pattern:dual", "dual"),
}
# ② 대응 정지: (② 칸 안의 문구 — 원문 그대로 들어 있어야 함, 넘어가는 조건, 멈추는 순간)
#   멈추는 순간: rush 돌진 직전 / apex 점프 정점 / second 공중 몸부림 착수 직전 / turn 방향 전환 순간 /
#   action 행동 시작 / peek 숨기 고개 내밂 / gap0·gap1 펌핑 첫·둘째 박 사이 / charge_tired 힘 모으기 끝 지침 /
#   real_tired 가짜 지침 뒤 진짜 지침 / chain 콤보 행동마다 (그 행동의 순간)
PSTEPS = {
    "TG-P1": [("지금이에요! 줄을 풀어 주세요. {드랙내리기}", "input:drag_down", "rush")],
    "TG-P2": [("지금이에요! 링이 맞았어요. {숙이기}", "input:lower", "apex")],
    "TG-P3": [("지금이에요! 표시된 방향으로! {왼쪽}", "input:turn", "turn")],
    "TG-P4": [("지금이에요! 지친 틈에 감으세요! {감기}", "input:reel", "charge_tired")],
    "TG-P5": [("지금은 아무것도 하지 마세요! {손떼기}", "hold:shake", "action")],
    "TG-P6": [("지금이에요! 낚싯대를 세우세요! {위}", "input:up", "action")],
    "TG-P7": [("지금이에요! 낚싯대를 낮추세요! {아래}", "input:down", "action")],
    "TG-P8": [("지금이에요! 늘어진 줄을 빨리 감으세요! {연타}", "input:mash", "action")],
    "TG-P9": [("지금이에요! 꼬임을 풀어요! {원}", "input:circle", "action")],
    "TG-P10": [("첫 번째!", "chain", "chain")],
    "TG-P11": [("살짝 풀어서 안심시켜요. {드랙내리기}", "input:drag_down", "action"),
               ("나왔어요! 지금 감으세요! {감기}", "input:reel", "peek")],
    "TG-P12": [("지금! 박자 사이에 감으세요! {감기}", "input:reel", "gap0"),
               ("지금! 박자 사이에 감으세요! {감기}", "input:reel", "gap1")],
    "TG-P13": [("첫 번째 링! {숙이기}", "input:lower", "apex"), ("한 번 더! {숙이기}", "input:lower", "second")],
    "TG-P14": [("지금이에요! 줄을 순간 확 풀어요! {순간최저}", "input:drag_min", "action")],
    "TG-P15": [("지느러미가 멈췄어요. 진짜예요! 감으세요! {감기}", "input:reel", "real_tired")],
    "TG-P16": [("지금이에요! 두 개 다!", "dual", "action")],
}

# 다른 시스템 (TG-09~19, TG-PH — TG-08 루어 액션은 삭제): 큰따옴표 문구 순서대로 (강조, 조건[, 덧붙임])
OTHER = {
    "TG-09": {"title": "수면 징후", "who": "haru", "start": "event:sign_seen",
              "steps": [("freeze", "fish.signs", "tap"), ("spotlight", "fish.signs", "event:cast_landed", {"allow": "cast"})]},
    "TG-10": {"title": "보물상자", "who": "haru", "start": "event:chest_card", "need_cond": "catch_card",
              "steps": [("info", "catch.chest", "tap", {"on_done": "close_catch"}), ("spotlight", "chest.menu", "scene:ChestScene"),
                        ("spotlight", "chest.box", "event:chest_opened"), ("info", "chest.grade", "tap"),
                        ("info", "chest.pity", "tap")]},
    "TG-11": {"title": "의뢰 게시판", "who": "haru", "start": "event:quests_open",
              "steps": [("info", "quests.daily", "tap"), ("info", "quests.cond", "tap"), ("info", "quests.reward", "tap"),
                        ("info", "quests.refresh", "tap"), ("info", "quests.weekly", "tap")]},
    "TG-13": {"title": "어탁", "who": "haru", "start": "event:record_card", "need_cond": "catch_card",
              "steps": [("info", "catch.print_btn", "tap"), ("spotlight", "catch.print_btn", "event:print_made"),
                        ("wait", None, "auto:3")]},
    "TG-14": {"title": "주인공의 집", "who": "haru", "start": "event:home_ready",
              "steps": [("info", "home.menu.journal", "tap"), ("info", "home.menu.memories", "tap"),
                        ("info", "home.menu.notebook", "tap")]},
    "TG-15": {"title": "계절", "who": "haru", "start": "event:village_enter", "need_cond": "season_changed",
              "script": "season_panel",
              "steps": [("info", "village.season", "tap"), ("info", "village.season.fish", "tap")]},
    "TG-16": {"title": "날씨 이벤트", "who": "haru", "start": "event:weather_event",
              "steps": [("info", "village.sky", "tap"), ("info", "village.banner", "tap")]},
    "TG-17": {"title": "변이 물고기", "who": "haru", "start": "event:mutation_card", "need_cond": "catch_card",
              "steps": [("info", "catch.mutation", "tap"), ("info", "catch.mutation", "tap")]},
    "TG-18": {"title": "특수 찌", "who": "ella", "start": "event:interior_ready:ella", "need_cond": "c402_done",
              "script": "float_shop",
              "steps": [("spotlight", "shop.tab.float", "cond:shop_tab_float"), ("spotlight", "shop.row.paralysis_float",
                                                                                   "cond:shop_sel_paralysis"),
                        ("spotlight", "shop.btn.action", "cond:float_owned", {"short_text": 4}),
                        ("spotlight", "shop.btn.action", "cond:float_equipped"), ("wait", None, "auto:3")]},
    # TG-20 대형 물고기 (DESIGN 49-4): drag_floor 물고기 첫 파이팅 시작 — 줄이 반드시 닳는다 · 랭크 예외
    "TG-20": {"title": "대형 물고기", "who": "haru", "start": "event:first:heavy_fish",
              "steps": [("freeze", "fight.gauge.line", "tap"), ("freeze", "fight.gauge.tension", "tap"),
                        ("freeze", "fight.gauge.line", "tap")]},
    # 백 노인의 시험 (BAEK_EXAM 🅲-3, DESIGN 49-6): TG-EX1 ~ EX5 → TG-21 ~ 25. 이야기 튜토리얼(TG-07) 뒤로.
    "TG-21": {"title": "잠긴 장비", "who": "haru", "start": "event:exam_lock_seen", "need_cond": "exam_fresh",
              "after": ["TG-07"], "group": "exam",
              "steps": [("freeze", "shop.row.examlock", "tap"), ("freeze", "shop.row.examlock.label", "tap")]},
    "TG-22": {"title": "시험 안내", "who": "baek", "start": "event:interior_ready:baek", "need_cond": "exam_tg22",
              "after": ["TG-07"], "group": "exam",
              "steps": [("spotlight", "interior.menu.exam", "scene:ExamScene")]},
    "TG-23": {"title": "자격 읽기", "who": "baek", "start": "event:exam_open", "after": ["TG-07"], "script": "exam_quals",
              "group": "exam",
              "steps": [("freeze", "exam.qual.dex", "tap"), ("freeze", "exam.qual.stars", "tap"),
                        ("freeze", "exam.qual.owner", "tap"), ("freeze", "exam.fish", "tap")]},
    "TG-24": {"title": "첫 시험", "who": "haru", "start": "event:exam_spot", "after": ["TG-07"], "script": "exam_first",
              "group": "exam",
              "steps": [("freeze", "fish.exam_float", "tap", {"who": "baek"}), ("wait", "fish.bobber", "event:exam_end"),
                        ("freeze", "fish.menu.shop", "tap", {"alt_text": 3, "alt_target": "fish.clock"})]},
    "TG-25": {"title": "새 랭크", "who": "haru", "start": "event:catch_shown", "need_cond": "catch_card", "after": ["TG-03"],
              "group": "rank",
              "steps": [("freeze", "catch.rank_bars", "tap"), ("freeze", "catch.rank_bars.weak", "tap")]},
    # TG-26 자동 드랙 (CORE_UPDATE CU3-4): 옛 세이브만, 업데이트 뒤 첫 파이팅 — 장력 게이지 한 줄
    "TG-26": {"title": "자동 드랙", "who": "haru", "start": "event:fight_start", "need_cond": "drag_legacy",
              "steps": [("freeze", "fight.gauge.tension", "tap")]},
    "TG-PH": {"title": "환상의 물고기", "who": "baek", "start": "event:phantom_caught", "script": "phantom",
              "steps": [("info", "catch.card", "tap"), ("info", "catch.card", "tap", {"on_done": "close_catch"}),
                        ("spotlight", "dex.open", "scene:DexScene", {"allow_keys": ["menu:dex"]}),
                        ("spotlight", "dex.btn.phantom", "cond:dex_phantom"), ("info", "dex.phantom.count", "tap")]},
}
GIMMICKS = [("tangle", "갈대 엉킴"), ("dark", "어둠"), ("current", "물살"), ("heat", "열 손상"), ("ice", "얼음 구멍")]


def build() -> tuple[dict, dict]:
    text = md()
    # ── 조작 이름 ──
    inputs = {}
    for c in rows(section(text, "## 3. 조작 이름"), "| 이름 | PC | 모바일 |"):
        names = re.findall(r"`\{([^}]+)\}`", c[0])
        if len(names) == 2:   # {왼쪽} / {오른쪽}
            pc = c[1]
            mo = c[2]
            for i, nm in enumerate(names):
                arrow = ("←", "→")[i] if "←" in pc else ("↑", "↓")[i]
                inputs[nm] = {"pc": pc.replace("← / →", arrow).replace("↑ / ↓", arrow),
                              "mobile": mo.replace("← / →", arrow).replace("↑ / ↓", arrow)}
        else:
            inputs[names[0]] = {"pc": c[1], "mobile": c[2]}
    tuts = {}
    # ── 표 형식 (TG-01~07) ──
    for tid, sp in SPEC.items():
        block = section(text, f"## {tid} ")
        rs = rows(block, "| 단계 |")
        if len(rs) != len(sp["steps"]):
            raise SystemExit(f"{tid}: 단계 수 {len(rs)} ≠ SPEC {len(sp['steps'])}")
        steps = []
        for cells, st in zip(rs, sp["steps"]):
            has_expr = len(cells) >= 6
            step = {"kind": KIND[cells[1]], "target": st[0], "text": cells[3],
                    "expr": cells[4] if has_expr else None, "until": st[1]}
            if len(st) > 2:
                step.update(st[2])
            steps.append(step)
        tuts[tid] = {k: v for k, v in sp.items() if k != "steps"} | {"steps": steps}
    # ── 패턴 (TG-P1~P16) ──
    prow = rows(section(text, "## 패턴별 문구"), "| ID | 패턴 |")
    for cells in prow:
        tid = cells[0]
        key, pat = PATTERNS[tid]
        tgt = ["fight.fish", "fight.slots"]
        steps = [{"kind": "freeze", "target": tgt, "text": cells[2], "until": "tap"}]
        for txt, until, at in PSTEPS[tid]:
            if txt not in cells[3].replace("\"", ""):
                raise SystemExit(f"{tid}: ② 문구가 원문에 없음: {txt}")
            steps.append({"kind": "freeze", "target": tgt, "text": txt, "until": until, "at": at})
        steps.append({"kind": "wait", "target": None, "text": cells[4], "until": "auto:1.5"})
        extra = {}
        q = quoted(cells[3])
        if tid == "TG-P10":
            extra["chain_texts"] = q[:3]               # "첫 번째!", "두 번째!", "마지막!"
        if tid == "TG-P5":
            extra["hold_text"] = q[0]                   # "참는 중…"
            extra["again_text"] = "손을 떼세요!"        # 4번 아래 설명 원문
            if extra["again_text"] not in text:
                raise SystemExit("TG-P5: '손을 떼세요!' 원문 없음")
        if tid == "TG-P8":
            m = re.search(r"0/(\d+)", cells[3])
            extra["mash_need"] = int(m.group(1))
        tuts[tid] = {"title": cells[1], "who": "haru", "start": f"event:first:{key}", "pattern": pat,
                     "script": "pattern", "no_ok": True, "steps": steps} | extra
    # ── 다른 시스템 ──
    orow = {re.sub(r"\*\*", "", c[0]).split(" ")[0]: c for c in
            rows(section(text, "# 🧭 [다른 시스템 튜토리얼 개편]"), "| ID | 시작 |")}
    for tid, sp in OTHER.items():
        cells = orow[tid]
        qs = quoted(cells[3])
        if tid == "TG-PH":
            ph = phantom_paragraphs()
            qs = ph + qs
        if tid == "TG-18":
            # ③ 돈이 모자랄 때 문구는 따로 (short_text)
            qs = qs[:3] + qs[4:]
            short = quoted(cells[3])[3]
        alt = None
        if tid == "TG-24":
            # ③ 불합격일 때 문구는 따로 (alt_text, 강조 대상 alt_target)
            alt = qs[3]
            qs = qs[:3]
        if len(qs) != len(sp["steps"]):
            raise SystemExit(f"{tid}: 문구 {len(qs)}개 ≠ 단계 {len(sp['steps'])} — {qs}")
        steps = []
        for q, st in zip(qs, sp["steps"]):
            step = {"kind": st[0], "target": st[1], "text": q, "expr": None, "until": st[2]}
            if len(st) > 3:
                step.update(st[3])
            if step.get("short_text"):
                step["short_text"] = short
            if step.get("alt_text"):
                step["alt_text"] = alt
            steps.append(step)
        tuts[tid] = {k: v for k, v in sp.items() if k != "steps"} | {"steps": steps}
    # TG-19 환경 기믹 5종: "이름 "문구"" 짝
    cell = orow["TG-19"][3]
    for gid, name in GIMMICKS:
        m = re.search(re.escape(name) + r' "([^"]+)"', cell)
        tuts[f"TG-19:{gid}"] = {"title": f"환경 기믹: {name}", "who": "ella", "start": f"event:first:gimmick:{gid}",
                                "steps": [{"kind": "freeze", "target": f"fight.gimmick.{gid}", "text": m.group(1),
                                           "expr": None, "until": "tap"}]}
    return tuts, inputs


def phantom_paragraphs() -> list[str]:
    """PHANTOM_FISH.md 6번 튜토리얼 문구 1~2문단 (그대로, 2단계)."""
    t = open(os.path.join(ROOT, "PHANTOM_FISH.md"), encoding="utf-8").read()
    blk = section(t, "## 6. 첫 포획 튜토리얼")
    quote = [ln[1:].strip() for ln in blk.split("\n") if ln.startswith(">")]
    paras, cur = [], []
    for ln in quote[1:]:      # 첫 줄 제목 '방금 낚은 물고기를 보셨나요?' 다음부터
        if not ln:
            if cur:
                paras.append(" ".join(cur))
                cur = []
        else:
            cur.append(ln)
    if cur:
        paras.append(" ".join(cur))
    return paras[:2]


def apply_voice(tuts: dict) -> None:
    """하루 아저씨 말투 (data/tutorial_voice.json, 사용자 요청): who=haru 문구를 하루 말투로. 원문은 src* 로 남겨 검사.
    + 사용자 요청으로 넣은 단계 (TG-02 뜰채 설명: 물고기가 퍼덕이는 동안 → 멈추는 순간 '지금이야!')."""
    v = json.load(open(os.path.join(ROOT, "data", "tutorial_voice.json"), encoding="utf-8"))
    hv = v["haru"]
    bv = v.get("baek", {})   # 백 노인 말투 (시험 튜토리얼 TG-22 ~ 24, 49-6) — 표에 있는 문구만 (TG-PH 는 PHANTOM_FISH.md 원문 그대로)
    for tid, t in tuts.items():
        for s in t["steps"]:
            who = s.get("who") or t.get("who")
            if who == "baek":
                for key in ("text",):
                    if key in s and s[key] in bv:
                        s["src_" + key], s[key] = s[key], bv[s[key]]
        if t.get("who") != "haru":
            continue
        for s in t["steps"]:
            if (s.get("who") or "haru") != "haru":
                continue
            for key in ("text", "short_text", "alt_text"):
                if key in s:
                    if s[key] not in hv:
                        raise SystemExit(f"{tid}: 하루 말투 표에 없음: {s[key]}")
                    s["src_" + key], s[key] = s[key], hv[s[key]]
        if "chain_texts" in t:
            t["src_chain_texts"], t["chain_texts"] = t["chain_texts"], [hv[x] for x in t["chain_texts"]]
        for key in ("hold_text", "again_text"):
            if key in t:
                t["src_" + key], t[key] = t[key], hv[t[key]]
    # TG-02 뜰채: 마지막 '지금이야! 뜰채로 건져!' 앞에 설명 단계 (게임은 흐르고, 물고기가 처음 멈추는 순간 넘어감)
    steps = tuts["TG-02"]["steps"]
    steps.insert(len(steps) - 1, {"kind": "wait", "target": ["fight.fish", "fight.net"], "text": v["added"]["TG-02:net_wait"],
                                  "expr": "happy", "until": "cond:net_still", "added": True})


def main() -> None:
    tuts, inputs = build()
    apply_voice(tuts)
    data = {"_설명": "튜토리얼 (TUTORIAL.md 원문 그대로, tools/tutorial_build.py 가 만듦 — 손으로 고치지 말 것). DESIGN.md 40.",
            "tutorials": tuts}
    json.dump(data, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump({"_설명": "조작 이름 (TUTORIAL.md 3번 표). 문구의 {이름} 을 기기에 맞게 바꾼다.", "inputs": inputs},
              open(OUT_IN, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("ok", len(tuts), "tutorials,", len(inputs), "inputs")


if __name__ == "__main__":
    sys.path.insert(0, ROOT)
    main()
