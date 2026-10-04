"""NPC 대사 고르기 (DESIGN.md 35-3). Y4: 마을 데이터의 기본 대사 — Y6 에서 조건·우선순위 대사 시스템으로 바뀐다."""
import random

from src.core.config import load_json


def _npc(npc_id: str) -> dict:
    for cont in ("sharmion", "eldrasion"):
        n = load_json("villages.json")[cont]["npcs"].get(npc_id)
        if n:
            return n
    return {"name": npc_id, "lines": ["…"]}


def pick(game, npc_id: str, cont: str) -> list[str]:
    return [random.choice(_npc(npc_id)["lines"])]


def gallery_comment(save, fish: dict) -> str:
    return random.choice(["오호, 이 비늘 결 좀 보십시오!", "훌륭한 탁본입니다. 물고기가 웃고 있군요.",
                          f"{fish['name'].split(' ')[0]}… 이 녀석은 제 연구 노트에도 있지요!"])
