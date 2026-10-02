외부 효과음 덮어쓰기 폴더 (DESIGN.md 32장 사운드)

여기에 <소리 이름>.ogg (또는 .wav) 를 넣으면 게임이 합성음 대신 이 파일을 쓴다.
- 새 이름 규칙: sfx_hook_success.ogg, sig_release.ogg, ui_click.ogg ...
- 기존 이름도 덮어쓸 수 있다: hookset.ogg, splash.ogg ...
- 이름 목록: data/sfx_recipes.json (새 소리), src/audio/sfx.py 의 bank (기존 소리)

외부 음원은 상업 이용이 되는 것만 (CC0 권장). 넣으면 반드시 프로젝트 루트 CREDITS.md 에 출처·라이선스를 적는다.
