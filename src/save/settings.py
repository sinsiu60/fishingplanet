"""설정 저장 (내 문서/FishingPlanet/settings.json). 튜토리얼 진행, 화면 흔들림 등."""
import json

from src.core.paths import save_dir

DEFAULTS = {"tutorial_seen": [], "screen_shake": True, "volume": 0.8, "scale": None, "sound_captions": False,
            # 모바일 터치 버튼: 크기·투명도 0~2단계, 왼손잡이(좌우 반전)
            "touch_size": 1, "touch_alpha": 1, "touch_left": False,
            # 모바일: 진동 0=끔 1=약 2=중 3=강, 화면 갱신 30/60 (메뉴 화면은 늘 30)
            "vibration": 2, "fps": 60,
            # 접근성 (31장 C6): 예고 시간 배율 0=1.0 1=1.25 2=1.5, 첫 만남 카드, 신호 슬롯 크기 0~2, 색약 팔레트, 소리 신호
            "tele_mult": 0, "signal_cards": True, "slot_size": 1, "colorblind": False, "signal_sound": True,
            # 소리 (32장 S3): 버스 볼륨 0~1, 신호 강조, 오디오 지연 보정(ms, + = 소리가 늦게 들리는 기기)
            "vol_music": 0.8, "vol_sfx": 1.0, "vol_amb": 0.8, "signal_boost": False, "audio_offset_ms": 0,
            "signal_mode": 0,
            "success_sfx": True,  # 패턴 성공 '지이이잉' (32-16 Z3)
            "fight_music": True,
            "bobber_zoom": True,
            "reduce_fx": False,  # 화면 효과 줄이기 (환상 파장 대신 0.8초 페이드)  # 찌 확대 말풍선 (찌·다가오는 그림자를 크게)  # 일반 파이팅 음악 (32-16 Z4) — 끄면 대기 층 낮추기만  # 신호음: 0 자연음 / 1 보조음 / 2 강조 (SOUND_CLEANUP N2)
            # 성능 표시 (FPS·단계별 처리 시간, v0.8.8)
            "perf_overlay": False}

TELE_MULTS = (1.0, 1.25, 1.5)


class Settings:
    def __init__(self):
        self.data = dict(DEFAULTS)
        try:
            with open(self._path(), encoding="utf-8") as f:
                self.data.update(json.load(f))
        except (OSError, ValueError):
            pass

    @staticmethod
    def _path():
        return save_dir() / "settings.json"

    def get(self, key):
        return self.data.get(key, DEFAULTS.get(key))

    def set(self, key, value) -> None:
        self.data[key] = value
        self.save()

    def save(self) -> None:
        try:
            with open(self._path(), "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except OSError:
            pass  # 저장 실패해도 게임은 계속
