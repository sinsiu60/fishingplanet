# REEL_AND_MUSIC Phase Z1 — 진단 (코드 수정 없음)

## 1. 파이팅 음악이 사라진 원인 — 버그가 아니라 N4 음악 절제 설계의 결과

| 원인 | 코드 위치 | 영향 |
|---|---|---|
| ① 대기 음악의 '정적' 상태가 파이팅에도 이어짐 | `adaptive_music.py` update: `rest = self.resting() and st in ("idle", "bite", "fight", "tired")` · `data/music_patterns.json` idle_cycle (울림 3바퀴 ≈ 34초 / 정적 60~180초) | 정적이 평균 120초, 울림 34초 → **파이팅의 약 78%가 정적 중에 시작돼 음악 0** |
| ② 울림 중이어도 파이팅 층이 '대기 층을 낮춘 것'뿐 | music_patterns.json `levels.fight = {pad 0.45, shimmer 0.3}` (타악·긴장 층 없음) | 리듬이 없는 잔잔한 패드 → 파이팅 음악으로 안 들림 |
| ③ 음악 기본 배율을 크게 낮춤 | `adaptive_music.GAIN = 0.35` (예전 0.75) | 파이팅 음악 약 −33dB, 파이팅 중 −4dB 덕킹된 환경음(−32dB)보다도 작음 → 릴·물소리에 묻힘 |
| ④ 대형만 예외 | `fishing_scene._update_music`: 100cm+ → `fight_big = {tension 0.5}` | 대형만 긴장 층 하나 |

볼륨 0·버스 설정·미리 굽기 누락·상태 전환 버그는 아님 (음악 32개 구운 파일 정상, 상태 전환은 설계대로).
→ Z4: ①은 파이팅 상태를 정적에서 빼고, ②는 대륙별 파이팅 기본 층 + 위기 층(새 레이어) 추가, ③은 파이팅 상황에만 state_gain.

## 2. 지금 릴 감기·드랙 소리 구조 (`src/audio/fight_audio.py`)
- **릴 감기**: 한 번 소리 `sfx_reel_click#0~4`를 감기 속도로 정한 간격(0.022~0.4초)마다 재생. 피치 단계 #0~4 = 속도. 부하(장력)·릴 티어 반영 없음.
- **드랙 풀림**: 반복음 `sfx_drag_run#0~3` (v0.8.13 바람 '휘이잉'), 풀리는 속도 > 0.12일 때만, 단계 = 속도.
- **연속음 주인공**(N3): 빨강 > 줄 풀림 > 첨벙 > 노란 > 감기 — 릴·드랙·첨벙 배율, 0.2초 크로스페이드.
- **공간**(N5): 릴 클릭·드랙 바람은 공간별 버전(`~out/~cave/~deep`).
- 회수(RETRIEVE) 때도 릴 클릭 속도 1.6. 멈춤 '딸깍'·가속음 없음.

## 3. `tools/audio/reel_synth.py` 구조 (numpy + **scipy** 필요 — 굽기는 로컬에서만, CI는 `--check`만이라 CI엔 불필요)
| 함수 | 하는 일 | 파라미터 |
|---|---|---|
| `bp/lp/hp` | scipy 버터워스 필터 | 주파수, 차수 |
| `speed_profile(dur, rps, accel, decel)` | 핸들 회전수 곡선 (가속 → 유지 → 감속 + 흔들림) | |
| `tick_kernel(res, decay_ms, wood)` | 기어 이빨 한 번 '틱' (노이즈 + 공명 2개) | |
| `reel(dur, rps, load, tier, stop_click)` | 이빨 틱 + 기어 웅웅(이빨 주파수 추종) + 줄 마찰 + 나무 삐걱(wood) + 맑은 공명(crystal) + 한 바퀴 주기 변조 + 멈춤 딸깍 | rps 1.2/2.0/3.2, load 0~1, tier wood/mid/crystal |
| `drag_scream(dur, peak_rate)` | 드랙 풀림 '지이이잉' (클리커 + 스풀 회전 + 마찰) | |
| `room` · `finish` | 짧은 잔향, 60Hz~8.5kHz, 페이드, tanh 포화, −1dBFS | |
- 주의: 전역 난수(`RNG`) 하나를 호출 순서대로 씀 → 굽기 결과가 호출 순서에 따라 달라짐. Z2에서 소리마다 시드 고정.
- 지금은 '가속→유지→감속'이 들어간 3초짜리 소리 → Z2에서 **유지 구간만, 핸들 정수 바퀴 길이**로 루프를 잘라야 함.
- 기준 소리: `tools/audio/reference/*.wav` 8개 (스크립트를 그대로 돌려 생성 — 받은 wav가 첨부되지 않아서).

⚠ **결정 필요**: 설계 Z2의 '드랙 풀림 루프 4단계'는 `drag_scream`('지이이잉')을 쓰게 되어 있는데,
v0.8.13에서 "파이팅 중 지이이잉이 난잡하다"고 해서 바람 '휘이잉'으로 바꾼 소리입니다.
→ (A) 지금 바람 소리 유지 / (B) drag_scream 기반 실제 릴 드랙 소리로 교체 (단, 풀릴 때만·주인공 규칙 유지).

## 4. 패턴 성공 판정 지점 (설계 2-2 등급 매핑 제안)
| 계열 | 패턴 | 성공 이벤트 (발생 위치) | 제안 등급 |
|---|---|---|---|
| 풀기 | 돌진 | `rush_ok` (fight.py 510) | 작은 지잉 |
| 풀기 | 물어뜯기 | `pattern_ok:bite` (fight.py 486, 판정 patterns.Bite) | 작은 지잉 |
| 풀기 | 숨기 | `pattern_ok:hide` (patterns.Hide — 고개 내밀 때 기습 성공) | **지이잉** |
| 감기 | 역주행 | `pattern_ok:reverse` (회수 완료) | **지이잉** |
| 방향 | 방향 전환 | `flick_perfect` / `flick_good` (fight.py 376) | 퍼펙트면 지이이이잉, 아니면 작은 지잉 |
| 방향 | 잠수 · 수면 질주 | `pattern_ok:dive` · `pattern_ok:surface` | 작은 지잉 |
| 참기 | 머리 흔들기 | `pattern_ok:shake` | 작은 지잉 |
| 타이밍 | 점프·몸털기·공중 몸부림 | `perfect` / `good` (fight.py 459·466) | 퍼펙트 = 지이이이잉, GREAT = 작은 지잉 |
| 타이밍 | 펌핑 | `pattern_ok:pump` (박마다 `pump_hit`는 지잉 없음) | 작은 지잉 |
| 제스처 | 줄 비틀기 | `pattern_ok:twist` (꼬임 완전 해소, 한 바퀴 `twist_turn`은 지잉 없음) | **지이잉** |
| 콤보 | 연쇄 콤보 | `combo_ok` (patterns.py 542, 3연속 완료) | **지이이이잉** |
| 이중 | 이중 패턴 | `dual_ok` (fight.py 573) | **지이이이잉** |
| — | 더블 퍼펙트 | `double_perfect` (fight.py 304) | **더블 지이이이잉** |
- 패턴 결과에 '퍼펙트 등급'이 붙는 경우(`f.last_grade == "perfect"`) → 그 패턴은 지이이이잉으로 올림.
- 실패 이벤트(`pattern_fail:*`, `miss_*`, `flick_miss`, `rush_fail`, `combo_fail`)에서 연속 성공 단계 초기화.

## 5. DESIGN.md 통합 → 32-16 (이 파일과 함께 커밋)
