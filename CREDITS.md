# 외부 음원·리소스 출처

게임 안의 효과음·음악은 기본적으로 코드로 합성한다 (`src/audio/synth.py` + `data/sfx_recipes.json`, `tools/bake_sfx.py`로 `assets/sfx_generated/`에 미리 구움).
`assets/sfx/`·`assets/music/`에 외부 파일을 넣어 덮어쓸 때는 아래 표에 한 줄씩 기록한다.

**허용 라이선스**: CC0 / 퍼블릭 도메인 / 상업 이용·수정 허용(CC BY는 표기 필수). CC BY-NC(비상업), CC BY-ND(수정 금지), 출처 불명은 쓰지 않는다.

| 게임 안 이름 | 파일 | 원본 제목 | 만든 사람 | 출처 URL | 라이선스 | 수정 내용 | 추가한 날 |
|---|---|---|---|---|---|---|---|
| (예) sfx_hook_success | assets/sfx/sfx_hook_success.ogg | Fishing Rod Snap | 이름 | https://… | CC0 | 길이 0.6초로 자름, 음량 −2dB | 2026-10-02 |

## 릴 사운드 · 패턴 성공음 (오디오 최종 팩 — tools/audio/INTEGRATE.md)
릴 감기·돌진·챔질 소리(`assets/sfx/reel/` 11개)는 아래 녹음을 **자르기만** 한 것 (구간 자르기·짧은 페이드·공통 음량 1회·반복 이음새 크로스페이드, 피치·필터·재합성 없음 — `tools/audio/cut_reel_clips.py`).
패턴 성공음(`assets/sfx/success/` 14개)과 퍼펙트 '팡'·'반짝임'(`assets/sfx/success_stems/`)은 원본 릴 꼬리 + **직접 합성한 보조 레이어**
(팽팽한 낚싯줄 울림 · 줄이 물을 가르는 소리 · 물고기가 끌려오는 물소리 · 낚싯대에 힘이 실리는 저음 · 퍼펙트 '팡') — `tools/audio/make_success_sfx.py`, `make_perfect_pop.py`.

| 게임 안 이름 | 파일 | 원본 제목 | 만든 사람 | 출처 URL | 라이선스 | 수정 내용 | 추가한 날 |
|---|---|---|---|---|---|---|---|
| 릴 클립 (assets/sfx/reel/*) · 성공음의 릴 꼬리 | tools/audio/source/reel_recording.wav | audiopapkin-fishing-reel-302355.mp3 | | | | 구간 자르기·페이드·공통 음량만 (음색 변형 없음) | 2026-10-03 |
| 성공음 보조 레이어 (줄·물·낚싯대·팡) | assets/sfx/success/*, assets/sfx/success_stems/* | — | 직접 합성 (이 프로젝트) | — | 이 프로젝트 | — | 2026-10-03 |

## 글꼴
시작 화면 '시우 공방'의 글자("시우 공방" · "SIU GONGBANG")는 갈무리 글꼴로 미리 그린 그림이다 (`assets/branding/siu_splash_text.png`, `tools/art/make_logo.py splash`). 게임에 글꼴 파일은 넣지 않았다.

| 게임 안 이름 | 파일 | 원본 제목 | 만든 사람 | 출처 URL | 라이선스 | 수정 내용 | 추가한 날 |
|---|---|---|---|---|---|---|---|
| 시작 화면 로고 글자 | assets/branding/siu_splash_text.png · siu_logo_horizontal*.png | 갈무리 (Galmuri14 · Galmuri7) 2.40.3 | 이민서 (quiple) | https://github.com/quiple/galmuri | SIL Open Font License 1.1 | 글자를 픽셀 그림으로 렌더링 | 2026-10-04 |
