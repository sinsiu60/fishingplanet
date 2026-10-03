# 🎣 릴 오디오 통합 (클라우드 Claude Code용)

이 폴더(`reel_audio_upload/`)를 GitHub 저장소 루트에 올린 뒤, 아래 프롬프트를 Claude Code에 붙여넣으세요.
Claude Code가 파일 이동, 소리 생성, 게임 연결까지 전부 합니다.

## 들어 있는 파일

| 파일 | 내용 |
|------|------|
| reel_recording.wav | 원본 릴 녹음 (모노 44.1kHz) |
| reel_from_recording.py | 녹음에서 클릭 그레인 추출·재배치 |
| drag_zing.py | 드랙 지이잉 (줄 풀리는 속도 = 피치) |
| bake_reel_audio.py | 게임용 파일 102개 + manifest.json 일괄 생성 |
| requirements-dev.txt | 생성에만 필요한 라이브러리 (numpy, scipy) |
| CREDITS_reel.md | 녹음 출처 기록 |

---

## 붙여넣을 프롬프트

```
저장소 루트의 reel_audio_upload/ 폴더에 릴 오디오 재료를 올려뒀어.
reel_audio_upload/REEL_AUDIO_INTEGRATE.md를 읽고 아래대로 진행해줘.

[1. 파일 배치]
- reel_from_recording.py, drag_zing.py, bake_reel_audio.py, requirements-dev.txt, CREDITS_reel.md
  → tools/audio/ 로 이동
- reel_recording.wav → tools/audio/source/reel_recording.wav 로 이동
- 이동이 끝나면 reel_audio_upload/ 폴더 삭제

[2. 소리 생성]
- tools/audio/requirements-dev.txt 설치 (numpy, scipy). 게임 실행용 requirements에는 넣지 말고 개발용 의존성에 합치기
- 프로젝트 루트에서 python tools/audio/bake_reel_audio.py 실행
- assets/sfx_generated/reel/ 에 파일 102개 + manifest.json 생성 확인
  (릴 감기 루프 54, 드랙 루프 12, 시작·멈춤 6, 지잉 30)
- 빌드 스크립트의 미리 굽기 단계에도 이 명령 추가
  (생성 결과는 저장소에 커밋해서, 빌드 환경에 scipy가 없어도 되게)

[3. 릴 감기]
- 기존 릴 감기 사운드를 manifest의 reel_loops로 교체
- 현재 감기 속도(핸들 회전/초)와 장력(부하 0~1)에 가장 가까운 루프 2~4개를 음량 비율로 섞어 반복 재생
- 재생 속도를 바꿔서 속도를 표현하지 말 것 (음색 유지)
- 장비한 릴 티어 → manifest의 tier_of_equipment로 음색 선택
- 감기 시작 시 start, 손 떼면 stop 원샷
- 게임의 감기 속도 값이 핸들 회전/초가 아니면 1.0~3.5 범위로 변환하는 매핑 추가

[4. 드랙 (돌진 지이잉)]
- 줄이 풀려나갈 때 manifest의 drag_loops 사용
- 물고기가 줄을 빼 가는 속도를 clicks_per_sec(150~850)로 변환해서 가까운 두 루프를 섞어 재생
  → 물고기가 빨라지면 피치가 올라가고 지치면 내려감
- 돌진 패턴의 자연음 신호는 이 드랙 소리로 처리

[5. 패턴 성공 지잉]
- 기존 릴 감기 기반 지잉은 제거하고 manifest의 zing으로 교체
- 등급: 일반 대응 성공 small / 꼬임 해소·역주행 회수·숨기 기습 mid /
  퍼펙트·콤보 완료·이중 패턴 성공 big / 더블 퍼펙트 double
- 같은 파이팅 연속 성공 수에 따라 streak 0~2, 실패 시 0
- small 쿨다운 1.5초, 재생 중 다른 연속음 -3dB
- 퍼펙트는 저음 쿵 + zing big (기존 "챙" 제거)

[6. 규칙 유지]
- SOUND_CLEANUP의 주인공 소리·동시 재생 한도·강조 등급 규칙 그대로
- 장소 잔향은 기존 방식대로 재생 시 적용
- 동시에 섞는 루프 최대 4개 (모바일 부담)

[7. 출처]
- tools/audio/CREDITS_reel.md 내용을 프로젝트 CREDITS.md에 합치기 (출처·라이선스 칸은 비워둔 채로)

[8. 확인 후 커밋]
- 사운드 테스트 룸에서 릴 속도·부하·티어 전환, 드랙 피치 변화, 지잉 등급별 재생 확인
- 게임 실행, 모바일 미리보기, 기존 세이브 불러오기 테스트
- 문제 없으면 변경 사항 커밋
```
