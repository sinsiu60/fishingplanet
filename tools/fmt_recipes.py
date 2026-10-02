"""data/sfx_recipes.json 정리: 소리마다 한 덩어리, 레이어는 한 줄씩 (사람이 읽고 고치기 쉽게).

  python tools/fmt_recipes.py
"""
import json
import os

P = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "sfx_recipes.json")


def one(v) -> str:
    return json.dumps(v, ensure_ascii=False, separators=(", ", ": "))


def main() -> None:
    d = json.load(open(P, encoding="utf-8"))
    out = ["{"]
    keys = list(d)
    for i, k in enumerate(keys):
        v = d[k]
        comma = "," if i < len(keys) - 1 else ""
        if not isinstance(v, dict) or "layers" not in v:
            out.append(f" {one(k)}: {one(v)}{comma}")
            continue
        out.append(f" {one(k)}: {{")
        items = [(kk, vv) for kk, vv in v.items() if kk != "layers"]
        for kk, vv in items:
            out.append(f"  {one(kk)}: {one(vv)},")
        out.append('  "layers": [')
        for j, ly in enumerate(v["layers"]):
            out.append(f"   {one(ly)}{',' if j < len(v['layers']) - 1 else ''}")
        out.append("  ]")
        out.append(f" }}{comma}")
    out.append("}")
    text = "\n".join(out) + "\n"
    json.loads(text)  # 검사
    open(P, "w", encoding="utf-8").write(text)


if __name__ == "__main__":
    main()
