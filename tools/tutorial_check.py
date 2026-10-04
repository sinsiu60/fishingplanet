"""튜토리얼 문구 검사 (TUTORIAL.md TU7-2·6).

  python tools/tutorial_check.py

1. data/tutorials.json 의 모든 문구(단계 문구 · 콤보 "첫 번째!" 등 · 돈 부족 문구 · "참는 중…" · "손을 떼세요!")가
   TUTORIAL.md 원문(또는 TG-PH 는 PHANTOM_FISH.md 6번) 안에 그대로 있는지
2. 조작 이름 {이름} 을 PC·모바일로 바꿨을 때 남는 {…} 가 없는지
3. 환상 비밀: TG-PH 말고는 어떤 튜토리얼 문구에도 '환상' 이 없는지
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main() -> int:
    tuts = json.load(open(os.path.join(ROOT, "data", "tutorials.json"), encoding="utf-8"))["tutorials"]
    inputs = json.load(open(os.path.join(ROOT, "data", "tutorial_inputs.json"), encoding="utf-8"))["inputs"]
    doc = open(os.path.join(ROOT, "TUTORIAL.md"), encoding="utf-8").read()
    ph = open(os.path.join(ROOT, "PHANTOM_FISH.md"), encoding="utf-8").read()
    ph = re.sub(r"\n>[ \t]*", " ", ph)   # 인용 문단 (> 여러 줄) = 한 문단
    flat = doc.replace('"', "")   # 문구 사이에 따옴표가 낀 줄 (예: "지금! 박자 사이에 감으세요!" {감기})
    bad = 0
    n = 0
    for tid, t in tuts.items():
        texts = [(f"{tid} {i + 1}단계", s["text"]) for i, s in enumerate(t["steps"])]
        texts += [(f"{tid} 콤보", x) for x in t.get("chain_texts", [])]
        texts += [(f"{tid} {k}", t[k]) for k in ("hold_text", "again_text") if k in t]
        texts += [(f"{tid} 돈 부족", s["short_text"]) for s in t["steps"] if s.get("short_text")]
        for where, txt in texts:
            n += 1
            src = ph if tid == "TG-PH" and "환상의 물고기" in txt or "물결이 숨을" in txt else doc
            if txt not in src and txt not in flat:
                print(f"[원문과 다름] {where}: {txt}")
                bad += 1
            for kind in ("pc", "mobile"):
                out = re.sub(r"\{([^}/]+)\}", lambda m: inputs[m.group(1)][kind] if m.group(1) in inputs else m.group(0), txt)
                if re.search(r"\{[^}]*\}", out):
                    print(f"[조작 이름 못 바꿈] {where} ({kind}): {out}")
                    bad += 1
            if tid != "TG-PH" and "환상" in txt:
                print(f"[환상 비밀] {where}: {txt}")
                bad += 1
    # 대본이 문구를 바꾸는 곳: 방향 전환 {왼쪽} → {오른쪽}
    for k in ("왼쪽", "오른쪽", "위", "아래", "감기", "숙이기", "드랙내리기", "순간최저", "연타", "원", "손떼기"):
        if k not in inputs:
            print(f"[조작 이름 없음] {{{k}}}")
            bad += 1
    print(f"문구 {n}개 · 튜토리얼 {len(tuts)}개 · 문제 {bad}개")
    print("결과:", "ok" if not bad else "확인 필요")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
