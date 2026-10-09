"""튜토리얼: 처음 보는 상황마다 게임을 멈추고 설명 카드를 띄운다 (한 번씩만).

- 카드(card): 일시정지 + 대상 강조 + 설명. 클릭하면 계속.
- 가이드(guide): 멈추지 않는 상단 안내 배너 (캐스팅·입질 단계).
- 도움말(help): H키로 언제든 조작법·예고 신호 표.
"""
import math

import pygame

from src.core.config import load_json
from src.ui.hud import SHADOW, text, wrap_text

CARDS = {
    "welcome": ("미니 피싱에 오신 걸 환영해요!", [
        "던지기 → 입질 기다리기 → 챔질 → 파이팅 → 뜰채 순서로 진행돼요.",
        "물고기는 행동하기 전에 반드시 신호를 보내요. 신호를 읽으면 이깁니다.",
        "처음 보는 상황마다 잠깐 멈추고 설명해 드릴게요. (H키: 도움말)",
    ]),
    "fight_intro": ("파이팅 시작!", [
        "왼쪽 장력 게이지를 초록 구간에 유지하세요.",
        "위 빨강 = 줄이 상함(줄 게이지↓) / 아래 = 느슨해서 바늘이 빠짐(바늘 게이지↑)",
        "좌클릭 유지: 감기   Q·휠↓: 돌진 때 풀기   마우스: 물고기 반대로 버티기",
    ]),
    "telegraph:rush": ("웅크림 → 줄 펄스 → 돌진!", [
        "그림자가 짧게 웅크리고 물결이 안쪽으로 빨려 들면 돌진 준비. 빛이 줄을 타고 손에 닿는 순간 돌진합니다.",
        "드랙은 릴이 알아서 맞춰요. 빛이 손에 닿는 순간 Q(풀기)를 한 번 — 딱 맞으면 퍼펙트! 큰 물고기는 펄스가 두 번 — 두 번째에 돌진!",
    ]),
    "telegraph:jump": ("그림자가 커진다 → 점프!", [
        "물고기가 수면 위로 뛰어오릅니다. 바깥 원이 줄어들어 금색 판정 원과 겹치는 순간이 정점!",
        "그때 우클릭(낚싯대 숙이기) = PERFECT, 조금 어긋나면 GREAT. 놓치면 바늘이 빠지기 쉬워요.",
    ]),
    "telegraph:turn": ("줄이 한쪽으로 쏠린다 → 방향 전환!", [
        "물고기가 꺾는 순간(타이밍 막대 가운데) 마우스를 반대쪽으로 확 슬라이드하세요 = 꺾기!",
        "꺾기에 성공하면 거의 끌려가지 않아요. 그다음엔 반대쪽에 버티고 있으면 됩니다.",
    ]),
    "telegraph:leap": ("하늘색 원 → 몸털기 점프!", [
        "뛰어오른 물고기가 정점에서 한쪽으로 몸을 비틉니다. 우클릭이 아니에요!",
        "원이 겹치는 순간 원 안의 화살표 방향으로 마우스를 확 슬라이드하세요.",
    ]),
    "action:charge": ("움직임이 멈췄다 → 힘 모으기", [
        "지금이 기회! 좌클릭으로 확 감으세요 (평소보다 훨씬 빨리 감겨요).",
        "멈춤이 끝나면 곧 돌진하니 대비하세요.",
    ]),
    "tired": ("지쳤다 → 빈틈!", [
        "저항이 약해졌어요. 계속 감으면 장력은 초록에 유지됩니다.",
        "릴이 알아서 드랙을 올려 빨리 감겨요. 감기를 멈추면 줄이 느슨해져요.",
    ]),
    "slack": ("줄이 느슨해요!", [
        "장력이 초록 아래면 바늘 게이지가 차오릅니다. 가득 차면 바늘이 빠져요.",
        "좌클릭으로 감아서 장력을 올리세요.",
    ]),
    "red": ("빨간 구간!", [
        "장력이 너무 높아서 줄이 상하고 있어요. 줄 게이지가 0이면 끊어집니다.",
        "감기를 멈추세요. 돌진이 오면 Q(풀기)로 줄을 풀어 주세요.",
    ]),
    "hazard_enter": ("위협 구역!", [
        "물고기가 수초·바위 쪽으로 들어갔어요. 걸림 게이지가 차면 줄이 걸려 끊어집니다.",
        "마우스를 물고기 반대쪽으로 당겨 구역 밖으로 빼내세요.",
    ]),
    "fake_tired": ("지친 척?!", [
        "지친 것처럼 보이지만 기포가 계속 올라오고 있어요. 진짜 지침이면 기포가 멈춥니다.",
        "속지 말고 돌진에 대비하세요 — 빛이 손에 닿으면 Q(풀기).",
    ]),
    "ink": ("먹물!", [
        "먹물이 그림자를 가렸어요. 그림자 신호(점프)가 안 보입니다.",
        "줄 쏠림과 소리(물보라·기포·긁힘)로 읽으세요.",
    ]),
    "gimmick:tangle": ("갈대 엉킴", [
        "물고기가 옆으로 오래 끌려가면 갈대가 줄을 감아 '엉킴' 게이지가 찹니다.",
        "가득 차면 잠깐 감을 수 없고 줄이 상해요. 마우스를 반대로 당겨 가운데로 끌어오세요.",
    ]),
    "gimmick:dark": ("어둠", [
        "동굴은 어두워서 물고기 그림자가 보이지 않아요.",
        "대신 천장 수정에 빛이 비칩니다: 금색 = 점프, 하늘색 = 몸털기, 흰 줄기 = 돌진, 화살표 = 방향 전환.",
    ]),
    "gimmick:current": ("물살", [
        "폭포 물살 때문에 장력이 4초마다 출렁입니다.",
        "장력 게이지 옆 물결 표시가 다음 '마루'를 알려줘요. 마루 직전엔 감기를 늦추세요.",
    ]),
    "gimmick:heat": ("열 손상", [
        "파이팅이 길어지면(보통 45초) 뜨거운 물에 줄이 상하기 시작합니다. 오래 끌수록 더 빨리!",
        "빈틈마다 확실히 감아 빨리 끝내세요. (줄 게이지 위 붉은 띠 = 열)",
    ]),
    "gimmick:ice": ("얼음 구멍", [
        "얼음 구멍이 좁아요. 물고기가 구멍 가장자리 밖으로 나가면 줄이 얼음에 쓸립니다.",
        "가장자리가 빨갛게 빛나면 마우스를 반대로 당겨 구멍 안으로 끌어오세요.",
    ]),
    "catch_intro": ("첫 물고기를 낚았어요!", [
        "잡은 물고기는 살림망에 들어가요. 인벤토리 (I)에서 언제든 볼 수 있어요.",
        "판매·분해는 '하루네 낚시점'(윤슬 마을)과 '엘라 공방'(아스테라)에서만 해요. 특급 배송 시스템을 사면 야외에서도 하루에 몇 번 팔 수 있어요.",
        "잡은 물고기는 도감 (Tab)에 기록돼요. 3번 · 10번 잡으면 예고 힌트가 하나씩 열려요.",
        "도감 별: 첫 포획 · S랭크 · 대물 · 변이 3종 · 숙련 5단계. 별을 모으면 보상을 받아요.",
    ]),
    "net_start": ("뜰채!", [
        "물고기가 눈앞에서 좌우로 몸부림칩니다.",
        "몸부림이 딱 멈춘 순간 좌클릭으로 뜨세요. 놓치면 다시 도망가요.",
    ]),
}

# 신규 패턴·루어 카드 (움직이는 시범 그림 포함, src/ui/pattern_guide.py)
from src.ui import pattern_guide as _pg  # noqa: E402
CARDS.update(_pg.CARDS)
# 환상어 고유 패턴 (33장 P4): 2페이즈 첫 진입 때 한 번 — 물고기 이름은 쓰지 않는다
from src.fishing.phantom import all_phantoms as _phantoms  # noqa: E402
CARDS.update({f"phantom:{_f['id']}": (f"고유 패턴: {_f['sig_title']}", [_f["sig_tip"]]) for _f in _phantoms()})

GUIDES = {
    "guide_cast": "좌클릭을 누르고 있으면 파워가 차요. 원하는 거리에서 놓으면 던집니다! (마우스: 방향)",
    "guide_wait": "찌를 지켜보세요. 톡톡 살짝 = 가짜 입질(무시!) / 찌가 쑥 잠기면 바로 좌클릭!",
}

HELP_CONTROLS = [
    ("던지기", "좌클릭 유지 → 놓기 (마우스로 방향)"),
    ("챔질", "찌가 쑥 잠길 때 좌클릭 (톡톡은 가짜)"),
    ("감기", "좌클릭 유지 · 금색 칸에 붙잡으면 2배 (감았다 뗐다)"),
    ("낚싯대 숙이기", "우클릭 (점프 때 원이 겹치는 순간 = PERFECT)"),
    ("드랙", "릴이 알아서 맞춤 · 돌진 때만 Q(풀기) 한 번 (설정: 직접 조절)"),
    ("버티기·꺾기", "마우스를 반대쪽으로 / 꺾는 순간 확 슬라이드"),
    ("소모품", "파이팅 중 1: 수리용 실타래  2: 잔잔한 물 부적 (파이팅당 1개)"),
    ("기타", "우클릭: 줄 회수  C: 보물상자  J: 의뢰  T: 시간 가속  F1: 수치  F2: 흔들림"),
]
DEBUG_CONTROLS = ("테스트", "F3: 물고기  F4: 낚시터  F5: 날씨  F6: 상자  F9: 패턴  F10: 변이  F11: 의뢰")
HELP_SIGNALS = [
    ("꼬리 물보라", "돌진", "닿는 순간 Q 풀기 (빨강이면 감기 멈춤)"),
    ("그림자 커짐 + 기포", "점프", "원이 겹칠 때 우클릭"),
    ("줄 쏠림", "방향 전환", "꺾는 순간 반대로 슬라이드"),
    ("그림자 + 하늘색 원", "몸털기 점프", "원이 겹칠 때 화살표 쪽 슬라이드"),
    ("멈춤", "힘 모으기", "확 감기"),
    ("지침", "빈틈", "크게 감기 (기포 계속 = 가짜)"),
    ("땀방울 (큰 행동 직후)", "틈", "1.5초 안에 꾹 감기 = 크게 지침"),
    ("금색 칸 (장력 맨 위)", "팽팽 구간", "감았다 뗐다 붙잡기 = 2배 지침"),
    ("등불만 번쩍 (기포 없음)", "가짜 신호", "무시 (진짜 점프는 기포 + 판정 원)"),
]

PANEL = (22, 28, 48)
BORDER = (255, 220, 120)


class Tutorial:
    def __init__(self, settings):
        self.settings = settings
        self.seen = set(settings.get("tutorial_seen"))

    def is_seen(self, key: str) -> bool:
        return key in self.seen

    def want(self, key: str) -> bool:
        """처음이면 True를 돌려주고 본 것으로 기록."""
        if key in self.seen:
            return False
        self.mark(key)
        return True

    def mark(self, key: str) -> None:
        if key not in self.seen:
            self.seen.add(key)
            self.settings.set("tutorial_seen", sorted(self.seen))

    def reset(self) -> None:
        self.seen.clear()
        self.settings.set("tutorial_seen", [])


def _dim(canvas, focus=None, radius: int = 0, alpha: int = 150) -> None:
    w, h = canvas.get_size()
    shade = pygame.Surface((w, h), pygame.SRCALPHA)
    shade.fill((6, 8, 20, alpha))
    if focus:
        pygame.draw.circle(shade, (0, 0, 0, 0), (int(focus[0]), int(focus[1])), radius)
    canvas.blit(shade, (0, 0))


def draw_card(canvas, key: str, focus, t: float, touch: bool = False) -> None:
    title, raw = CARDS[key]
    if key in _pg.DEMO:
        _pg.draw_card(canvas, key, title, raw, focus, t, touch)
        return
    w, h = canvas.get_size()
    pw = 440
    lines = [ln for r in raw for ln in wrap_text(r, pw - 24)]
    radius = 0
    if focus:
        radius = 22 + int(2 * math.sin(t * 6))
    _dim(canvas, focus, radius)
    if focus:
        pygame.draw.circle(canvas, BORDER, (int(focus[0]), int(focus[1])), radius, 1)
    ph = 34 + len(lines) * 15 + 18
    x = (w - pw) // 2
    # 강조 대상과 겹치지 않게 위/아래 선택
    y = 150 if not focus or focus[1] < 130 else 30
    y = max(8, min(y, h - ph - 8))   # 긴 카드도 화면 안에
    canvas.fill(SHADOW, (x + 2, y + 2, pw, ph))
    canvas.fill(PANEL, (x, y, pw, ph))
    pygame.draw.rect(canvas, BORDER, (x, y, pw, ph), 1)
    text(canvas, title, (w // 2, y + 14), BORDER, 16, "center")
    for i, ln in enumerate(lines):
        text(canvas, ln, (w // 2, y + 36 + i * 15), (232, 236, 245), 11, "center")
    if t > 0.35 and int(t * 2) % 2 == 0:
        text(canvas, "클릭해서 계속", (w // 2, y + ph - 9), (160, 170, 195), 11, "center")


def draw_guide(canvas, key: str, t: float) -> None:
    w = canvas.get_width()
    s = GUIDES[key]
    pw, ph = 452, 20
    x, y = (w - pw) // 2, 22
    canvas.fill(SHADOW, (x + 1, y + 1, pw, ph))
    canvas.fill(PANEL, (x, y, pw, ph))
    border = BORDER if int(t * 2) % 2 == 0 else (200, 170, 90)
    pygame.draw.rect(canvas, border, (x, y, pw, ph), 1)
    text(canvas, s, (w // 2, y + ph // 2), (240, 240, 250), 11, "center")


def draw_help(canvas, more: bool = False) -> None:
    w, h = canvas.get_size()
    _dim(canvas, alpha=190)
    pw, ph = 450, 266
    x, y = (w - pw) // 2, (h - ph) // 2
    canvas.fill(PANEL, (x, y, pw, ph))
    pygame.draw.rect(canvas, BORDER, (x, y, pw, ph), 1)
    text(canvas, "도움말", (w // 2, y + 11), BORDER, 16, "center")
    yy = y + 22
    text(canvas, "조작", (x + 10, yy), (150, 200, 255), 11)
    yy += 12
    controls = HELP_CONTROLS + ([DEBUG_CONTROLS] if load_json("fishing_config.json").get("debug_keys") else [])
    for name, desc in controls:
        text(canvas, name, (x + 14, yy), (255, 240, 200), 11)
        text(canvas, desc, (x + 100, yy), (230, 232, 240), 11)
        yy += 12
    yy += 3
    text(canvas, "예고 신호 → 행동 → 대응", (x + 10, yy), (150, 200, 255), 11)
    yy += 12
    for sig, act, resp in HELP_SIGNALS:
        text(canvas, sig, (x + 14, yy), (255, 240, 200), 11)
        text(canvas, act, (x + 140, yy), (255, 170, 150), 11)
        text(canvas, resp, (x + 220, yy), (230, 232, 240), 11)
        yy += 11
    yy += 3
    text(canvas, "장력은 초록 구간 유지! 빨강 = 줄 손상, 아래 = 바늘 빠짐", (w // 2, yy + 4), (140, 230, 150), 11,
         "center")
    text(canvas, "H 또는 클릭: 다음 쪽 (신규 패턴)" if more else "H 또는 클릭: 닫기", (w // 2, y + ph - 9),
         (160, 170, 195), 11, "center")


def draw_help_patterns(canvas, seen: list, touch: bool) -> None:
    """도움말 2쪽: 신규 패턴 — 본 것만 대응법, 못 본 것은 ???."""
    from src.fishing.patterns import TIP_SHORT
    w, h = canvas.get_size()
    _dim(canvas, alpha=190)
    pw, ph = 450, 266
    x, y = (w - pw) // 2, (h - ph) // 2
    canvas.fill(PANEL, (x, y, pw, ph))
    pygame.draw.rect(canvas, BORDER, (x, y, pw, ph), 1)
    text(canvas, "도움말 · 신규 패턴", (w // 2, y + 11), BORDER, 16, "center")
    names = load_json("patterns.json")["names"]
    guides = load_json("patterns.json")["guide"]
    order = ("shake", "dive", "surface", "reverse", "twist", "chain", "hide", "pump", "thrash", "bite", "fake", "dual")
    yy = y + 28
    for pid in order:
        if pid in seen:
            sig = guides[pid].split("!")[0]
            text(canvas, names[pid], (x + 14, yy), (255, 240, 200), 11)
            r = text(canvas, sig, (x + 96, yy), (255, 170, 150), 11)
            text(canvas, "→ " + TIP_SHORT[pid], (r.right + 6, yy), (230, 232, 240), 11)
        else:
            text(canvas, "???", (x + 14, yy), (120, 126, 150), 11)
            text(canvas, "아직 만나지 못한 패턴", (x + 96, yy), (120, 126, 150), 11)
        yy += 17
    text(canvas, "패턴마다 처음 만날 때 시범 카드가 나와요. (설정 → 튜토리얼 다시 보기)", (w // 2, y + ph - 22),
         (140, 230, 150), 11, "center")
    text(canvas, "H 또는 클릭: 닫기", (w // 2, y + ph - 9), (160, 170, 195), 11, "center")
