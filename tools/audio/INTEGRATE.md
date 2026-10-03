# 🎣 낚시 게임 오디오 최종 통합

릴 루프, 돌진 소리, 패턴 성공음("쒸익-팽!"), 퍼펙트 "팡"까지 한 번에 넣는 팩입니다.

## 넣는 법 (폰)

1. 폰 브라우저(데스크톱 사이트)로 GitHub 저장소 열기
2. **Add file → Upload files** → `audio_final.zip` 선택 → **Commit changes**
3. Claude Code에 아래 **붙여넣을 프롬프트** 전체 붙여넣기

## 팩 구성

| 경로 | 내용 |
|------|------|
| `manifest.json` | 모든 파일의 용도, 길이, **타격 시점(impact_ms)**, 매핑 규칙 |
| `sfx/reel/` | 원본 녹음을 자르기만 한 릴 클립 11개 (루프 4, 시작·멈춤, 돌진용, 챔질용) |
| `sfx/success/` | 패턴 성공음 14개 (작은·중간·큰·퍼펙트 팡 × 연속 3단계 + 더블 2종) |
| `sfx/success_stems/` | 퍼펙트 "팡"과 "반짝임" 단독 |
| `tools/` | 원본 녹음 + 전체 재생성 스크립트 |

## 파일 → 상황

| 상황 | 소리 |
|------|------|
| 릴 감기 | 속도에 따라 loop_slow / loop_normal_A·B(번갈아) / loop_fast, 시작 reel_start, 멈춤 reel_stop |
| 물고기 돌진 | zing_rise_C(또는 A·B 랜덤) → 줄이 계속 풀리는 동안 loop_fast → 정점에 drag_fast → 끝 reel_stop |
| 챔질·대물 | reel_burst_heavy |
| 일반 대응 성공 | success_small (연속 0~2) |
| 꼬임 해소·역주행 회수·숨기 기습 | success_mid |
| 콤보 완료·이중 패턴 성공 | success_big |
| **퍼펙트** | **success_big_pop** + 노란 이펙트 싱크 |
| **더블 퍼펙트** | **success_double_pop** + 노란 이펙트 2회 |

---

## 붙여넣을 프롬프트

```
저장소 루트에 audio_final.zip을 올렸어. 낚시 게임 오디오 최종 팩이야.
압축을 풀고 audio_final/INTEGRATE.md와 manifest.json을 읽은 뒤 아래대로 통합해줘.

[1. 파일 배치]
- audio_final/sfx/ 전체 → assets/sfx/ 아래로 (reel/, success/, success_stems/ 폴더 유지)
- audio_final/tools/ 전체 → tools/audio/ 아래로 (source/, pull_samples/ 폴더 유지)
- audio_final/manifest.json → assets/sfx/audio_manifest.json
  (manifest 안의 경로 "sfx/..."는 "assets/sfx/..." 기준으로 읽게)
- audio_final/INTEGRATE.md → tools/audio/INTEGRATE.md
- audio_final.zip과 audio_final/ 폴더 삭제

[2. 이전 방식 정리]
- 예전에 만든 릴 합성·재합성 관련 코드와 파일 제거
  (reel_synth.py, reel_from_recording.py, drag_zing.py, bake_reel_audio.py,
   assets/sfx_generated/reel/, 빌드 스크립트의 해당 굽기 단계, 릴 감기 기반 지잉)
- 제거 전에 어디서 쓰이는지 확인하고, 다른 기능이 깨지지 않게 이 팩으로 대체
- 이 팩의 소리는 미리 만들어진 파일이라 빌드 때 굽기 단계가 필요 없음
  (tools/audio/의 스크립트는 소리를 다시 만들고 싶을 때만 수동 실행, scipy는 개발용 의존성)

[3. 재생 원칙]
- 모든 클립은 재생 속도·피치·필터 변경 없이 그대로 재생
- 장소 잔향은 기존 방식대로 재생 시 적용 가능

[4. 릴 감기]
- 감기 속도를 0~1로 정규화해서 manifest의 speed_bands로 slow / normal / fast 선택
- 구간이 바뀌면 0.2초 크로스페이드
- normal은 loop_normal_A와 B를 번갈아 반복 (단조로움 방지)
- 장력(부하)이 높으면 한 단계 느린 구간을 쓰고 음량 +2dB
- 감기 시작 reel_start, 손 떼면 reel_stop
- 동시에 재생되는 릴 루프는 크로스페이드 중에도 최대 2개

[5. 물고기 돌진]
- 돌진 시작: zing_rise_C, zing_rise_A, zing_rise_B 중 랜덤 (같은 것 연속 금지)
- 줄이 계속 풀리는 동안: loop_fast 반복, 돌진 정점에 drag_fast 한 번
- 돌진이 끝나면 reel_stop
- 돌진 중에는 릴 감기 루프 정지 (둘이 겹치지 않게)

[6. 챔질·대물]
- 챔질 성공 임팩트에 reel_burst_heavy, 대형 물고기일수록 음량 크게

[7. 패턴 성공음]
- manifest의 success_mapping대로 등급 선택
  small: 일반 대응 성공 / mid: 꼬임 해소·역주행 회수·숨기 기습 /
  big: 콤보 완료·이중 패턴 성공 / big_pop: 퍼펙트 / double_pop: 더블 퍼펙트
- 같은 파이팅에서 연속 성공 수에 따라 streak0~2 선택 (3번째 이후는 streak2 유지), 실패 시 streak0
- 성공 판정 순간 즉시 재생 (파일 안에 impact_ms만큼 앞부분이 있음)
- small은 쿨다운 1.5초 (겹치면 생략)
- 성공음이 울리는 동안 릴 루프·환경음 -3dB, 0.3초 후 복귀
- 기존 지잉 기반 성공음과 퍼펙트의 "챙" 소리는 제거
- 성공 시 실제 물고기 거리가 등급만큼 줄어드는 로직이 있으면 연출과 맞추기

[8. 퍼펙트 노란 이펙트 싱크]
- success_big_pop 재생 시작 후 manifest의 impact_ms(약 41ms) 시점에 노란 이펙트가 터지게
- 노란 빛이 퍼졌다 사라지는 시간을 perfect_effect.glow_duration_ms(300ms)에 맞추기
- 더블 퍼펙트: 첫 이펙트는 impact_ms, 두 번째 이펙트는 second_impact_ms(약 461ms)
- 오디오 지연 보정 설정값이 있으면 이펙트 타이밍에도 같이 적용
- 모바일 진동도 impact_ms에 맞추기 (일반 성공은 짧게, 퍼펙트는 강하게, 더블은 두 번)

[9. 기존 규칙 유지]
- SOUND_CLEANUP의 주인공 소리·동시 재생 한도·강조 등급 규칙 유지
- 파이팅 음악(복구된 기본 층·위기 층)은 건드리지 말고, 성공음·챔질 때 -3dB 덕킹만 적용
- 설정의 "성공 효과음 켜기/끄기"가 있으면 이 성공음에 연결

[10. 출처]
- CREDITS.md에 릴 녹음 출처 항목 추가
  (원본 파일명 audiopapkin-fishing-reel-302355.mp3, 출처·라이선스 칸은 내가 채울 테니 비워두기)
- 성공음의 보조 레이어(줄·물·낚싯대·팡)는 직접 합성한 소리라고 함께 기록

[11. 확인 후 커밋]
- 사운드 테스트 룸에 다음 추가
  - 릴 속도 슬라이더 + 장력 슬라이더로 루프 전환 확인
  - 돌진 시뮬레이션 버튼
  - 성공음 등급·연속 단계별 재생 버튼
  - 퍼펙트·더블 퍼펙트를 노란 이펙트와 같이 재생해서 싱크 확인
- 훈련 수조에서 실제 파이팅으로 확인
- PC 실행, 모바일 미리보기, 기존 세이브 불러오기
- 문제 없으면 커밋하고, 바뀐 파일 목록과 제거한 파일 목록 알려줘
```
