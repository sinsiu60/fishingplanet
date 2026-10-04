"""STORY.md 의 대사 표를 그대로 읽어 온다 (data/story 를 만들 때 · tools/story_check.py 검증 때 같이 씀).

대사는 한 글자도 바꾸지 않는다: 표의 '대사' 칸 문자열 그대로 (표 구분자 '|' 와 양끝 공백만 뗌).
"""
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPEAKERS = {"하루 아저씨": "haru", "백 노인": "baek", "엘라": "ella", "오렌": "oren", "(자막)": None}


def story_text() -> str:
    return open(os.path.join(ROOT, "STORY.md"), encoding="utf-8").read()


def sections(md: str) -> dict:
    """'### <ID> 제목' 단위로 자른 본문 {ID: 본문}."""
    out = {}
    parts = re.split(r"^### ", md, flags=re.M)
    for p in parts[1:]:
        head = p.split("\n", 1)[0]
        m = re.match(r"([A-Z][A-Z0-9]*-\d+[A-Z]?)", head)
        if m:
            out[m.group(1)] = p
    # 환상 연결 장면은 '**PH-01**' 굵은 제목 아래 표
    for pid in ("PH-01", "PH-02"):
        m = re.search(r"\*\*%s\*\*\n(.*?)(?=\n\*\*PH-|\n---|\Z)" % pid, md, flags=re.S)
        if m:
            out[pid] = m.group(1)
    return out


def dialogue_tables(body: str) -> list[list[tuple]]:
    """본문 속 '| 순서 | 화자 | 표정 | 대사 |' 표들 → [[(화자 원문, 표정, 대사), …], …]."""
    tables, cur = [], None
    for line in body.split("\n"):
        if line.startswith("| 순서 | 화자 | 표정 | 대사 |"):
            cur = []
            tables.append(cur)
            continue
        if cur is None:
            continue
        if not line.startswith("|"):
            cur = None
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 4 or set(cells[0]) <= set("-"):
            continue
        cur.append((cells[1], cells[2], cells[3]))
    return tables


def unquote(s: str) -> str:
    """'**"…"**' 처럼 굵게·따옴표로 감싼 자막 → 안쪽 글자."""
    m = re.search(r'\*\*"(.*?)"\*\*', s)
    return m.group(1) if m else s


def code_block(body: str, after: str) -> str:
    """'after' 문구 뒤에 나오는 ``` 블록 내용 (편지 본문 등)."""
    i = body.index(after)
    m = re.search(r"```\n(.*?)\n```", body[i:], flags=re.S)
    return m.group(1)


def md_table(md: str, header: str) -> list[list[str]]:
    rows, on = [], False
    for line in md.split("\n"):
        if line.startswith(header):
            on = True
            continue
        if on:
            if not line.startswith("|"):
                break
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if set(cells[0]) <= set("-"):
                continue
            rows.append(cells)
    return rows
