# 외부 음원·리소스 출처

게임 안의 효과음·음악은 기본적으로 코드로 합성한다 (`src/audio/synth.py` + `data/sfx_recipes.json`, `tools/bake_sfx.py`로 `assets/sfx_generated/`에 미리 구움).
`assets/sfx/`·`assets/music/`에 외부 파일을 넣어 덮어쓸 때는 아래 표에 한 줄씩 기록한다.

**허용 라이선스**: CC0 / 퍼블릭 도메인 / 상업 이용·수정 허용(CC BY는 표기 필수). CC BY-NC(비상업), CC BY-ND(수정 금지), 출처 불명은 쓰지 않는다.

| 게임 안 이름 | 파일 | 원본 제목 | 만든 사람 | 출처 URL | 라이선스 | 수정 내용 | 추가한 날 |
|---|---|---|---|---|---|---|---|
| (예) sfx_hook_success | assets/sfx/sfx_hook_success.ogg | Fishing Rod Snap | 이름 | https://… | CC0 | 길이 0.6초로 자름, 음량 −2dB | 2026-10-02 |
