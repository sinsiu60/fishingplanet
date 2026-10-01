"""배경음악: data/music/ 에 파일을 넣으면 자동으로 재생된다 (없으면 조용히 건너뜀).

파일 이름 규칙 (확장자 .ogg / .mp3 / .wav):
- spot_<낚시터id>   낚시터 평상시 음악      예) spot_reservoir.ogg
- fight_<낚시터id>  그 낚시터 파이팅 음악   예) fight_reservoir.ogg
- legend_<물고기id> 전설 테마              예) legend_golden_carp.ogg

pygame.mixer.music 으로 스트리밍하므로 메모리를 거의 쓰지 않는다.
곡 전환은 페이드 아웃 → 페이드 인.
"""
import pygame

from src.core.paths import data_path

EXTS = (".ogg", ".mp3", ".wav")
FADE_OUT_MS = 900
FADE_IN_MS = 1200


class Music:
    def __init__(self, sfx):
        self.sfx = sfx               # 볼륨·오디오 사용 가능 여부를 함께 쓴다
        self.current: str | None = None   # 지금 나오는 곡
        self.target: str | None = None    # 나와야 하는 곡
        self.fading = False
        self.gain = 0.6              # 효과음보다 살짝 작게
        self._paths: dict[str, str | None] = {}

    def path(self, key: str) -> str | None:
        if key not in self._paths:
            found = None
            for ext in EXTS:
                p = data_path("music", key + ext)
                if p.exists():
                    found = str(p)
                    break
            self._paths[key] = found
        return self._paths[key]

    def has(self, key: str | None) -> bool:
        return key is not None and self.path(key) is not None

    def play(self, key: str | None) -> None:
        """나와야 하는 곡을 알려준다 (매 프레임 불러도 됨). 파일이 없는 곡은 무음."""
        self.target = key if self.has(key) else None

    def update(self) -> None:
        if not self.sfx.enabled:
            return
        pygame.mixer.music.set_volume(self.sfx.volume * self.gain)
        if self.target == self.current and not self.fading:
            return
        if self.current is not None and pygame.mixer.music.get_busy():
            if not self.fading:
                pygame.mixer.music.fadeout(FADE_OUT_MS)
                self.fading = True
            return
        # 페이드 아웃이 끝났거나 아무것도 안 나오는 중 → 새 곡
        self.fading = False
        self.current = self.target
        if self.current is None:
            return
        try:
            pygame.mixer.music.load(self.path(self.current))
            pygame.mixer.music.play(loops=-1, fade_ms=FADE_IN_MS)
        except pygame.error:
            self._paths[self.current] = None  # 읽을 수 없는 파일은 다시 시도하지 않음
            self.current = self.target = None

    def stop(self) -> None:
        if self.sfx.enabled:
            pygame.mixer.music.stop()
        self.current = self.target = None
        self.fading = False
