"""유리병 편지 (CORE_UPDATE CU9): 일반 판정 자리의 0.7% 로 물고기 대신 유리병 — data/story/bottles.json 12장.
모은 것은 save.data["bottles"] (id 목록) + 낚시 일지 한 줄, 12장 다 모으면 칭호 (core.json variety.bottle_title)."""
import random

from src.core.config import load_json


def letters() -> list[dict]:
    return load_json("story/bottles.json")["letters"]


def collected(save) -> list[str]:
    return save.data.setdefault("bottles", [])


def remaining(save) -> list[dict]:
    have = set(collected(save))
    return [b for b in letters() if b["id"] not in have]


def take(save, rnd=random) -> tuple[dict | None, bool]:
    """아직 안 모은 편지 하나 (12번째 = 할아버지 마지막 쪽지는 맨 마지막). (편지, 방금 다 모음)."""
    left = remaining(save)
    if not left:
        return None, False
    pool = [b for b in left if b["id"] != "B12"] or left
    b = rnd.choice(pool)
    collected(save).append(b["id"])
    _journal(save, b)
    done = not remaining(save)
    if done:
        tid = load_json("core.json")["variety"]["bottle_title"]
        cos = save.data.setdefault("cosmetics", {"titles": [], "float_skins": [], "rod_skins": []})
        if tid not in cos.setdefault("titles", []):
            cos["titles"].append(tid)
    return b, done


def _journal(save, b: dict) -> None:
    """낚시 일지에 한 줄: "유리병 편지 (n/12) — 보낸 이: 첫 줄"."""
    from src.story import story
    try:
        st = story.state(save)
    except (KeyError, TypeError):
        return
    first = b["text"].split("\n")[0]
    n = len(collected(save))
    st.setdefault("journal", []).append({"id": f"bottle:{b['id']}", "day": int(save.data.get("day", 1)),
                                         "text": f"유리병 편지 ({n}/12) — {b['from']}: {first}"})


def body(b: dict) -> str:
    return f"[{b['from']}]\n\n{b['text']}"
