"""사운드 재생 지점 전수 점검 (DESIGN.md 32-14, Phase S8).

src/ 안의 sfx.play(...) / sfx.loop(...) / play_hit 등 소리 이름(문자열·f-string)을 모두 찾아
  - 없는 소리 (재생하면 무음)            → 0개여야 함
  - 새 이름 규칙(sfx_/sig_/mus_/amb_/ui_)이 아닌 예전 내장 합성음 → 0개여야 함
  - 레시피·내장음 중 아무 데서도 안 쓰는 소리
를 보여 준다.

  python tools/sound_audit.py          표
  python tools/sound_audit.py --strict 문제가 있으면 종료 코드 1 (CI용)
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

NEW = ("sfx_", "sig_", "mus_", "amb_", "ui_")
CALL = re.compile(r"""\.(play|loop)\(\s*(f?)(["'])(.+?)\3""")
COND = re.compile(r"""\.(play|loop)\(\s*["']([\w#]+)["']\s+if\s+.+?\s+else\s+["']([\w#]+)["']""")
SKIP = {"src/scene/sound_test.py"}  # 목록에서 고른 이름을 그대로 재생


def scan() -> list[tuple[str, int, str]]:
    out = []
    for d, _, files in os.walk("src"):
        for f in files:
            if not f.endswith(".py"):
                continue
            p = os.path.join(d, f).replace(os.sep, "/")
            if p in SKIP:
                continue
            for i, line in enumerate(open(p, encoding="utf-8"), 1):
                if "music.play" in line or "pygame.mixer.music" in line:
                    continue  # data/music 스트리밍 곡 이름
                for m in COND.finditer(line):
                    out += [(p, i, m.group(2)), (p, i, m.group(3))]
                for m in CALL.finditer(line):
                    if COND.search(line):
                        continue
                    name = m.group(4)
                    out.append((p, i, ("f:" if m.group(2) else "") + name))
    return out


LIT = re.compile(r"""(f?)(["'])((?:sfx|sig|mus|amb|ui)_[^"']*)\2""")


def literals() -> set[str]:
    """도우미 함수를 거쳐 재생되는 이름 (예: fight_audio._loop("drag", f"sfx_drag_run#{n}")) — '안 쓰는 소리' 판정용."""
    out = set()
    for d, _, files in os.walk("src"):
        for f in files:
            if f.endswith(".py"):
                for m in LIT.finditer(open(os.path.join(d, f), encoding="utf-8").read()):
                    out.add(("f:" if m.group(1) else "") + m.group(3))
    return out


def resolve(name: str, sounds: set) -> list[str]:
    if not name.startswith("f:"):
        return [name] if name in sounds else []
    pat = "^" + re.sub(r"\\\{[^}]*\\\}", r"[\\w#]+", re.escape(name[2:])) + "$"
    return [s for s in sounds if re.match(pat, s)]


def main(argv) -> int:
    import pygame
    pygame.mixer.init(44100, -16, 2, 512)
    from src.audio.sfx import Sfx
    from src.audio import music_synth
    sfx = Sfx()
    sounds = set(sfx.sounds)
    music = set(music_synth.recipes())
    # 다른 경로로 재생되는 이름 (데이터 표·조각 표)
    from src.core.config import load_json
    data_used = set()
    for fam in load_json("signals.json")["families"].values():
        data_used.add(fam["sound"])
    amb = load_json("ambience.json")
    for blk in list(amb["spots"].values()) + list(amb["weather"].values()):
        if blk.get("bed"):
            data_used.add(blk["bed"][0])
        for fr in blk.get("frags", []):
            data_used |= {s for s in sounds if s == fr[0] or (fr[0].endswith("#") and s.startswith(fr[0]))}
    data_used |= {"amb_thunder_near", "amb_thunder_far"}
    rows = scan()
    missing, old, used = [], [], set(data_used)
    for p, i, name in rows:
        hits = resolve(name, sounds | music)
        if not hits:
            missing.append((p, i, name))
            continue
        used |= set(hits)
        for h in hits:
            if not h.startswith(NEW):
                old.append((p, i, h))
    for lit in literals():
        used |= set(resolve(lit, sounds))
    unused = sorted(s for s in sounds if s not in used)
    print(f"재생 지점 {len(rows)}곳 · 소리 {len(sounds)}개 (+ 음악 층 {len(music)}개)")
    print(f"\n[없는 소리] {len(missing)}")
    for r in missing:
        print("  ", *r)
    print(f"\n[예전 이름] {len(old)}")
    for r in old:
        print("  ", *r)
    print(f"\n[안 쓰는 소리] {len(unused)}")
    print("  ", " ".join(unused))
    if "--strict" in argv and (missing or old):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
