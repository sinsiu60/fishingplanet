# 🎣 낚시 게임

어렵지만 공정한 1인칭 낚시 게임. 설계는 [DESIGN.md](DESIGN.md) 참고.

## 실행 (Windows)

1. Python 3.12 설치 (설치 첫 화면에서 **"Add python.exe to PATH" 체크**)
2. `run.bat` 더블클릭
   - 처음 실행하면 `setup.bat`이 자동으로 가상환경(`.venv`)을 만들고 라이브러리를 설치합니다.

## 실행 (직접)

```
python -m venv .venv
.venv\Scripts\activate        (macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt
python main.py
```
