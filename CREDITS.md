# 외부 음원·리소스 출처

게임 안의 효과음·음악은 기본적으로 코드로 합성한다 (`src/audio/synth.py` + `data/sfx_recipes.json`, `tools/bake_sfx.py`로 `assets/sfx_generated/`에 미리 구움).
`assets/sfx/`·`assets/music/`에 외부 파일을 넣어 덮어쓸 때는 아래 표에 한 줄씩 기록한다.

**허용 라이선스**: CC0 / 퍼블릭 도메인 / 상업 이용·수정 허용(CC BY는 표기 필수). CC BY-NC(비상업), CC BY-ND(수정 금지), 출처 불명은 쓰지 않는다.

| 게임 안 이름 | 파일 | 원본 제목 | 만든 사람 | 출처 URL | 라이선스 | 수정 내용 | 추가한 날 |
|---|---|---|---|---|---|---|---|
| (예) sfx_hook_success | assets/sfx/sfx_hook_success.ogg | Fishing Rod Snap | 이름 | https://… | CC0 | 길이 0.6초로 자름, 음량 −2dB | 2026-10-02 |

## 릴 사운드 (실제 녹음 재합성 — REEL_AUDIO_INTEGRATE.md)
게임의 릴 감기·드랙·패턴 성공 지잉은 아래 녹음에서 클릭 그레인(약 5ms)을 잘라 다시 배치해 만든다
(`tools/audio/reel_from_recording.py`, `drag_zing.py`, `bake_reel_audio.py` → `assets/sfx_generated/reel/`). 자세한 기록: `tools/audio/CREDITS_reel.md`.

| 게임 안 이름 | 파일 | 원본 제목 | 만든 사람 | 출처 URL | 라이선스 | 수정 내용 | 추가한 날 |
|---|---|---|---|---|---|---|---|
| reel_* · drag_* · zing_* (assets/sfx_generated/reel) | tools/audio/source/reel_recording.wav | audiopapkin-fishing-reel-302355.mp3 | (audiopapkin?) | | | 모노 44.1kHz 변환 → 클릭 그레인 추출·재배치 (속도·부하·티어·드랙·지잉) | 2026-10-03 |

> ⚠ 출처 URL·라이선스는 아직 비어 있다. 위 '허용 라이선스' 기준을 확인해 채우기 전에는 출처 불명 상태 (파일명으로 보아 Pixabay 'audiopapkin' 음원일 가능성이 높음).
