"""스토리 검증 (STORY.md ST8, DESIGN.md 36). 실행: python tools/story_check.py [기준 커밋]

1. 동기화: STORY.md 로 data/story 를 다시 만들었을 때 지금 파일과 같은가 (수작업 수정 없음)
2. 원문: data/story 의 모든 문장(대사·자막·일지·휴대폰·목표·편지)이 STORY.md 에 글자 그대로 있는가
3. 빠짐: STORY.md 의 대사 표 각 줄 · 굵은 따옴표 자막이 data/story 에 있는가
4. 순서·발생: 장면마다 재생 경로가 있는가 (장소 장면 ORDER / 컷신 SPECS / 전용 실행)
5. 안 바뀜: 기준 커밋(기본: 스토리 문서만 들어간 커밋) 대비 해금 조건 · 가격 · 엔딩 문구 · 도주 안내 문구 · 수첩 본문
"""
import json
import os
import re
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import story_extract as X  # noqa: E402

ROOT = X.ROOT
DATA = os.path.join(ROOT, "data", "story")
NAMES = ("scenes", "journal", "phone", "goals", "letters", "chapters")
BASE = sys.argv[1] if len(sys.argv) > 1 else "add4f6e"
errors: list[str] = []


def load(name: str) -> dict:
    return json.load(open(os.path.join(DATA, f"{name}.json"), encoding="utf-8"))


def check_sync() -> None:
    import story_build
    with tempfile.TemporaryDirectory() as tmp:
        story_build.OUT = tmp
        story_build.main()
        for n in NAMES:
            a = json.load(open(os.path.join(tmp, f"{n}.json"), encoding="utf-8"))
            if a != load(n):
                errors.append(f"[동기화] data/story/{n}.json 이 STORY.md 에서 다시 만든 것과 다르다")


def texts() -> list[tuple[str, str]]:
    """(어디, 문장) — 화면에 나오는 모든 문장."""
    out = []
    for sid, sc in load("scenes").items():
        if sid.startswith("_"):
            continue
        for ln in sc.get("lines", []):
            if isinstance(ln, list):
                out.append((sid, ln[2]))
        for s in sc.get("subs", []):
            out.append((sid, s))
        for s in sc.get("choices", []):
            out.append((sid, s))
    for jid, e in load("journal")["entries"].items():
        out.append((jid, e["text"]))
    for mid, m in load("phone")["messages"].items():
        out.append((mid, m["text"]))
        if m.get("from"):
            out.append((mid, m["from"]))
    for g in load("goals")["goals"]:
        out.append(("goal", g["text"]))
    lt = load("letters")
    for k in ("letter", "last_page"):
        out.append((k, lt[k]))
    return out


def check_verbatim(md: str) -> None:
    for where, s in texts():
        if s not in md:
            errors.append(f"[원문] {where}: STORY.md 에 없는 문장 → {s!r}")


def check_coverage(md: str) -> None:
    have = {s for _, s in texts()}
    S = X.sections(md)
    for sid, body in S.items():
        for table in X.dialogue_tables(body):
            for who, _expr, txt in table:
                if who.startswith("**"):
                    continue
                if txt not in have:
                    errors.append(f"[빠짐] {sid}: 대사 → {txt!r}")
        for q in re.findall(r'자막\s*\*\*"(.*?)"\*\*', body):
            if q not in have:
                errors.append(f"[빠짐] {sid}: 자막 → {q!r}")


def check_paths() -> None:
    sys.path.insert(0, ROOT)
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    from src.story import story
    from src.story.cutscene import SPECS
    special = {"C3-02", "C3-04", "C4-01", "C5-04", "C5-05", "E-01", "P-05"}
    for sid, sc in load("scenes").items():
        if sid.startswith("_"):
            continue
        place = sc.get("place", "")
        if place.startswith("interior:") and sid not in story.ORDER and sid not in special:
            errors.append(f"[발생] {sid}: 장소 장면인데 ORDER 에 없음")
        if not place.startswith("interior:") and sid not in SPECS and sid not in special:
            errors.append(f"[발생] {sid}: 재생 경로 없음")
    # 환상 연결은 환상어 안내(튜토리얼) 전에는 절대 나오지 않는다
    src = open(os.path.join(ROOT, "src", "story", "story.py"), encoding="utf-8").read()
    for pid in ("PH-01", "PH-02"):
        if not re.search(r'"%s":\s*tut\b' % pid, src):
            errors.append(f"[비밀] {pid}: 발생 조건에 환상어 안내(tutorial) 확인이 없다")


def git_show(path: str) -> str | None:
    try:
        return subprocess.run(["git", "show", f"{BASE}:{path}"], cwd=ROOT, capture_output=True, text=True,
                              check=True).stdout
    except subprocess.CalledProcessError:
        return None


def check_unchanged() -> None:
    def js(path):
        old = git_show(path)
        return (json.loads(old) if old else None), json.load(open(os.path.join(ROOT, path), encoding="utf-8"))

    old, new = js("data/spots.json")
    if old is not None:
        o = {s["id"]: s.get("unlock") for s in old["spots"]}
        n = {s["id"]: s.get("unlock") for s in new["spots"]}
        if o != n:
            errors.append("[안 바뀜] 낚시터 해금 조건이 바뀌었다 (data/spots.json)")

    def prices(obj, acc, path=""):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k in ("price", "cost", "sell") and isinstance(v, (int, float)):
                    acc[path + "." + k] = v
                else:
                    prices(v, acc, path + "." + str(obj.get("id", k)) if k != "id" else path)
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                prices(v, acc, path + f"[{v.get('id', i) if isinstance(v, dict) else i}]")
        return acc
    for p in ("data/equipment.json", "data/baits.json", "data/floats.json", "data/lure.json", "data/spots.json",
              "data/continents.json", "data/fish.json"):
        old, new = js(p)
        if old is not None and prices(old, {}) != prices(new, {}):
            errors.append(f"[안 바뀜] 가격이 바뀌었다 ({p})")

    def strings(path):
        src = git_show(path)
        cur = open(os.path.join(ROOT, path), encoding="utf-8").read()
        pick = lambda s: set(re.findall(r'"([^"\n]*[가-힣][^"\n]*)"', s))   # noqa: E731
        return (pick(src) if src else None), pick(cur)
    for p, what in (("src/scene/ending.py", "엔딩 문구"), ("src/scene/escape_tutorial.py", "도주 안내 문구")):
        o, n = strings(p)
        if o is not None and o - n:
            errors.append(f"[안 바뀜] {what}가 바뀌었다 ({p}): {sorted(o - n)[:3]}")
    old, new = js("data/phantom_hints.json")
    if old is not None and old.get("diary") != new.get("diary"):
        errors.append("[안 바뀜] 수첩 본문이 바뀌었다 (data/phantom_hints.json diary)")
    if old is not None and len(new.get("diary", {})) != 12:
        errors.append(f"[안 바뀜] 수첩은 12장이어야 한다 (지금 {len(new.get('diary', {}))})")


def main() -> int:
    md = X.story_text()
    check_sync()
    check_verbatim(md)
    check_coverage(md)
    check_paths()
    check_unchanged()
    n = len(texts())
    if errors:
        for e in errors:
            print(e)
        print(f"실패 {len(errors)}건 (문장 {n}개 검사)")
        return 1
    print(f"ok — 문장 {n}개 STORY.md 원문 그대로, 빠짐 없음, 기준 {BASE} 대비 해금·가격·엔딩·도주 문구·수첩 그대로")
    return 0


if __name__ == "__main__":
    sys.exit(main())
