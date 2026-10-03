"""상태 연동 연속 사운드 (DESIGN.md 32장 S4): 숫자처럼 상태를 알려 주는 소리.

  릴 감기     감기 속도 → 클릭 간격(빠를수록 촘촘)·피치(#0~4)
  드랙 풀림   줄이 풀리는 속도 → 바람 '휘이잉' 반복음 높이(#0~3)·음량 (v0.8.13: 예전 '지이잉'은 거슬려서)
  장력 삐걱임 장력 → 신음 반복음 단계(#0~2)·음량, 빨강 구간이면 떨리는 삐걱(red)으로
  줄 실금     내구도 50% 아래부터 '지직' — 낮을수록 잦고 크게
  드랙 단계   단계가 바뀔 때마다 묵직한 '딸깍' (단계 = 피치)
  몸부림     물고기가 움직일 때 가끔 첨벙 — 가까울수록 크게

낚시 화면은 매 틱 update(dt, values)를 부르고(values = 아래 SLIDERS 키), 사운드 테스트 룸은 슬라이더 값으로 부른다.
연속음끼리 겹쳐도 지저분하지 않게: 삐걱임은 감기·드랙 소리가 날 때 한 단계 낮추고, 드랙 풀림이 크면 클릭을 줄인다.
"""
import random

SLIDERS = [
    {"key": "reel", "label": "감기 속도", "min": 0.0, "max": 3.0, "default": 1.2},
    {"key": "payout", "label": "줄 풀림", "min": 0.0, "max": 1.0, "default": 0.0},
    {"key": "tension", "label": "장력", "min": 0.0, "max": 110.0, "default": 50.0},
    {"key": "line", "label": "줄 내구도", "min": 0.0, "max": 1.0, "default": 1.0},
    {"key": "drag", "label": "드랙 단계", "min": 0.0, "max": 4.0, "default": 2.0},
    {"key": "near", "label": "물고기 가까움", "min": 0.0, "max": 1.0, "default": 0.5},
]
RED = 75.0  # 테스트 룸에선 이 위가 빨강 (게임에선 물고기별 green_high)


class FightAudio:
    def __init__(self, sfx):
        self.sfx = sfx
        self.click_t = 0.0
        self.crack_t = 1.0
        self.thrash_t = 1.5
        self.loops: dict[str, str | None] = {"drag": None, "strain": None}
        self.last_drag = None

    def _loop(self, slot: str, name: str | None, vol: float = 1.0) -> None:
        cur = self.loops[slot]
        if cur != name and cur is not None:
            self.sfx.loop(cur, False)
        if name is not None:
            self.sfx.loop(name, True, vol)
        self.loops[slot] = name

    def stop(self) -> None:
        for slot in self.loops:
            self._loop(slot, None)
        self.last_drag = None

    def update(self, dt: float, v: dict, red_at: float = RED, active: bool = True) -> None:
        reel, payout, tension = v.get("reel", 0.0), v.get("payout", 0.0), v.get("tension", 0.0)
        line, drag, near = v.get("line", 1.0), v.get("drag"), v.get("near", 0.5)
        # 드랙 풀림: 바람 휘이잉 (풀리는 속도 → 높이 단계·음량). 살짝 풀릴 땐 안 내서 파이팅 내내 깔리지 않게
        if payout > 0.12:
            step = min(3, int(payout * 4))
            self._loop("drag", f"sfx_drag_run#{step}", 0.12 + 0.45 * payout)
        else:
            self._loop("drag", None)
        # 릴 감기: 클릭 간격·피치 (드랙이 크게 풀리면 클릭은 묻히니 줄인다)
        if reel > 0.05 and payout < 0.6:
            self.click_t -= dt
            if self.click_t <= 0:
                self.click_t = max(0.022, 0.16 / (0.4 + reel))
                step = min(4, int(reel / 3.0 * 5))
                self.sfx.play(f"sfx_reel_click#{step}", 0.35 + 0.1 * min(1.0, reel / 2))
        # 장력 삐걱임: 단계·음량, 빨강이면 떨림
        if tension >= red_at:
            self._loop("strain", "sfx_rod_strain_red", min(1.0, 0.45 + (tension - red_at) / 40))
        elif tension > 30:
            k = (tension - 30) / max(1.0, red_at - 30)
            step = min(2, int(k * 3))
            busy = reel > 0.05 or payout > 0.05
            self._loop("strain", f"sfx_rod_strain#{step}", (0.12 + 0.4 * k) * (0.7 if busy else 1.0))
        else:
            self._loop("strain", None)
        # 줄 실금: 내구도 50% 아래, 낮을수록 잦고 크게
        if line < 0.5:
            self.crack_t -= dt
            if self.crack_t <= 0:
                k = 1 - line / 0.5
                self.crack_t = random.uniform(0.8, 1.4) * (1.8 - 1.4 * k)
                self.sfx.play("sfx_line_crack", 0.3 + 0.6 * k)
        # 드랙 단계 딸깍
        if drag is not None:
            d = int(round(drag))
            if self.last_drag is not None and d != self.last_drag:
                self.sfx.play(f"sfx_drag_step#{max(0, min(4, d))}", 0.7)
            self.last_drag = d
        # 몸부림 첨벙 (가까울수록 크게)
        if active:
            self.thrash_t -= dt
            if self.thrash_t <= 0:
                self.thrash_t = random.uniform(0.9, 2.2)
                self.sfx.play("sfx_thrash", 0.15 + 0.6 * near)
