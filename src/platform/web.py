"""웹(브라우저) 버전 도우미 — pygbag (WebAssembly) 로 돌 때만 쓴다 (DESIGN.md 41).

- 화면: 브라우저 창의 가로 화면비로 캔버스를 잡고, 페이지 CSS 가 그 비율 그대로 화면에 꽉 차게 늘린다 (픽셀 그대로).
- 세이브: 브라우저 안 파일은 새로고침하면 사라진다 → 세이브 폴더 파일을 localStorage 에 그대로 옮겨 두고, 시작 때 되살린다.
"""
import base64
from pathlib import Path

KEY = "minifishing:"        # localStorage 키 앞머리 (뒤는 세이브 폴더 안 상대 경로)
SKIP = (".log", ".tmp")     # 시작 기록·임시 파일은 안 옮김
_last: dict[str, str] = {}  # 마지막으로 옮긴 내용 (같으면 다시 안 씀)
SCALE = 2                   # 창 = 캔버스 x2 (브라우저가 화면 크기만큼 다시 늘림)


def _window():
    import platform as _pf   # pygbag 이 window 를 붙여 준 모듈
    return _pf.window


def window_size() -> tuple[int, int]:
    """창(프레임버퍼) 크기. 세로로 들고 시작해도 가로 비율로 (게임은 가로 전용)."""
    from src.render.screen import canvas_size_for
    try:
        w = _window()
        a, b = int(w.innerWidth), int(w.innerHeight)
    except Exception:
        a, b = 1280, 720
    a, b = max(a, b, 1), max(1, min(a, b))
    cw, ch = canvas_size_for(a, b)
    try:   # 페이지 CSS 가 쓰는 화면비 (index.html 의 #canvas 크기 규칙)
        _window().document.documentElement.style.setProperty("--ar", str(cw / ch))
    except Exception:
        pass
    return cw * SCALE, ch * SCALE


def _encode(data: bytes) -> str:
    try:
        return "t" + data.decode("utf-8")
    except UnicodeDecodeError:
        return "b" + base64.b64encode(data).decode("ascii")


def _decode(s: str) -> bytes:
    return s[1:].encode("utf-8") if s[:1] == "t" else base64.b64decode(s[1:])


def restore(folder: Path) -> int:
    """시작 때: localStorage → 세이브 폴더. 되살린 파일 수."""
    n = 0
    try:
        ls = _window().localStorage
        for i in range(int(ls.length)):
            k = str(ls.key(i))
            if not k.startswith(KEY):
                continue
            rel = k[len(KEY):]
            if ".." in rel or rel.startswith("/"):
                continue
            v = str(ls.getItem(k))
            p = folder / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(_decode(v))
            _last[rel] = v
            n += 1
    except Exception as e:
        print("web.restore:", e)
    return n


def sync(folder: Path | None = None) -> None:
    """세이브 폴더 → localStorage (바뀐 파일만). 저장할 때마다 부른다."""
    try:
        if folder is None:
            from src.core.paths import save_dir
            folder = save_dir()
        ls = _window().localStorage
        seen = set()
        for p in folder.rglob("*"):
            if not p.is_file() or p.suffix in SKIP:
                continue
            rel = p.relative_to(folder).as_posix()
            seen.add(rel)
            v = _encode(p.read_bytes())
            if _last.get(rel) != v:
                ls.setItem(KEY + rel, v)
                _last[rel] = v
        for rel in [r for r in _last if r not in seen]:   # 지운 파일 (슬롯 삭제)
            ls.removeItem(KEY + rel)
            del _last[rel]
    except Exception as e:
        print("web.sync:", e)
