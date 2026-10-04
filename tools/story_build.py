"""STORY.md → data/story/*.json (대사·자막·일지·휴대폰·목표·편지 원문 그대로). 다시 만들려면: python tools/story_build.py
장면 조건·장소·결과는 DESIGN.md 36-0 표 (게임 신호) 기준으로 여기서 붙인다 — 문장은 전부 STORY.md 에서 읽는다."""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import story_extract as X  # noqa: E402

OUT = os.path.join(X.ROOT, "data", "story")


def lines_of(table) -> list:
    out = []
    for who, expr, txt in table:
        if who.startswith("**이름 입력"):
            out.append({"do": "name"})
        elif who.startswith("**클로즈업"):
            out.append({"do": "closeup"})
        elif who.startswith("**편지"):
            out.append({"do": "letter", "id": "letter"})
        else:
            out.append([X.SPEAKERS[who], expr or None, txt])
    return out


def main() -> None:
    md = X.story_text()
    S = X.sections(md)
    subs = {}
    for sid in ("P-01", "P-02", "P-03", "P-04", "C3-02", "C5-04", "C5-05", "E-01", "C4-01"):
        subs[sid] = re.findall(r'(?:자막|말풍선\(백 노인[^)]*\):)\s*\*\*"(.*?)"\*\*', S[sid])
    T = {sid: X.dialogue_tables(S[sid]) for sid in S}
    scenes = {
        "_설명": "스토리 장면 (DESIGN.md 36, STORY.md 원문). lines = [화자(haru/baek/ella/oren, null=자막), 표정, 대사] 또는 {do: name|closeup|letter}. "
                 "place = 재생 장소 (interior:<npc> = 그 NPC 건물에 들어갈 때 / cutscene). results = journal·flags·items·phone.",
        "P-05": {"act": 0, "place": "interior:haru", "menu": False, "lines": lines_of(T["P-05"][0]), "results": {"journal": "J01"}},
        "NAME": {"act": 0, "place": "interior:haru", "menu": True, "replay": False,
                 "lines": [["haru", "happy", "그러고 보니 이름을 안 물었네!"], {"do": "name"}, ["haru", "happy", "{player}! 좋은 이름이네."]]},
        "C1-04": {"act": 1, "place": "interior:baek", "lines": lines_of(T["C1-04"][0])},
        "C1-06": {"act": 1, "place": "interior:baek", "lines": lines_of(T["C1-06"][0]),
                  "results": {"journal": "J04", "flags": {"grandpa_named": True}}},
        "C2-02": {"act": 2, "place": "interior:haru", "lines": lines_of(T["C2-02"][0])},
        "C2-03": {"act": 2, "place": "interior:baek", "lines": lines_of(T["C2-03"][0])},
        "C2-05": {"act": 2, "place": "interior:baek", "lines": lines_of(T["C2-05"][0])},
        "C3-02": {"act": 3, "place": "cutscene", "subs": subs["C3-02"], "results": {"journal": "J08"}},
        "C3-03": {"act": 3, "place": "interior:baek", "lines": lines_of(T["C3-03"][0])},
        "C3-04": {"act": 3, "place": "interior:baek", "menu": False, "lines": lines_of(T["C3-04"][0]), "results": {"journal": "J09"}},
        "C4-01": {"act": 4, "place": "village:eldrasion", "subs": subs["C4-01"], "results": {"journal": "J10", "phone": "M6"}},
        "C4-02A": {"act": 4, "place": "interior:ella", "lines": lines_of(T["C4-02"][0])},
        "C4-02B": {"act": 4, "place": "interior:ella", "lines": lines_of(T["C4-02"][1])},
        "C4-03": {"act": 4, "place": "interior:oren", "lines": lines_of(T["C4-03"][0])},
        "C4-04": {"act": 4, "place": "interior:ella", "lines": lines_of(T["C4-04"][0])},
        "C4-05": {"act": 4, "place": "interior:ella", "lines": lines_of(T["C4-05"][0]),
                  "results": {"journal": "J11", "items": {"haegang_bobber_skin": True}}},
        "C5-03": {"act": 5, "place": "interior:oren", "lines": lines_of(T["C5-03"][0])},
        "C5-04": {"act": 5, "place": "cutscene", "subs": subs["C5-04"], "results": {"journal": "J12", "items": {"grandpa_last_page": True}}},
        "C5-05": {"act": 5, "place": "cutscene", "subs": subs["C5-05"]},
        "E-01": {"act": 6, "place": "cutscene", "subs": subs["E-01"], "results": {"journal": "J14"}},
        "PH-01": {"act": None, "place": "interior:baek", "lines": lines_of(T["PH-01"][0]), "results": {"journal": "J15"}},
        "PH-02": {"act": None, "place": "interior:baek", "lines": lines_of(T["PH-02"][0]), "results": {"journal": "J16"}},
    }
    for sid in ("P-01", "P-02", "P-03", "P-04"):
        scenes[sid] = {"act": 0, "place": "cutscene", "subs": subs[sid]}
    # 프롤로그 컷신 원문 (쪽지 3줄, 모니터 알림 3개, 시계)
    p3 = re.findall(r'\*\*"(.*?)"\*\*', S["P-03"])
    scenes["P-03"]["note"] = [x for x in p3 if x not in subs["P-03"]]
    p1 = re.findall(r'\*\*"(.*?)"\*\*', S["P-01"])
    scenes["P-01"]["alerts"] = [x for x in p1 if x.startswith("[업무]")]
    scenes["P-01"]["clock"] = next(x for x in p1 if ":" in x and not x.startswith("["))
    p4 = re.findall(r'\*\*"(.*?)"\*\*', S["P-04"])
    scenes["P-04"]["envelope"] = next(x for x in p4 if x not in subs["P-04"])
    c55 = re.findall(r'\*\*\[ (.*?) \]\*\*', S["C5-05"])
    scenes["C5-05"]["choices"] = list(dict.fromkeys(c55))[:2]
    e1 = re.findall(r'\*\*"(.*?)"\*\*', S["E-01"])
    scenes["E-01"]["all_quoted"] = e1
    c42 = re.findall(r'\*\*"(.*?)"\*\*', S["C3-02"])
    scenes["C3-02"]["carved"] = [x for x in c42 if x not in subs["C3-02"]]
    for sid in list(scenes):   # 추억 목록 제목 = STORY.md 장면 제목 그대로 ('### P-01 사무실 (6초)' → '사무실')
        key = {"C4-02A": "C4-02", "C4-02B": "C4-02"}.get(sid, sid)
        if key in S and isinstance(scenes[sid], dict):
            head = S[key].split("\n", 1)[0]
            title = re.sub(r"^\S+\s*", "", head)
            title = re.sub(r"\s*\(\d+초\)$", "", title)
            scenes[sid]["title"] = title + {"C4-02A": " (A)", "C4-02B": " (B)"}.get(sid, "")
    scenes["NAME"]["title"] = "이름"
    for pid, t in (("PH-01", "환상 연결 1"), ("PH-02", "환상 연결 2")):
        scenes[pid]["title"] = t
    os.makedirs(OUT, exist_ok=True)
    jr = X.md_table(md, "| ID | 조건 | 일지 문장 |")
    journal = {"_설명": "낚시 일지 (STORY.md 원문).", "entries": {r[0]: {"cond": r[1], "text": r[2]} for r in jr}}
    ph = X.md_table(md, "| ID | 발생 조건 | 보낸 사람 | 메시지 | 이어지는 자막 |")
    phone = {"_설명": "휴대폰 알림 (STORY.md 원문). after = 이어지는 자막 (없음 → null).",
             "messages": {r[0]: {"cond": r[1], "from": None if r[2] == "없음" else r[2], "text": r[3],
                                 "after": None if r[4] in ("없음", "E-01 참고") else r[4]} for r in ph}}
    phone["messages"]["M6"]["text"] = X.unquote(phone["messages"]["M6"]["text"])
    gl = X.md_table(md, "| 상태 | 표시 문구 |")
    goals = {"_설명": "다음 목표 (STORY.md 원문). state = 구간 이름 (src/story/story.py goal() 이 진행 상태로 고름).",
             "goals": [{"state": r[0], "text": r[1]} for r in gl]}
    letters = {"_설명": "편지·종이 (STORY.md 원문, 줄바꿈 그대로).",
               "letter": X.code_block(md, "**편지 본문**"), "last_page": X.code_block(md, "**마지막 장 본문**")}
    chapters = {"_설명": "막 (STORY.md 3).", "acts": [{"act": int(r[0]), "name": r[1], "start": r[2], "end": r[3]}
                                                  for r in X.md_table(md, "| 막 | 이름 | 시작 조건 | 끝 조건 |")]}
    for name, obj in (("scenes", scenes), ("journal", journal), ("phone", phone), ("goals", goals), ("letters", letters),
                      ("chapters", chapters)):
        with open(os.path.join(OUT, f"{name}.json"), "w", encoding="utf-8") as fp:
            json.dump(obj, fp, ensure_ascii=False, indent=1)
            fp.write("\n")
    print("ok", len(scenes) - 1, "scenes")


if __name__ == "__main__":
    main()
