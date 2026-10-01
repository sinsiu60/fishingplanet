"""data/ 폴더의 JSON 로더."""
import json
from functools import lru_cache

from src.core.paths import data_path


@lru_cache(maxsize=None)
def load_json(name: str) -> dict:
    with open(data_path(name), encoding="utf-8") as f:
        return json.load(f)


def game_config() -> dict:
    return load_json("game_config.json")
