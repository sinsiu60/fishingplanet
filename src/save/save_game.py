"""게임 진행 저장 (슬롯 3개, 내 문서/FishingPlanet/slot1~3.json).

돈·장비·살림망·도감·통계·현재 시간/낚시터를 담는다. 자동 저장은 FishingScene이 호출한다.

버전 기록:
  1  출시 버전
  2  확장 (대륙·강화·소재·상자·부적·특수 찌 필드). v1 세이브는 불러올 때 원본을 slotN.v1.bak.json으로
     백업한 뒤 새 필드만 기본값으로 채운다 (DESIGN.md 22장). 지우는 필드 없음, unlocked_spots는 그대로.
"""
import copy
import json
import os
import shutil
import threading
import time

from src.core.config import load_json
from src.core.paths import save_dir

SLOTS = 3
VERSION = 4
RANK_ORDER = {"C": 0, "B": 1, "A": 2, "S": 3}
GEAR_KINDS = ("rod", "reel", "line", "net")
TOP_TIER = {"sharmion": 5, "eldrasion": 8}  # 대륙별 상점 최고 티어


def _slot_path(slot: int):
    return save_dir() / f"slot{slot}.json"


def legend_economy() -> dict:
    return load_json("fishing_config.json")["legend_economy"]


def _today() -> str:
    from src.save.quests import today_key
    return today_key()


def rules() -> dict:
    return load_json("equipment.json")["_rules"]


def _deep_merge(base: dict, data: dict) -> dict:
    """data 값을 우선하되, base에만 있는 키(새 버전에서 생긴 필드)는 중첩 dict 안까지 채운다."""
    out = dict(base)
    for k, v in data.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict) and k not in ("dex", "treasure_dex"):
            out[k] = _deep_merge(base[k], v)
        else:
            out[k] = v
    return out


# 장비 강화 (46장 S4 에서 제거) — 옛 세이브 환급용 옛 비용표 (equipment.json _rules 에 있던 값 그대로)
_OLD_ENHANCE = {"gold_frac": [0.15, 0.3, 0.5], "gold_free": [100, 250, 500], "materials": [5, 12, 20], "rare_materials": [0, 0, 3]}


def _refund_enhance(data: dict) -> None:
    """강화된 장비 → +0, 강화에 쓴 골드 · 소재 100% 환급 (옛 비용표 기준) + 처음 불러올 때 안내 1번 · 환영 선물 희귀 비늘석 1개.
    이미 첫 의뢰를 완료했으면 first_quest_bonus 지급 완료 (환영 선물로 대신). 전설 · 환상 첫 포획 비늘석은 소급하지 않음."""
    enh = data.pop("enhance", {}) or {}
    items = {}
    for kind, lst in equipment().items():
        if kind.startswith("_") or not isinstance(lst, list):
            continue
        for g in lst:
            items[g["id"]] = g
    gold = 0
    mats: dict = {}
    for gid, lvl in enh.items():
        g = items.get(gid)
        if g is None or not isinstance(lvl, int):
            continue
        cont = g.get("continent", "sharmion")
        for i in range(min(lvl, 3)):
            gold += round(g["price"] * _OLD_ENHANCE["gold_frac"][i]) if g["price"] > 0 else _OLD_ENHANCE["gold_free"][i]
            mats[cont] = mats.get(cont, 0) + _OLD_ENHANCE["materials"][i]
            mats["rare"] = mats.get("rare", 0) + _OLD_ENHANCE["rare_materials"][i]
    data["money"] = data.get("money", 0) + gold
    m = data.setdefault("materials", {})
    for k, v in mats.items():
        m[k] = m.get(k, 0) + v
    st = data.setdefault("scalestone", {})
    st.setdefault("items", [])
    st.setdefault("equipped", {k: None for k in ("rod", "reel", "line", "net")})
    st.setdefault("next_id", 1)
    st["first_quest_bonus"] = st.get("first_quest_bonus") or data.get("stats", {}).get("quests_done", 0) > 0
    from src.save import scalestone

    class _D:   # scalestone.grant 는 save.data 만 씀
        pass
    holder = _D()
    holder.data = data
    gift = scalestone.grant(holder, "rare", "welcome", "sharmion")
    st["welcome"] = {"pending": True, "gold": gold, "mat": sum(mats.values()),
                     "gift": gift["stone"]["uid"] if gift["stone"] else None}


def migrate(data: dict, slot: int | None = None) -> dict:
    """옛 세이브를 현재 버전으로. 지우지 않고 추가만 한다."""
    ver = data.get("version", 1)
    if ver < 2:
        if slot is not None:
            src, bak = _slot_path(slot), save_dir() / f"slot{slot}.v1.bak.json"
            if src.exists() and not bak.exists():
                try:
                    shutil.copyfile(src, bak)
                except OSError:
                    pass
        conts = ["sharmion"]
        if "dragon_carp" in data.get("dex", {}):
            conts.append("eldrasion")  # 이미 '등용'을 잡았으면 확장을 바로 시작
            spots = data.setdefault("unlocked_spots", ["reservoir"])
            if "marsh" not in spots:
                spots.append("marsh")
            data.setdefault("flags", {})["voyage_pending"] = True
        data.setdefault("unlocked_continents", conts)
        data["version"] = 2
    if data["version"] < 3:
        # 콘텐츠 업데이트 (DESIGN.md 27-8): 새 필드는 _deep_merge가 기본값으로 채운다 — 버전만 올림 (지우는 것 없음)
        if slot is not None and ver == 2:  # v1에서 온 세이브는 이미 v1 백업이 있다
            src, bak = _slot_path(slot), save_dir() / f"slot{slot}.v2.bak.json"
            if src.exists() and not bak.exists():
                try:
                    shutil.copyfile(src, bak)
                except OSError:
                    pass
        data["version"] = 3
    if data["version"] < 4:
        # 콘텐츠 확장 (DESIGN.md 35-5): 도감 별·숙련은 기존 기록에서 계산(소급), 가 본 낚시터 = 지금 해금된 곳 전부
        if slot is not None:
            src, bak = _slot_path(slot), save_dir() / f"slot{slot}.v3.bak.json"
            if src.exists() and not bak.exists():
                try:
                    shutil.copyfile(src, bak)
                except OSError:
                    pass
        data.setdefault("visited", list(data.get("unlocked_spots", ["reservoir"])))
        data["version"] = 4
    if "details" not in data:
        # 디테일 업데이트 이전 세이브: 이미 잡은 종은 입질 연출을 '본 것'으로 (45-D 확정 9) — 나머지 칸은 기본값
        seen = [fid for fid, e in data.get("dex", {}).items() if isinstance(e, dict) and e.get("count", 0) > 0]
        seen += [fid for fid, e in data.get("phantom", {}).get("caught", {}).items() if isinstance(e, dict) and e.get("count", 0) > 0]
        data["details"] = {"seen_hook_cinematic": seen}
    if "tutorial" not in data:
        from src.tutorial import legacy
        legacy.migrate(data)   # 가이드 튜토리얼 이전 세이브: 이미 쓴 시스템은 완료 처리 (DESIGN.md 40)
    if "scalestone" not in data:
        # 비늘석 이전 세이브 (46장): 이미 의뢰를 완료했으면 첫 의뢰 보너스는 지급 완료로 (환영 선물로 대신 — S4)
        done = data.get("stats", {}).get("quests_done", 0) > 0
        data["scalestone"] = {"items": [], "equipped": {k: None for k in ("rod", "reel", "line", "net")},
                              "first_quest_bonus": done, "next_id": 1}
    if "enhance" in data:
        _refund_enhance(data)
    if "legend_sales" not in data:
        # 전설 감가(A+D) 이전에 잡아 둔 살림망 전설은 제값으로 (규칙이 생기기 전에 잡은 것)
        legends = {f["id"] for f in load_json("fish.json")["fish"] if f["rarity"] == "legend"}
        for it in data.get("keepnet", []):
            if it.get("id") in legends:
                it["first"] = True
    return data


def equipment() -> dict:
    return load_json("equipment.json")


def baits() -> dict:
    return {b["id"]: b for b in load_json("baits.json")["baits"]}


def find_gear(kind: str, gear_id: str) -> dict:
    for g in equipment()[kind]:
        if g["id"] == gear_id:
            return g
    return equipment()[kind][0]


def all_fish() -> list[dict]:
    return load_json("fish.json")["fish"]


def fish_by_id(fid: str) -> dict:
    f = next((f for f in all_fish() if f["id"] == fid), None)
    if f is None:  # 환상어 (data/phantom.json — 도감 %·해금 집계 밖)
        from src.fishing.phantom import by_id
        f = by_id(fid)
    if f is None:  # 계절·날씨 이벤트 한정 (도감 %·해금 집계 밖)
        from src.save.dexbook import limited_fish
        f = next((x for x in limited_fish() if x["id"] == fid), None)
    if f is None:
        raise StopIteration(fid)
    return f


def spot_continent(spot_id: str) -> str:
    for s in load_json("spots.json")["spots"]:
        if s["id"] == spot_id:
            return s.get("continent", "sharmion")
    return "sharmion"


def new_data() -> dict:
    eq = equipment()
    now = time.time()
    return {
        "version": VERSION, "created": now, "updated": now, "playtime": 0.0,
        "money": 0, "hour": 7.0, "day": 1, "spot": "reservoir",
        "unlocked_spots": ["reservoir"],
        "gear": {k: eq[k][0]["id"] for k in GEAR_KINDS} | {"bait": "worm"},
        "owned": {k: [eq[k][0]["id"]] for k in GEAR_KINDS} | {"bait": ["worm"]},
        "keepnet": [],
        # 디테일 업데이트 (DESIGN.md 45장): seen_hook_cinematic = 전체 버전 입질 연출을 본 종 (DT4)
        "details": {"seen_hook_cinematic": [], "rod_casts": {}, "release_count": 0, "release_points": 0,
                    "release_points_today": {"date": "", "n": 0},
                    "cat_affection": 0, "cat_fed_date": "", "haru_night_day": 0,   # DT9 마을 고양이 · 하루 아저씨 밤 대사
                    "birthday": None, "birthday_gift_year": 0, "grandpa_marks": [], "photos": []},   # DT11 생일 · 흔적 · 사진
        "dex": {},
        "stats": {"catches": 0, "s_ranks": 0, "perfects": 0, "lost": 0, "earned": 0,
                  "chests_opened": 0, "s_ranks_eldra": 0, "double_perfects": 0, "mutations_caught": 0,
                  "quests_done": 0},
        # ── 확장 (v2) ──
        "continent": "sharmion",
        "unlocked_continents": ["sharmion"],
        # 비늘석 (46장): 보관함 · 장착 칸 4개 · 첫 의뢰 보너스 지급 여부 · 다음 고유 번호
        "scalestone": {"items": [], "equipped": {"rod": None, "reel": None, "line": None, "net": None},
                       "first_quest_bonus": False, "next_id": 1},
        "materials": {"sharmion": 0, "eldrasion": 0, "rare": 0},
        "scales": 0,                                     # 전설 비늘
        "chests": {"common": 0, "rare": 0, "special": 0, "legend": 0},
        "pity": {"special": 0, "legend": 0},
        "shards": 0,
        "items": {"owned": [], "consumables": {}, "charms": [None]},
        "float": {"owned": [], "equipped": None},
        "treasure_dex": {},
        "flags": {"eldra_escape_tutorial": False},
        "buffs": {"lucky_casts": 0, "lunch_until": 0.0, "blessing_until": 0.0},
        "legend_sales": {"day": "", "counts": {}},
        # 환상의 물고기 (33장): 낚시터별 착수 천장 카운트, 환상 도감, 첫 포획 튜토리얼, 수첩, 환상 비늘, 받은 수집 보상, 칭호 보라 테두리
        "phantom": {"casts": {}, "caught": {}, "tutorial": False, "notes": [], "scales": 0, "rewards": [],
                    "title_frame": False, "phase2_seen": []},       # 오늘(실제 날짜) 전설 종별 판매 수 → 반복 판매 감가  # 소모품 효과 (행운의 떡밥 남은 캐스팅, 도시락 끝나는 플레이 시간)
        # ── 콘텐츠 업데이트 (DESIGN.md 27-8) ──
        "patterns_seen": [],                             # 만나 본 신규 패턴 (첫 만남 안내·도감 힌트)
        "pattern_mastery": {},                           # 패턴별 성공 횟수 → 예고 배율 (31장 C5)
        "pattern_fail_streak": {},                       # 패턴별 연속 실패 (3번이면 다음 1번 예고 보조)
        "mutation_dex": {},                              # 물고기 id → 잡아 본 변이 목록
        "cosmetics": {"titles": [], "float_skins": [], "rod_skins": [], "net_skins": []},
        "equipped_cosmetic": {"title": None, "float_skin": None, "rod_skin": None, "net_skin": None},
        "quests": {"points": 0, "done": 0, "boards": {}},  # 챌린지 의뢰 (대륙별 게시판, src/save/quests.py)
        # ── 콘텐츠 확장 v4 (DESIGN.md 35) ──
        "dex_book": {"claimed": [], "cover": None, "seen": None},  # 도감 보상 받은 것·표지·알림 기준 (별·숙련 자체는 계산)
        "prints": {},                                    # 어탁: 물고기 id → {size, date, spot, season, kind}
        "visited": ["reservoir"],                        # 이동 컷신: 첫 방문 기록
        "dialogue": {"heard": [], "recent": {}, "flags": {}},  # 들은 1회성 대사·NPC별 최근 대사·대사용 진행 기록
        "tutorial": {"done": [], "active": None, "enabled": True, "replay": []},   # 가이드 튜토리얼 (DESIGN.md 40)
        "season_seen": None,                             # 마지막으로 마을에서 본 계절 (계절 바뀜 알림)
        "events": {"day": -1, "plan": None, "active": None, "seen": {}},  # 날씨 이벤트 (오늘 계획·진행 중·본 횟수)
    }


def _write_file(path, payload: str) -> bool:
    tmp = path.with_suffix(".tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(payload)
        os.replace(tmp, path)  # 저장 중 꺼져도 기존 파일이 깨지지 않게
        return True
    except OSError:
        return False


class _Writer:
    """자동 저장 파일 쓰기 일꾼 (경로별 최신 내용 하나만 — 같은 슬롯에 연속으로 오면 마지막 것만 쓴다)."""

    def __init__(self):
        self.lock = threading.Lock()
        self.pending: dict = {}
        self.thread = None
        self.wake = threading.Event()

    def submit(self, path, payload: str) -> None:
        with self.lock:
            self.pending[path] = payload
            if self.thread is None:
                self.thread = threading.Thread(target=self._run, name="save-writer", daemon=True)
                self.thread.start()
        self.wake.set()

    def _run(self) -> None:
        while True:
            self.wake.wait()
            with self.lock:
                self.wake.clear()
                items = list(self.pending.items())
                self.pending.clear()
            for path, payload in items:
                _write_file(path, payload)
            with self.lock:
                self.idle.set() if not self.pending else self.idle.clear()

    def flush(self) -> None:
        """기다리는 쓰기를 지금 끝낸다 (종료 · 동기 저장 전)."""
        with self.lock:
            items = list(self.pending.items())
            self.pending.clear()
        for path, payload in items:
            _write_file(path, payload)


_writer = _Writer()
_writer.idle = threading.Event()


class SaveGame:
    def __init__(self, slot: int, data: dict | None = None):
        self.slot = slot
        self.data = data or new_data()

    # ── 슬롯 ──
    @staticmethod
    def load(slot: int) -> "SaveGame | None":
        try:
            with open(_slot_path(slot), encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            return None
        data = migrate(data, slot)
        return SaveGame(slot, _deep_merge(new_data(), data))  # 새 항목은 기본값으로 채움

    @staticmethod
    def summary(slot: int) -> dict | None:
        sg = SaveGame.load(slot)
        if sg is None:
            return None
        d = sg.data
        from src.save.quests import title_name
        return {"money": d["money"], "dex": sg.dex_count(), "dex_total": len(all_fish()),
                "playtime": d["playtime"], "updated": d["updated"], "spot": d["spot"], "title": title_name(sg)}

    @staticmethod
    def latest_slot() -> int | None:
        best, best_t = None, -1.0
        for s in range(1, SLOTS + 1):
            info = SaveGame.summary(s)
            if info and info["updated"] > best_t:
                best, best_t = s, info["updated"]
        return best

    def save(self, sync: bool = True) -> bool:
        """sync=False (자동 저장, OPTIMIZATION.md O6): 직렬화(0.5ms)만 메인에서 하고 파일 쓰기는 일꾼 스레드에서 —
        연속 요청은 마지막 것 하나로 합쳐진다. sync=True (종료 · 장면 전환) 는 앞선 백그라운드 쓰기를 끝낸 뒤 바로 쓴다."""
        self.data["updated"] = time.time()
        path = _slot_path(self.slot)
        try:
            payload = json.dumps(self.data, ensure_ascii=False, indent=1)
        except (TypeError, ValueError):
            return False
        if sync:
            _writer.flush()
            return _write_file(path, payload)
        _writer.submit(path, payload)
        return True

    @staticmethod
    def flush_pending() -> None:
        _writer.flush()

    # ── 장비 ──
    @property
    def money(self) -> int:
        return self.data["money"]

    def equipped(self, kind: str) -> dict:
        if kind == "bait":
            return baits()[self.data["gear"]["bait"]]
        gid = self.data["gear"][kind]
        if self.owns_treasure(kind, gid):
            return self.treasure_gear(kind, gid)
        return find_gear(kind, gid)

    def owns(self, kind: str, item_id: str) -> bool:
        return item_id in self.data["owned"][kind] or self.owns_treasure(kind, item_id)

    # ── 상자 아이템 (Phase E) ──
    def owns_treasure(self, kind: str, item_id: str) -> bool:
        if item_id not in self.data["items"]["owned"]:
            return False
        from src.save.treasure import item_info
        return item_info(item_id)["kind"] == kind

    def top_continent(self) -> str:
        return "eldrasion" if "eldrasion" in self.data["unlocked_continents"] else "sharmion"

    def treasure_gear(self, kind: str, item_id: str) -> dict:
        """상자 장비의 실제 수치. 기본 = 대륙 상점 최고 티어 (전설은 지금 열린 가장 높은 대륙 기준으로 자동 상향,
        특별은 얻은 대륙 기준). 대가(-5%)는 그대로 유지. 상점 최고 티어를 넘지 않는다."""
        from src.save.treasure import item_info
        it = item_info(item_id)
        cont = self.top_continent() if it["grade"] == "legend" else \
            self.data["items"].get("origin", {}).get(item_id, "sharmion")
        top = TOP_TIER[cont]
        base = max((g for g in equipment()[kind] if g["tier"] <= top), key=lambda g: g["tier"])
        g = copy.deepcopy(base)
        g.pop("continent", None)
        g.pop("scales", None)
        g.update(id=item_id, name=it["name"], desc=it["desc"], price=0, treasure=True)
        if item_id == "dragon_scale_rod":
            lo, hi = g["green"]
            c, w = (lo + hi) / 2, (hi - lo) * 0.95
            g["green"] = [round(c - w / 2, 1), round(c + w / 2, 1)]
        elif item_id == "ancient_reel":
            g["speed"] = round(g["speed"] * 0.95, 3)
        return g

    def unlock_continent(self, cont: str) -> bool:
        """대륙 해금 (처음이면 True). 첫 낚시터도 함께 연다."""
        if cont in self.data["unlocked_continents"]:
            return False
        self.data["unlocked_continents"].append(cont)
        first = next(c["first_spot"] for c in load_json("continents.json")["continents"] if c["id"] == cont)
        if first not in self.data["unlocked_spots"]:
            self.data["unlocked_spots"].append(first)
        return True

    # ── 특수 찌 (엘드라시온) ──
    def float_tier(self) -> int:
        fid = self.data["float"].get("equipped")
        if not fid:
            return 0
        return next((f["tier"] for f in load_json("floats.json")["floats"] if f["id"] == fid), 0)

    def float_need(self, fish: dict, spot: dict) -> int:
        """이 물고기를 끝까지 잡는 데 필요한 찌 티어 (샤르미온 = 0)."""
        if spot.get("continent", "sharmion") != "eldrasion":
            return 0
        need = spot.get("float_req", 0) + (1 if fish["rarity"] in ("legend", "phantom") else 0)
        return min(5, need)

    def float_scales_needed(self) -> int:
        """아직 안 산 특수 찌들에 드는 전설 비늘 합계."""
        owned = self.data["float"]["owned"]
        return sum(f.get("scales", 0) for f in load_json("floats.json")["floats"] if f["id"] not in owned)

    def scale_warning(self, item: dict) -> int | None:
        """비늘이 드는 장비를 사면 남은 특수 찌를 살 비늘이 모자라지는지. 모자라지면 필요한 비늘 수."""
        cost = item.get("scales", 0)
        need = self.float_scales_needed()
        if cost and self.data["scales"] >= need and self.data["scales"] - cost < need:
            return need
        return None

    def buy_float(self, item: dict) -> str:
        fl = self.data["float"]
        if item["id"] in fl["owned"]:
            return "already"
        if "eldrasion" not in self.data["unlocked_continents"]:
            return "locked"
        if self.data["money"] < item["price"]:
            return "money"
        if self.data["scales"] < item.get("scales", 0):
            return "scales"
        self.data["money"] -= item["price"]
        self.data["scales"] -= item.get("scales", 0)
        fl["owned"].append(item["id"])
        fl["equipped"] = item["id"]
        self.data["flags"]["float_highlight"] = False
        return "ok"

    def record_seen(self, fish_id: str) -> None:
        """도감에 '목격'으로 등록 (잡은 것은 아님). 환상어는 기록하지 않는다 (33장)."""
        if not any(f["id"] == fish_id for f in all_fish()):
            return
        self.data["dex"].setdefault(fish_id, {"count": 0, "max_size": 0.0, "best_rank": "C", "seen": True})

    def charm_slots(self) -> int:
        return 2 if "eldrasion" in self.data["unlocked_continents"] else 1

    def charms(self) -> list:
        ch = self.data["items"].setdefault("charms", [None])
        n = self.charm_slots()
        while len(ch) < n:
            ch.append(None)
        return ch[:n]

    def charm_on(self, item_id: str) -> bool:
        return item_id in self.charms()

    def toggle_charm(self, item_id: str) -> str:
        """장착/해제. 칸이 꽉 찼으면 첫 칸을 바꾼다."""
        ch = self.charms()
        full = self.data["items"]["charms"]
        if item_id in ch:
            full[full.index(item_id)] = None
            return "off"
        for i, v in enumerate(ch):
            if v is None:
                full[i] = item_id
                return "on"
        full[0] = item_id
        return "on"

    def cosmetic_on(self, item_id: str) -> bool:
        return self.data["items"].get("cosmetic") == item_id

    def toggle_cosmetic(self, item_id: str) -> None:
        items = self.data["items"]
        items["cosmetic"] = None if items.get("cosmetic") == item_id else item_id

    def consumable_count(self, item_id: str) -> int:
        return self.data["items"]["consumables"].get(item_id, 0)

    def use_consumable(self, item_id: str) -> bool:
        cons = self.data["items"]["consumables"]
        if cons.get(item_id, 0) <= 0:
            return False
        cons[item_id] -= 1
        return True

    def lunch_active(self) -> bool:
        return self.data["playtime"] < self.data["buffs"].get("lunch_until", 0.0)

    def sale_price(self, item: dict, nth: int = 0) -> int:
        """판매가. 전설은 첫 포획 1마리 말고는 재판매 ×resell, 같은 종을 오늘 여러 번 팔면 감가 (nth = 이번 묶음에서 앞선 같은 종 수)."""
        k = 1.1 if self.lunch_active() else 1.0
        return int(round(item["price"] * k * self.legend_sale_mult(item, nth)))

    def legend_sale_mult(self, item: dict, nth: int = 0) -> float:
        fish = fish_by_id(item["id"])
        if fish["rarity"] != "legend":
            return 1.0
        cfg = legend_economy()
        k = 1.0 if item.get("first") else cfg["resell_mult"]
        decay = cfg["daily_decay"]
        return k * decay[min(len(decay) - 1, self.legend_sold_today(item["id"]) + nth)]

    def legend_sold_today(self, fid: str) -> int:
        ls = self.data["legend_sales"]
        return ls["counts"].get(fid, 0) if ls.get("day") == _today() else 0

    def sale_prices(self, items: list) -> list[int]:
        """여러 마리를 차례로 팔 때 각 판매가 (같은 전설이 여럿이면 뒤로 갈수록 감가)."""
        seen: dict = {}
        out = []
        for it in items:
            out.append(self.sale_price(it, seen.get(it["id"], 0)))
            seen[it["id"]] = seen.get(it["id"], 0) + 1
        return out

    def _note_sale(self, item: dict) -> None:
        if fish_by_id(item["id"])["rarity"] != "legend":
            return
        ls = self.data["legend_sales"]
        if ls.get("day") != _today():
            ls["day"], ls["counts"] = _today(), {}
        ls["counts"][item["id"]] = ls["counts"].get(item["id"], 0) + 1

    def fight_gear(self, period: str = "day") -> dict:
        """Fight에 넘길 장비 수치 (상자 아이템 효과 + 장착한 비늘석 합계 효과, DESIGN 46장 S4).
        장비 강화는 없어짐 — 비늘석은 칸에 붙어서 장비를 바꿔도 그대로 적용."""
        from src.save import scalestone as ss
        rod, reel, line, net = (self.equipped(k) for k in GEAR_KINDS)
        green = list(rod["green"])
        if rod["id"] == "moon_rod" and period in ("night", "day"):
            # 달빛 낚싯대: 밤 +10%, 낮 -5%
            k = 1.10 if period == "night" else 0.95
            c, w = (green[0] + green[1]) / 2, (green[1] - green[0]) * k
            green = [c - w / 2, c + w / 2]
        base = {"rod_green": green, "rod_tier": rod.get("tier", 1), "reel_speed": reel["speed"], "drag_steps": reel["drag_steps"],
                "drag_cushion": reel.get("drag_cushion", 0.0), "line_max": line["durability"],
                "net_window_sec": net["window"], "net_fail_distance": net["fail_distance"],
                "line_red_mult": 0.9 if self.charm_on("warm_gloves") else 1.0,
                "perfect_heal": 0.10 if rod["id"] == "dragon_scale_rod" else 0.0,
                "auto_drag": reel["id"] == "ancient_reel"}
        return ss.apply_fight(base, ss.effects(self))   # 비늘석 (칸 4개 합계, 상한 적용)

    def gear_tier(self, kind: str) -> int:
        """장착한 장비 티어 (전설 미끼처럼 티어 없는 미끼는 0)."""
        return self.equipped(kind).get("tier", 0)

    def bait_locked_reason(self, bait: dict) -> str | None:
        """판매 조건을 못 채웠으면 이유, 아니면 None."""
        if bait.get("price", 0) < 0:
            return "판매하지 않음"
        spot = bait.get("unlock_spot")
        if spot:
            # 일반~고급만 (희귀는 빠짐 — 전설 미끼가 너무 늦게 열리지 않게, DESIGN.md 25장)
            need = [f for f in all_fish() if f["spot"] == spot and f["rarity"] in ("common", "uncommon")]
            missing = [f for f in need if f["id"] not in self.data["dex"]]
            if missing:
                return f"이 낚시터 일반~고급 {len(need) - len(missing)}/{len(need)}종 포획 필요"
        return None

    def gear_locked_reason(self, item: dict) -> str | None:
        """대륙 잠금 (엘드라시온 장비)."""
        cont = item.get("continent")
        if cont and cont not in self.data["unlocked_continents"]:
            return "엘드라시온 대륙에서 판매"
        return None

    def buy(self, kind: str, item: dict) -> str:
        if self.owns(kind, item["id"]):
            return "already"
        if self.gear_locked_reason(item) or (kind == "bait" and self.bait_locked_reason(item)):
            return "locked"
        if self.data["money"] < item["price"]:
            return "money"
        if self.data["scales"] < item.get("scales", 0):
            return "scales"
        self.data["money"] -= item["price"]
        self.data["scales"] -= item.get("scales", 0)
        self.data["owned"][kind].append(item["id"])
        self.data["gear"][kind] = item["id"]
        return "ok"

    def equip(self, kind: str, item_id: str) -> None:
        if self.owns(kind, item_id):
            self.data["gear"][kind] = item_id

    # ── 포획 · 판매 ──
    def record_catch(self, result: dict) -> dict:
        """획득 기록. 돌려주는 값: 새로 등록 / 최대 크기 경신 / 힌트 해금 / S 금테 등."""
        fish = result["fish"]
        fid = fish["id"]
        self.data.setdefault("dialogue", {}).setdefault("flags", {})["lost_streak"] = 0
        if fish.get("rarity") == "phantom":
            return self._record_phantom(result)
        dex = self.data["dex"]
        entry = dex.get(fid)
        news = {"new": entry is None, "record": False, "hint": 0, "gold": False}
        if entry is None:
            entry = {"count": 0, "max_size": 0.0, "best_rank": "C"}
            dex[fid] = entry
        entry["count"] += 1
        if result["size"] > entry["max_size"]:
            news["record"] = not news["new"]
            entry["max_size"] = result["size"]
        if RANK_ORDER[result["rank"]] > RANK_ORDER[entry["best_rank"]] or entry["count"] == 1:
            if result["rank"] == "S" and entry.get("best_rank") != "S":
                news["gold"] = True
            entry["best_rank"] = result["rank"] if RANK_ORDER[result["rank"]] >= RANK_ORDER[entry["best_rank"]] \
                else entry["best_rank"]
        if entry["count"] in (3, 10):
            news["hint"] = entry["count"]
        self.data["keepnet"].append({"id": fid, "size": result["size"], "rank": result["rank"],
                                     "price": result["price"]})
        if news["record"]:
            self.data["keepnet"][-1]["record"] = True   # 상점: 신기록 배지
        if news["record"] or fish["rarity"] == "legend":
            self.data["keepnet"][-1]["lock"] = True     # 상점: 전설·크기 신기록은 자동 잠금 (일괄 판매에서 빠짐)
        if fish.get("limited"):   # 한정 물고기: 잡은 대륙 (분해 소재용 — 이벤트 물고기는 두 대륙 공통)
            self.data["keepnet"][-1]["cont"] = spot_continent(fish["spot"])
        if fish["rarity"] == "legend":
            # 전설: 첫 포획은 트로피 보상금 + 그 한 마리는 제값, 이후는 재판매가 (판매 감가는 sale_price)
            cfg = legend_economy()
            if news["new"]:
                self.data["keepnet"][-1]["first"] = True
                news["trophy"] = int(round(result["price"] * cfg["trophy_mult"]))
                self.data["money"] += news["trophy"]
                self.data["stats"]["earned"] += news["trophy"]
            else:
                news["resell"] = cfg["resell_mult"]
        # 비늘석 (46장): 일반 · 고급 0.8% / 희귀 3%, 전설 첫 포획 = 희귀 확정 — 표시는 파이팅 뒤 포획 카드 · 결과 화면
        from src.save import scalestone
        cont = spot_continent(fish["spot"]) if fish.get("spot") else "sharmion"
        if fish["rarity"] == "legend":
            stone = scalestone.grant_table(self, "legend_first", cont) if news["new"] else None
        else:
            stone = scalestone.roll_catch(self, fish, cont)
        if stone is not None:
            news["scalestone"] = stone
        st = self.data["stats"]
        st["catches"] += 1
        st["perfects"] += result.get("perfects", 0)
        if result["rank"] == "S":
            st["s_ranks"] += 1
            if spot_continent(fish["spot"]) == "eldrasion":
                st["s_ranks_eldra"] = st.get("s_ranks_eldra", 0) + 1
        return news

    def _record_phantom(self, result: dict) -> dict:
        """환상어: 일반 도감(dex)·도감 % 에 넣지 않고 환상 도감에만 (33장). 살림망·통계는 같게."""
        from src.fishing import phantom
        prev = dict(phantom.state(self)["caught"].get(result["fish"]["id"]) or {})   # 기록 전 최대 크기
        got = phantom.record(self, result)
        news = {"new": False, "record": False, "hint": 0, "gold": False, "phantom": True,
                "phantom_new": got["new"], "phantom_first_ever": got["first_ever"]}
        self.data["keepnet"].append({"id": result["fish"]["id"], "size": result["size"], "rank": result["rank"],
                                     "price": result["price"], "lock": True})   # 환상어는 자동 잠금
        if prev and result["size"] > prev.get("max_size", 0.0):
            self.data["keepnet"][-1]["record"] = True
        st = self.data["stats"]
        st["catches"] += 1
        st["perfects"] += result.get("perfects", 0)
        if result["rank"] == "S":
            st["s_ranks"] += 1
        if got["new"]:   # 환상 첫 포획 = 전설 비늘석 확정 (환상 비밀: 포획 연출 뒤 카드에만)
            from src.save import scalestone
            news["scalestone"] = scalestone.grant_table(self, "phantom_first", spot_continent(result["fish"].get("spot", "")))
        return news

    def release_last(self, item: dict) -> dict:
        """놓아주기 (DETAILS D, DT7): 방금 잡은 한 마리를 살림망에서 뺀다 (도감 · 숙련 · 업적은 이미 포획으로 기록).
        도감 포인트 +1 (실제 날짜 하루 최대 20). 돌려주는 값 {"point": 받은 포인트, "count": 누적, "title": 새 칭호 id | None}."""
        import datetime
        c = load_json("details/hands_catch.json")["release"]
        kn = self.data["keepnet"]
        for i in range(len(kn) - 1, -1, -1):
            if kn[i] is item:
                kn.pop(i)
                break
        det = self.data.setdefault("details", {})
        det["release_count"] = det.get("release_count", 0) + 1
        today = datetime.date.today().isoformat()
        day = det.setdefault("release_points_today", {"date": "", "n": 0})
        if day.get("date") != today:
            day["date"], day["n"] = today, 0
        got = 0
        if day["n"] < c["daily_max"]:
            got = c["points_per"]
            day["n"] += got
            det["release_points"] = det.get("release_points", 0) + got
        title = None
        if det["release_count"] >= c["title_at"]:
            cos = self.data.setdefault("cosmetics", {"titles": [], "float_skins": [], "rod_skins": []})
            if c["title_id"] not in cos.setdefault("titles", []):
                cos["titles"].append(c["title_id"])
                title = c["title_id"]
        return {"point": got, "count": det["release_count"], "title": title}

    def record_loss(self) -> None:
        self.data["stats"]["lost"] += 1
        fl = self.data.setdefault("dialogue", {}).setdefault("flags", {})
        fl["lost_streak"] = fl.get("lost_streak", 0) + 1   # 하루 아저씨: 계속 놓치면 한마디 (35-12)

    def sell(self, index: int) -> int:
        if not 0 <= index < len(self.data["keepnet"]):
            return 0
        item = self.data["keepnet"].pop(index)
        price = self.sale_price(item)
        self._note_sale(item)
        self.data["money"] += price
        self.data["stats"]["earned"] += price
        return price

    def disassemble_yield(self, index: int) -> dict | None:
        """분해하면 얻는 소재 {대륙: n, 'rare': n}. 전설은 분해 불가 (None)."""
        if not 0 <= index < len(self.data["keepnet"]):
            return None
        fish = fish_by_id(self.data["keepnet"][index]["id"])
        r = rules()
        n = r["disassemble"].get(fish["rarity"])
        if n is None:
            return None
        out = {self.data["keepnet"][index].get("cont") or spot_continent(fish["spot"]): n}
        if r["disassemble_rare_bonus"].get(fish["rarity"]):
            out["rare"] = r["disassemble_rare_bonus"][fish["rarity"]]
        if "cunning" in self.data["keepnet"][index].get("mut", []):
            from src.fishing.mutation import cfg as mcfg
            k = mcfg()["kinds"]["cunning"]["material_mult"]  # 교활 변이: 분해 소재 ×2
            out = {key: v * k for key, v in out.items()}
        from src.save import scalestone as ss
        mg = ss.frac(self, "material_gain")
        if mg > 0:   # 비늘석 소재 획득량 +% (대륙 소재만, 소수는 확률로 1개 — 기대값 그대로)
            import random as _r
            for key in list(out):
                if key != "rare":
                    v = out[key] * (1 + mg)
                    out[key] = int(v) + (1 if _r.random() < v - int(v) else 0)
        return out

    def disassemble(self, index: int) -> dict | None:
        got = self.disassemble_yield(index)
        if got is None:
            return None
        self.data["keepnet"].pop(index)
        mats = self.data["materials"]
        for k, v in got.items():
            mats[k] = mats.get(k, 0) + v
        return got

    def sell_all(self) -> int:
        total = sum(self.sale_prices(self.data["keepnet"]))
        for it in self.data["keepnet"]:
            self._note_sale(it)
        self.data["money"] += total
        self.data["stats"]["earned"] += total
        self.data["keepnet"].clear()
        return total

    # ── 도감 ──
    def dex_count(self) -> int:
        """도감 종 수 (해금 조건) — fish.json 물고기만 (계절·이벤트 한정은 빼서 진행이 막히지 않게)."""
        ids = {f["id"] for f in all_fish()}
        return sum(1 for fid, e in self.data["dex"].items() if e.get("count", 0) > 0 and fid in ids)

    def dex_entry(self, fish_id: str) -> dict | None:
        e = self.data["dex"].get(fish_id)
        return e if e and e.get("count", 0) > 0 else None  # '목격'만 한 물고기는 잡은 것이 아님

    def hint_status(self, fish: dict) -> tuple[bool, list[tuple[str, int, int]]]:
        """고급·희귀·전설의 등장 조건(시간·날씨)이 도감에 보이는지 + 진행 [(등급, 잡은 수, 필요 수)].
        고급 = 그 낚시터 일반 전부, 희귀 = 일반 전부 + 고급 1종 이상, 전설 = 일반·고급 전부 + 희귀 1종 이상.
        (그 등급이 그 낚시터에 없으면 그 조건은 빠진다 — 용문 폭포의 희귀처럼)"""
        order = ["common", "uncommon", "rare", "legend"]
        k = order.index(fish["rarity"])
        if k == 0:
            return False, []
        same = [f for f in all_fish() if f["spot"] == fish["spot"]]
        if k == 1:
            group = [f for f in same if f["rarity"] == "common"]
            rows = [("common", sum(self.caught(f["id"]) for f in group), len(group))] if group else []
            return all(h >= n for _, h, n in rows), rows
        rows = []
        for tier in order[:k - 1]:
            group = [f for f in same if f["rarity"] == tier]
            if group:
                rows.append((tier, sum(self.caught(f["id"]) for f in group), len(group)))
        prev = [f for f in same if f["rarity"] == order[k - 1]]
        if prev:
            rows.append((order[k - 1], min(1, sum(self.caught(f["id"]) for f in prev)), 1))
        return all(have >= need for _, have, need in rows), rows

    def caught(self, fish_id: str) -> bool:
        return self.dex_entry(fish_id) is not None

    def continent_dex(self, continent: str = "sharmion") -> tuple[int, int]:
        """(잡은 종 수, 전체 종 수) — 그 대륙 기준."""
        fish = [f for f in all_fish() if spot_continent(f["spot"]) == continent]
        return sum(1 for f in fish if self.caught(f["id"])), len(fish)

    def rare_total(self) -> int:
        """희귀 이상 누적 포획 마리 수."""
        rar = {f["id"]: f["rarity"] for f in all_fish()}
        return sum(e.get("count", 0) for fid, e in self.data["dex"].items() if rar.get(fid) in ("rare", "legend"))

    def spot_has_s(self, spot: str) -> bool:
        return any(self.dex_entry(f["id"]) and self.data["dex"][f["id"]].get("best_rank") == "S"
                   for f in all_fish() if f["spot"] == spot)
