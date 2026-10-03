"""물고기 패턴 상태머신 = 보스 AI. 종마다 fish.json 값으로 성격이 달라진다.

격렬 사이클:  idle ⇄ (telegraph → 행동) 반복, 행동마다 burst 소모
burst가 바닥나면: tired(지침, 빈틈) → recover(회복) → 다시 격렬
stamina가 0이면: exhausted (끝까지 저항 거의 없음)

모든 행동 앞에는 예고(telegraph)가 있다. (DESIGN.md 0장 공정함 규칙 1)
  rush  ← 꼬리 물보라
  jump  ← 그림자 커짐 + 기포 (정점에 우클릭)
  leap  ← 그림자 커짐 + 한쪽으로 튀는 물보라 (몸털기 점프: 정점에 반대쪽으로 슬라이드)
  turn  ← 줄 쏠림
  charge(힘 모으기)는 "멈춤" 자체가 신호이며, 끝나면 예고 후 돌진한다.

종별 특성 (fish.json):
  jump_chain [min,max]  연속 점프 (다음 점프 예고는 짧게, 최소 0.35초)
  turn_chain [min,max]  연속 방향 전환 (좌우 번갈아)
  combo {행동: [다음 행동, 확률]}  행동 직후 짧은 예고로 이어지는 콤보
  cover_bias 0~1        방향 전환·돌진을 수초/바위 쪽으로 할 확률
  charge_rush_mult      힘 모으기 뒤 돌진의 힘 배율
  fake_tired 0~1        지칠 때 '가짜 지침'일 확률 (단서: 기포가 계속 올라옴)
  ink 0~1               돌진 후 먹물을 뿜을 확률 (그림자 신호를 가림)
  first_rush {power_mult, sec, telegraph_sec, burst_after}
                        챔질 직후 강한 첫 돌진 (예고 있음). 끝나면 burst를 깎아 빨리 지친다 (가물치)
  fake_cue 0~1          행동 대신 '가짜 예고(lure)'를 보낼 확률: 그림자가 부풀고 등불이 번쩍이지만
                        기포·판정 원이 없고 아무 일도 일어나지 않는다 (초롱아귀). 진짜 점프는 기포 + 판정 원
  sound_only            그림자·행동 아이콘·화면 연출 없이 소리로만 예고 (안개잉어). dark를 포함한다
  phase_at [..]         페이즈 전환 체력 비율 (없으면 전설 공통값). 미니보스(비늘왕)도 phases를 쓴다

전설 (phases): 체력 비율이 phase_at 아래로 떨어지면 다음 페이즈 값으로 덮어쓴다.
  전환 순간에는 잠깐 행동을 멈춘다 (숨 돌릴 틈). 추가 필드:
  dark            그림자 신호가 사라짐 (줄·소리로 읽기)
  lightning_cue   점프 예고마다 번개가 친다 (번개 = 박자)
  jump_height_m   점프 높이 (꼬리 연타는 낮게)
  dragon          용으로 변신 (연출)

신규 패턴 (Phase U3, data/patterns.json · DESIGN.md 27-2): actions에 넣으면 예고 → 패턴 상태 → 끝
  shake 머리 흔들기 / dive 잠수 / surface 수면 질주 / reverse 역주행 / twist 줄 비틀기
  chain 연쇄 콤보: 예고 한 번 뒤 chain_seq(3행동)를 짧은 예고로 이어 간다
  판정은 fishing/patterns.py (Fight가 들고 있음). 패턴 상태가 끝나면 events에 "end:<id>"
U4: hide 숨기 / pump 펌핑 리듬 / bite 줄 물어뜯기 (상태), thrash 공중 몸부림 (점프 변형 jump_kind "thrash"),
  stiff 경직 (물어뜯기 성공 뒤 빈틈), dual 이중 패턴 (dual_pairs 중 한 짝을 동시에 — 각자 길이, 둘 다 끝나면 끝),
  가짜 지침 일반화: 끝날 때 "fake_end" → Fight가 rush_mult_next / tired_mult_next 를 정한다
"""
import random

from src.core.config import load_json

PATTERNS = ("shake", "dive", "surface", "reverse", "twist", "hide", "pump", "bite")  # 상태가 되는 신규 패턴
NEW_ACTIONS = PATTERNS + ("chain", "thrash", "dual")  # 신규 패턴 행동 전체 (chain은 순서만, thrash는 점프 변형)
ACTIVE_STATES = ("idle", "telegraph", "rush", "jump", "turn", "fake_tired", "dual") + PATTERNS
CALM_STATES = ("charge", "tired", "exhausted", "stiff")
STATE_NAMES = {
    "idle": "격렬", "telegraph": "격렬", "rush": "돌진!", "jump": "점프!", "turn": "방향 전환",
    "charge": "멈춤", "tired": "지침", "fake_tired": "지침", "recover": "회복 중", "exhausted": "완전 지침",
    "shake": "머리 흔들기!", "dive": "잠수!", "surface": "수면 질주!", "reverse": "역주행!", "twist": "줄 비틀기!",
    "hide": "숨기!", "pump": "펌핑!", "bite": "물어뜯기!", "stiff": "경직!", "dual": "이중 패턴!",
}


def patterns_cfg() -> dict:
    return load_json("patterns.json")


class FishBrain:
    def __init__(self, fish: dict, rnd: random.Random | None = None):
        self.fish = fish
        root = load_json("fishing_config.json")
        self.cfg = root["fish_ai"]
        self.legend_cfg = root["legend"]
        self.rnd = rnd or random.Random()
        cfg = self.cfg
        self.phases = fish.get("phases") or []
        self.phase = 0
        self.pcfg = patterns_cfg()
        self._load_params(fish)
        if self.phases:
            self._load_params({**fish, **self.phases[0]})
        self.state = "idle"
        self.pending: str | None = None   # telegraph 중일 때 다음 행동
        self.cur_telegraph = self.telegraph_sec
        self.timer = self._rand(cfg["idle_sec"])
        self.state_t = 0.0
        self.burst = 1.0
        self.turn_dir = 1
        self.leap_dir = 1           # 몸털기 점프 때 몸을 던지는 쪽
        self.turn_count = 0         # 방향 전환 예고 횟수 (꺾기 판정 구분용)
        self.jump_kind = "dip"      # dip: 우클릭 점프 / swipe: 슬라이드 점프
        self.cover_dir = 0          # Fight가 매 틱 알려줌: 가장 가까운 위협 구역 방향 (-1/0/1)
        self.cover_from_gimmick = False  # True면 cover_dir이 위협 구역이 아니라 기믹(바깥) 방향
        self.chain_left = 0
        self.chain_action: str | None = None
        self.rush_after_charge = False
        self.jump_judged = False
        self.events: list[str] = []
        # 신규 패턴
        self.telegraph_lead = 0.0   # 모바일: 신규 패턴 예고를 이만큼 길게 (Fight가 넣어 줌)
        self.combo_seq: list[str] = []  # 연쇄 콤보 남은 행동
        self.combo_all: list[str] = []  # 이번 콤보 전체 (화면 표시용)
        self.combo_on = False
        self.combo_mult = 1.0       # 콤보 중간 실패 → 남은 행동 힘 ×1.3
        self.busy = 0               # Fight가 매 틱 알려줌: 지금 대응 중인 것 수 (동시 2개 규칙)
        self.dual_pair: tuple[str, str] | None = None  # 이중 패턴 짝 (예고~행동)
        self.dual_dur: dict[str, float] = {}           # 짝마다 행동 길이
        self.dual_ended: set = set()
        self.pump_beats = 0          # 펌핑 리듬 박 수
        self.thrash_judged = [False, False]  # 공중 몸부림: 정점 / 착수 직전
        self.rush_mult_next = 1.0    # 가짜 지침에 감았다 → 이어지는 돌진 ×1.4
        self.tired_mult_next = 1.0   # 가짜 지침을 버텼다 → 다음 진짜 지침 ×1.3
        # 첫 돌진 (가물치): 챔질 직후 예고 → 강한 돌진
        # 파이팅 가독성 (31장 C4): 시간 규칙·부하 예산·휴식
        self.sig = load_json("signals.json")
        self.clock = 0.0
        self.load_budget = self.sig["budget_3s"].get(fish.get("spot"), 99)  # 낚시터가 없으면(테스트) 제한 없음
        self.starts: list[tuple] = []   # (시각, 부하, 그때 예산) — 3초 창 부하
        self.ep_start: float | None = None          # 지금 에피소드(쉬지 않고 이어지는 행동 묶음) 시작
        self.ep_action: str | None = None
        self.last_ep_end = -99.0
        self.last_ep_load = 0
        self.last_ep_action: str | None = None
        self.mastery: dict | None = None      # 세이브 pattern_mastery (낚시 화면이 넣어 줌, 봇·테스트는 None = 배율 1)
        self.fail_streak: dict | None = None  # 세이브 pattern_fail_streak
        self.access_mult = 1.0                 # 접근성 설정 예고 시간 배율 1.0/1.25/1.5 (랭크 판정엔 영향 없음)
        self.first_rush = fish.get("first_rush")
        self.first_rush_on = False
        self.first_rush_done = not self.first_rush
        if self.first_rush:
            self._begin_telegraph("rush", self.first_rush.get("telegraph_sec", self.telegraph_sec))

    def _rand(self, pair) -> float:
        return self.rnd.uniform(pair[0], pair[1])

    def _load_params(self, src: dict) -> None:
        cfg = self.cfg
        self.telegraph_sec = src.get("telegraph_sec", 1.0)
        self.actions = src.get("actions", {"rush": 1})
        self.tired_range = src.get("tired_sec", cfg["tired_sec"])
        self.rush_sec = src.get("rush_sec", cfg["rush_sec"])
        self.turn_sec = src.get("turn_sec", cfg["turn_sec"])
        self.turn_speed = src.get("turn_speed", cfg["turn_speed"])
        self.charge_range = src.get("charge_sec", cfg["charge_sec"])
        self.jump_chain = src.get("jump_chain", [1, 1])
        self.turn_chain = src.get("turn_chain", [1, 1])
        self.combo = src.get("combo", {})
        self.cover_bias = src.get("cover_bias", 0.0)
        self.charge_rush_mult = src.get("charge_rush_mult", 1.0)
        self.fake_tired_p = src.get("fake_tired", 0.0)
        self.ink_p = src.get("ink", 0.0)
        self.dark = src.get("dark", False)
        self.lightning_cue = src.get("lightning_cue", False)
        self.jump_height = src.get("jump_height_m", cfg["jump_height_m"])
        self.dragon = src.get("dragon", False)
        self.fake_cue_p = src.get("fake_cue", 0.0)
        self.fake_rush_p = src.get("fake_rush", 0.0)  # 교활 변이: 웅크렸다가 안 오는 가짜 돌진 (31-14)
        self.gimmick = src.get("gimmick")            # 전설 페이즈가 기믹을 바꿀 때 (오르시엘)
        self.gimmick_mult = src.get("gimmick_mult", 1.0)
        self.gimmick_bias = src.get("gimmick_bias", 0.0)  # 기믹 쪽(바깥)으로 끄는 경향 — 위협 구역 경향과 따로
        self.sound_only = src.get("sound_only", False)
        if self.sound_only:
            self.dark = True
        self.chain_seq = src.get("chain_seq") or self.pcfg["chain"]["default_seq"]
        self.dual_pairs = src.get("dual_pairs") or self.pcfg["dual"]["allowed"]

    @property
    def phase_desc(self) -> str:
        return self.phases[self.phase].get("desc", "") if self.phases else ""

    def _check_phase(self, stamina_frac: float) -> None:
        """전설: 체력이 기준 아래로 떨어지면 다음 페이즈로 (점프 중이면 착수 뒤에)."""
        if not self.phases or self.phase >= len(self.phases) - 1 or self.state in ("jump", "exhausted"):
            return
        threshold = self.fish.get("phase_at", self.legend_cfg["phase_at"])[self.phase]
        if stamina_frac > threshold:
            return
        self.phase += 1
        # 이전 페이즈 값 위에 새 페이즈 값을 쌓는다
        merged = dict(self.fish)
        for ph in self.phases[: self.phase + 1]:
            merged.update(ph)
        self._load_params(merged)
        if self.phase == 2:   # 3페이즈 진입: 체력 회복 (용등 변신은 전부) — Fight 가 heal_to 를 읽어 적용
            self.heal_to = 1.0 if self.dragon else self.legend_cfg.get("phase3_heal", 0.5)
        self.pending = None
        self.chain_left = 0
        self.chain_action = None
        self.combo_seq, self.combo_on, self.combo_mult = [], False, 1.0
        self.burst = max(self.burst, 0.8)
        pause = self.legend_cfg["phase_pause_sec"] + (self.legend_cfg["dragon_extra_pause_sec"] if self.dragon else 0)
        self._enter("idle", pause)  # 숨 돌릴 틈 (용 변신은 연출 동안 더 길게)
        self.events.append(f"phase:{self.phase + 1}")

    # ── 조회 ──
    @property
    def pull(self) -> float:
        p = self._state_pull(self.state)
        p *= self.combo_mult
        if self.state == "rush":
            p *= self.rush_mult_next
        if self.state == "rush" and self.rush_after_charge:
            p *= self.charge_rush_mult
        if self.state == "rush" and self.first_rush_on:
            p *= self.first_rush.get("power_mult", 1.5)
        return p

    def _state_pull(self, state: str) -> float:
        if state in self.cfg["pull"]:
            return self.cfg["pull"][state]
        if state == "stiff":
            return self.pcfg["bite"]["stiff_pull"]
        if state == "dual":
            running = [a for a in (self.dual_pair or ()) if a not in self.dual_ended]
            return max((self._state_pull(a) for a in running), default=self.cfg["pull"]["idle"])
        return self.pcfg[state]["pull"]

    def doing(self, pid: str) -> bool:
        """그 패턴 행동 중인가 (이중 패턴의 한쪽 포함)."""
        if self.state == pid:
            return True
        return self.state == "dual" and pid in (self.dual_pair or ()) and pid not in self.dual_ended

    def telegraphing(self, pid: str) -> bool:
        """그 패턴 예고 중인가 (이중 패턴 예고의 한쪽 포함)."""
        if self.state != "telegraph":
            return False
        return self.pending == pid or (self.pending == "dual" and pid in (self.dual_pair or ()))

    def pattern_elapsed(self, pid: str) -> float:
        return self.state_t

    def end_pattern(self, pid: str) -> None:
        """판정이 일찍 끝난 패턴(숨기 성공)을 다음 틱에 끝낸다."""
        if self.state == pid:
            self.timer = 0.0

    def enter_stiff(self, sec: float) -> None:
        """물어뜯기를 헛물었다: 잠깐 경직 (콤보 중이면 밀려난 다음 행동은 경직 뒤로)."""
        if self.state == "telegraph" and self.combo_on and self.pending:
            self.combo_seq.insert(0, self.pending)
        self.chain_left = 0
        self.pending = None
        self._enter("stiff", sec)
        self.events.append("stiff")

    @property
    def is_calm(self) -> bool:
        """크게 감을 수 있는 빈틈 상태."""
        return self.state in CALM_STATES

    @property
    def is_active(self) -> bool:
        return self.state in ACTIVE_STATES

    @property
    def signal(self) -> str | None:
        """현재 보여줄 예고 신호 종류."""
        return self.pending if self.state == "telegraph" else None

    def signal_progress(self) -> float:
        if self.state != "telegraph":
            return 0.0
        return min(1.0, self.state_t / max(1e-6, self.cur_telegraph))

    @property
    def jump_air(self) -> float:
        thrash = (self.state == "jump" and self.jump_kind == "thrash") or \
            (self.state == "telegraph" and self.pending == "thrash")
        return self.pcfg["thrash"]["air_sec"] if thrash else self.cfg["jump_air_sec"]

    @property
    def air_height(self) -> float:
        """화면 점프 높이 (공중 몸부림은 더 높이)."""
        k = self.pcfg["thrash"]["height_mult"] if self.jump_kind == "thrash" and self.state == "jump" else 1.0
        return self.jump_height * k

    def time_to_second(self) -> float:
        """공중 몸부림 두 번째 저스트(착수 직전)까지 남은 시간."""
        if self.state == "jump" and self.jump_kind == "thrash":
            return (self.jump_air - self.pcfg["thrash"]["land_before"]) - self.state_t
        if self.state == "telegraph" and self.pending == "thrash":
            return (self.cur_telegraph - self.state_t) + self.jump_air - self.pcfg["thrash"]["land_before"]
        return 999.0

    def jump_phase(self) -> float:
        """점프 진행도 0~1 (0.5 = 정점)."""
        if self.state != "jump":
            return 0.0
        return min(1.0, self.state_t / self.jump_air)

    def time_to_apex(self) -> float:
        """점프 정점까지 남은 시간 (음수면 지남). 점프 예고 중이면 예고 남은 시간 포함."""
        if self.state == "jump":
            return self.jump_air / 2 - self.state_t
        if self.state == "telegraph" and self.pending in ("jump", "leap", "thrash"):
            return (self.cur_telegraph - self.state_t) + self.jump_air / 2
        return 999.0

    def turn_offset(self) -> float | None:
        """방향 전환 시작 시각 기준 지금 시간 (예고 중이면 음수). 전환과 상관없으면 None."""
        if self.state == "telegraph" and self.pending == "turn":
            return -(self.cur_telegraph - self.state_t)
        if self.state == "turn":
            return self.state_t
        return None

    def display_name(self) -> str:
        if self.state == "jump" and self.jump_kind == "swipe":
            return "몸털기!"
        if self.state == "jump" and self.jump_kind == "thrash":
            return "공중 몸부림!"
        return STATE_NAMES[self.state]

    # ── 외부 개입 ──
    def lose_burst(self, amount: float) -> None:
        self.burst -= amount

    def insert_jump(self, telegraph_sec: float) -> None:
        """수면 질주 실패: 곧바로 점프 시도. 콤보 중이면 밀려난 다음 행동은 점프 뒤로."""
        if self.state == "telegraph" and self.combo_on and self.pending:
            self.combo_seq.insert(0, self.pending)
        self.chain_left = 0
        self._begin_telegraph("jump", telegraph_sec, penalty=True)

    def recover_from_net_fail(self) -> None:
        self.burst = max(self.burst, 0.6)
        self.combo_seq, self.combo_on, self.combo_mult = [], False, 1.0
        self.dual_pair = None
        self.chain_left = 0
        self._begin_telegraph("rush", penalty=True)

    # ── 상태 전환 ──
    def _enter(self, state: str, duration: float) -> None:
        rest = state in self.sig["rest_states"]
        if rest and self.ep_start is not None:
            # 에피소드 끝: 휴식 규칙의 기준 (부하 = 이 에피소드에서 시작한 행동 부하 합, 실패 결과 행동 제외)
            mine = [s for s in self.starts if s[0] >= self.ep_start]
            load = sum(s[1] for s in mine if not s[4])
            if mine:  # 등불 가짜 예고만 있던 묶음(기록 없음)은 패턴이 아니다 — 앞 패턴 기록을 그대로 둔다
                # 실패 결과 행동(수면 질주 실패 → 점프)만 있던 묶음도 휴식은 그 뒤부터 센다 (C7)
                self.last_ep_end = self.clock
                if load > 0:
                    self.last_ep_load = load
                    self.last_ep_action = self.ep_action
            self.ep_start = None
        elif not rest and self.ep_start is None:
            self.ep_start = self.clock
            self.ep_action = None
        self.state = state
        self.timer = duration
        self.state_t = 0.0

    # ── 파이팅 가독성 (31장 C4) ──
    def load_of(self, action: str) -> int:
        acts = self.sig["actions"]
        if action == "dual":
            pairs = [self.dual_pair] if self.dual_pair else self.dual_pairs
            return max(sum(acts.get(x, {}).get("load", 1) for x in p) for p in pairs)
        return acts.get(action, {}).get("load", 1)

    def budget(self) -> int:
        """3초 부하 예산: 낚시터 값, 전설 마지막 페이즈는 legend_last_phase."""
        if len(self.phases) > 1 and self.phase == len(self.phases) - 1:
            return max(self.load_budget, self.sig["legend_last_phase"])
        return self.load_budget

    def window_load(self) -> int:
        w = self.sig["timing"]["window_sec"]
        return sum(s[1] for s in self.starts if s[0] > self.clock - w)

    def fits(self, action: str, extra: int = 0, alone_ok: bool = True) -> bool:
        """이 행동(+ 이어서 확정된 행동 부하 extra)을 지금 시작해도 3초 예산 안인가.
        alone_ok: 창이 비어 있으면 예산보다 큰 단일 패턴(콤보 4·이중)도 혼자는 허용."""
        w = self.window_load()
        load = self.load_of(action) + extra
        return w + load <= self.budget() or (alone_ok and extra == 0 and w == 0)

    def rest_needed(self) -> float:
        r = self.sig["rest"]
        return r["after_heavy_sec"] if self.last_ep_load >= r["heavy_load"] else r["min_sec"]

    def dual_allowed(self) -> bool:
        """이중 패턴은 세계수 뿌리 샘 + 전설 마지막 페이즈에서만."""
        if self.fish.get("spot") == "world_tree":
            return True
        return len(self.phases) > 1 and self.phase == len(self.phases) - 1

    def min_telegraph(self, action: str) -> float:
        """계열별 최소 예고 (+모바일). 가짜(lure)·펌핑(박자 미리 듣기 길이 고정)은 0."""
        tm = self.sig["timing"]
        if action in ("lure", "pump"):
            return 0.0
        if action == "chain":
            m = tm["combo_preview"]
        elif action in ("jump", "leap"):
            m = tm["ring_total"] - self.cfg["jump_air_sec"] / 2
        elif action == "thrash":
            m = tm["ring_total"] - self.pcfg["thrash"]["air_sec"] / 2
        elif action == "dual":
            pair = self.dual_pair or ("shake", "bite")
            return max(self.min_telegraph(a) for a in pair if a != "pump") + self.sig["dual_stagger_sec"] \
                if any(a != "pump" for a in pair) else 0.0
        else:
            fam = self.sig["actions"].get(action, {}).get("family")
            m = tm["min"].get(fam, 0.7)
        return m + self.telegraph_lead

    def can_start(self, action: str) -> bool:
        """휴식이 끝났고 예산 안이면 True (뜰채 앞 다시 도망치기 같은 외부 계기용)."""
        return (self.state in self.sig["rest_states"] and self.clock - self.last_ep_end >= self.rest_needed()
                and self.fits(action))

    def learn_mult(self, action: str) -> float:
        """숙련도 배율 (처음 1.5 / 익숙함 1.2 / 숙련 1.0) + 연속 실패 보조(다음 1번 1.2) 중 큰 쪽."""
        if self.mastery is None or action in ("lure", "fake_rush"):
            return 1.0
        mc = self.sig["mastery"]
        n = self.mastery.get(action, 0)
        mult = 1.0
        for need, m in mc["tiers"]:
            if n >= need:
                mult = m
        if self.fail_streak is not None and self.fail_streak.get(action, 0) >= mc["assist_after_fails"]:
            self.fail_streak[action] = 0  # 보조는 한 번만
            mult = max(mult, mc["assist_mult"])
        return mult

    def _record_start(self, action: str, penalty: bool = False) -> None:
        """penalty = 플레이어 실패의 결과로 바로 이어지는 행동(수면 질주 실패 → 점프, 뜰채 실패 → 돌진).
        3초 창 부하엔 넣지만(다음 패턴이 기다리게) 예산 위반 집계에선 뺀다."""
        load = self.load_of(action)
        if load > 0:
            self.starts.append((self.clock, load, self.budget(), action, penalty))
            self.starts = [s for s in self.starts if s[0] > self.clock - 10]
        if self.ep_action is None:
            self.ep_action = action

    def _short_telegraph(self) -> float:
        return max(self.cfg["min_telegraph_sec"], self.telegraph_sec * self.cfg["chain_telegraph_mult"])

    def pattern_telegraph(self, action: str) -> float:
        """신규 패턴 예고 길이: 물고기 예고 × 배율, 최소 0.4초, 모바일은 조금 더.
        이중 패턴은 두 예고가 시차(dual_stagger_sec)를 두고 차례로 뜨니 그만큼 길게 (31장 C3)."""
        t = self._pattern_telegraph(action)
        if action == "dual":
            t += load_json("signals.json")["dual_stagger_sec"]
        return t

    def _pattern_telegraph(self, action: str) -> float:
        pc = self.pcfg
        if action == "chain":
            base = pc["chain"]["telegraph_sec"]
        elif action == "pump" or (action == "dual" and "pump" in (self.dual_pair or ())):
            # 펌핑: 예고 = 미리 들려주는 박 (박자가 끊기지 않게 모바일 여유도 안 붙임 — 판정 창을 늦춘다)
            return pc["pump"]["preview_beats"] * pc["pump"]["interval"]
        else:
            base = self.telegraph_sec * pc[action].get("telegraph_mult", 1.0)
        return max(pc["min_telegraph_sec"], base) + self.telegraph_lead

    def _begin_telegraph(self, action: str, duration: float | None = None, turn_dir: int | None = None,
                         penalty: bool = False) -> None:
        if action == "dual":
            self.dual_pair = tuple(self.rnd.choice(self.dual_pairs))
        if action == "pump" or (action == "dual" and "pump" in self.dual_pair):
            duration = None  # 박자 예고는 길이가 정해져 있다
        if duration is None and action in NEW_ACTIONS:
            duration = self.pattern_telegraph(action)
        elif duration is not None and action in NEW_ACTIONS:
            duration = max(self.pcfg["min_telegraph_sec"], duration) + self.telegraph_lead
        self.pending = action
        if action == "leap":
            self.leap_dir = self.rnd.choice((-1, 1))
        if action == "turn":
            self.turn_count += 1
        if action == "turn":
            if turn_dir is not None:
                self.turn_dir = turn_dir
            elif self.cover_dir and self.rnd.random() < (self.gimmick_bias if self.cover_from_gimmick else self.cover_bias):
                self.turn_dir = self.cover_dir
            else:
                self.turn_dir = self.rnd.choice((-1, 1))
        self.cur_telegraph = duration if duration is not None else self.telegraph_sec
        self.cur_telegraph = max(self.cur_telegraph, self.min_telegraph(action))  # 계열별 최소 예고 (31장 C4)
        self.cur_telegraph *= self.learn_mult(action) * self.access_mult  # 패턴 숙련도 (C5) × 접근성 배율 (C6)
        speed = getattr(self, "train_speed", None)  # 훈련 수조 예고 속도
        if self.min_telegraph(action) <= 0:
            speed = None  # 펌핑(박자 미리 듣기 길이 고정)·등불은 속도 배율 없음 — 0초 예고로 꺼지던 문제 (훈련 수조 펌핑)
        if speed == "slow":
            self.cur_telegraph = self.min_telegraph(action) * 2
        elif speed == "norm":
            self.cur_telegraph = self.min_telegraph(action)
        self._enter("telegraph", self.cur_telegraph)
        if not self.combo_on:
            self._record_start(action, penalty)  # 콤보 안의 단계는 콤보 부하(4)에 포함
        self.events.append(f"telegraph:{action}")

    def _choose_action(self) -> str | None:
        names = list(self.actions)
        if not self.dual_allowed():
            names = [n for n in names if n != "dual"] or names
        # 부하 예산: 멈춤 뒤엔 돌진이 확정이라 그만큼 더 본다. 같은 고부하 패턴 연속 금지.
        heavy = self.sig["rest"]["heavy_load"]
        names = [n for n in names if self.fits(n, 1 if n == "charge" else 0)
                 and not (self.last_ep_load >= heavy and n == self.last_ep_action and self.load_of(n) >= heavy)]
        if not names:
            return None
        if self.busy >= 2:
            # 동시 2개 규칙: 이미 둘에 대응 중이면(패턴 + 꼬임 게이지 등) 신규 패턴 대신 기존 행동
            plain = [n for n in names if n not in NEW_ACTIONS]
            names = plain or names
        elif self.busy >= 1:
            names = [n for n in names if n != "dual"] or names  # 이중 패턴은 혼자 2칸
        return self.rnd.choices(names, [self.actions[n] for n in names])[0]

    def force_pattern(self, action: str) -> None:
        """테스트(F9): 지금 바로 그 패턴 예고."""
        self.chain_left = 0
        self.chain_action = None
        self.combo_seq = []
        self.combo_on = False
        self.combo_mult = 1.0
        self.burst = max(self.burst, 0.6)
        if action == "fake":
            self.burst = 0.0
            self._enter("fake_tired", self._rand(self.cfg["fake_tired_sec"]))
            self.events.append("fake_tired")
            return
        self._begin_telegraph(action)

    def _start_action(self, action: str) -> None:
        cfg = self.cfg
        # 연속 동작(체인) 중엔 burst를 덜 쓴다
        if action in NEW_ACTIONS:
            cost = self.pcfg[action]["burst_cost"]
        else:
            cost = cfg["burst_cost"].get(action, 0.2)
        if self.combo_on:
            cost *= 0.5  # 콤보는 묶어서 한 번 크게 쓴 셈
        self.burst -= cost * (0.5 if self.chain_action == action else 1.0)
        self.pending = None
        if action in ("lure", "fake_rush"):
            # 가짜 예고: 아무 일도 없다 (가짜 돌진 = 웅크림·안쪽 물결만, 줄 펄스 없음)
            self.events.append(f"action:{action}")
            self._enter("idle", self._rand(cfg["idle_sec"]))
            return
        if action == "chain":
            # 연쇄 콤보: 예고가 끝나면 첫 행동을 바로 시작 (예고 때 순서를 보여 줬다)
            self.combo_all = list(self.chain_seq)
            self.combo_seq = list(self.chain_seq)
            self.combo_on = True
            self.combo_mult = 1.0
            self.events.append("action:chain")
            first = self.combo_seq.pop(0)
            self.chain_left = 0
            self.chain_action = None
            if first == "charge":
                self._start_action("charge")
            else:
                self._start_action(first)
            return
        if action == "dual":
            a, b = self.dual_pair
            self.dual_dur = {x: self._pattern_sec(x) for x in (a, b)}
            self.dual_ended = set()
            self._enter("dual", max(self.dual_dur.values()))
            self.events += ["action:dual", f"action:{a}", f"action:{b}"]
            return
        if action in PATTERNS:
            self._enter(action, self._pattern_sec(action))
            self.events.append(f"action:{action}")
            return
        if action == "thrash":
            self.jump_judged = False
            self.thrash_judged = [False, False]
            self.jump_kind = "thrash"
            self._enter("jump", self.pcfg["thrash"]["air_sec"])
            self.events.append("action:thrash")
            return
        if action == "rush":
            if not self.first_rush_done:
                self.first_rush_on = self.first_rush_done = True
                self._enter("rush", self.first_rush.get("sec", self.rush_sec))
                self.events.append("action:rush")
                return
            self._enter("rush", self.rush_sec)
        elif action in ("jump", "leap"):
            self.jump_judged = False
            self.jump_kind = "dip" if action == "jump" else "swipe"
            self._enter("jump", cfg["jump_air_sec"])
        elif action == "turn":
            self._enter("turn", self.turn_sec)
        elif action == "charge":
            self._enter("charge", self._rand(self.charge_range))
            if not self.combo_on:
                self._record_start("charge")
        self.events.append(f"action:{action}")

    def _pattern_sec(self, pid: str) -> float:
        if pid == "pump":
            pc = self.pcfg["pump"]
            self.pump_beats = self.rnd.randint(*pc["beats"])
            return self.pump_beats * pc["interval"]
        return self._rand(self.pcfg[pid]["sec"])

    def _begin_action_sequence(self, action: str) -> None:
        """새 행동 시작: 체인 횟수 결정."""
        self.chain_action = None
        self.chain_left = 0
        if action == "jump":
            self.chain_left = self.rnd.randint(*self.jump_chain) - 1
        elif action == "turn":
            self.chain_left = self.rnd.randint(*self.turn_chain) - 1
        # 연속 동작은 묶음 전체 부하가 예산 안에 들도록 줄인다 (31장 C4)
        while self.chain_left > 0 and not self.fits(action, self.chain_left * self.load_of(action), alone_ok=False):
            self.chain_left -= 1
        if self.chain_left > 0:
            self.chain_action = action
        if action == "charge":
            self._start_action("charge")  # 멈춤 자체가 신호
        else:
            self._begin_telegraph(action)

    def update(self, dt: float, stamina_empty: bool, stamina_frac: float = 1.0) -> None:
        self.clock += dt
        self.state_t += dt
        self.timer -= dt
        self._check_phase(stamina_frac)
        if self.state == "exhausted":
            return
        if stamina_empty and self.state not in ("jump",):
            self._enter("exhausted", 999.0)
            self.events.append("exhausted")
            return
        if self.state == "dual":
            for a, d in self.dual_dur.items():
                if a not in self.dual_ended and self.state_t >= d:
                    self.dual_ended.add(a)
                    self.events.append(f"end:{a}")
        if self.timer > 0:
            return

        cfg = self.cfg
        s = self.state
        if s == "telegraph":
            self._start_action(self.pending)
        elif s == "jump":
            self.events.append("jump_land")
            self._after_action({"dip": "jump", "swipe": "leap"}.get(self.jump_kind, self.jump_kind))
        elif s == "charge":
            # 힘을 모았다가 돌진 (예고 후)
            self._begin_telegraph("rush")
            self.rush_after_charge = True
            return
        elif s in ("rush", "turn"):
            if s == "rush" and self.ink_p and self.rnd.random() < self.ink_p:
                self.events.append("ink")
            self._after_action(s)
        elif s in PATTERNS:
            self.events.append(f"end:{s}")
            self._after_action(s)
        elif s == "dual":
            for a in self.dual_pair:
                if a not in self.dual_ended:
                    self.events.append(f"end:{a}")
            self.events.append("end:dual")
            self.dual_pair = None
            self._after_action("dual")
        elif s == "stiff":
            self._after_action("stiff")
        elif s == "idle":
            wait = self.rest_needed() - (self.clock - self.last_ep_end)
            if wait > 0 and self.burst > 0:
                self._enter("idle", wait)  # 패턴 사이 최소 휴식 (31장 C4)
                return
            if self.burst <= 0:
                if self.fake_tired_p and self.rnd.random() < self.fake_tired_p and wait <= 0 \
                        and self.fits("fake_tired", self.load_of("rush")):
                    self._enter("fake_tired", self._rand(cfg["fake_tired_sec"]))
                    self._record_start("fake_tired")
                    self.events.append("fake_tired")
                else:
                    self._enter("tired", self._rand(self.tired_range) * self.tired_mult_next)
                    self.tired_mult_next = 1.0
                    self.events.append("tired")
            elif self.fake_cue_p and self.rnd.random() < self.fake_cue_p:
                self._begin_telegraph("lure")
            elif self.fake_rush_p and self.rnd.random() < self.fake_rush_p:
                self._begin_telegraph("fake_rush")
            else:
                act = self._choose_action()
                if act is None:
                    self._enter("idle", 0.3)  # 예산이 빌 때까지 조금 더 쉰다
                    return
                self._begin_action_sequence(act)
        elif s == "fake_tired":
            # 지친 척 끝 → 돌진 (예고는 정상 길이)
            self.burst = max(self.burst, 0.3)
            self.events.append("fake_end")
            self._begin_telegraph("rush")
        elif s == "tired":
            self._enter("recover", cfg["recover_sec"])
            self.events.append("recover")
        elif s == "recover":
            self.burst = 1.0
            self._enter("idle", self._rand(cfg["idle_sec"]))
        if self.state != "rush":
            self.rush_after_charge = False
            if s == "rush":
                self.rush_mult_next = 1.0  # 가짜 지침 벌칙은 돌진 한 번만

    def _after_action(self, action: str) -> None:
        if self.first_rush_on:
            # 첫 돌진에 힘을 다 써서 빨리 지친다
            self.first_rush_on = False
            self.burst = min(self.burst, self.first_rush.get("burst_after", 0.7))
        # 연쇄 콤보: 다음 행동을 짧은 예고로
        if self.combo_on:
            if self.combo_seq:
                nxt = self.combo_seq.pop(0)
                gap = self.pcfg["chain"]["gap_telegraph_sec"]
                if nxt == "charge":
                    self._start_action("charge")
                else:
                    self._begin_telegraph(nxt, max(gap, self.cfg["min_telegraph_sec"]))
                return
            self.combo_on = False
            self.combo_mult = 1.0
            self.events.append("combo_end")
        # 연속 동작
        if self.chain_left > 0 and self.chain_action == action and self.fits(action, alone_ok=False):
            self.chain_left -= 1
            if action == "turn":
                self._begin_telegraph("turn", self._short_telegraph(), turn_dir=-self.turn_dir)
            else:
                self._begin_telegraph(action, self._short_telegraph())
            return
        self.chain_action = None
        # 콤보
        nxt = self.combo.get(action)
        if nxt and self.burst > 0 and self.rnd.random() < nxt[1] and \
                self.fits(nxt[0], 1 if nxt[0] == "charge" else 0, alone_ok=False):
            if nxt[0] == "charge":
                self._start_action("charge")  # 멈춤은 그 자체가 신호
            else:
                self._begin_telegraph(nxt[0], self._short_telegraph())
            return
        self._enter("idle", self._rand(self.cfg["idle_sec"]))
