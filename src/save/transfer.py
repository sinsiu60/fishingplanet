"""세이브 옮기기 (MOBILE.md 5번): PC ↔ 모바일.

내보내기 : 슬롯 파일 → 'FPSAVE1:<crc>:<압축+base64>' 한 줄 코드.
           클립보드에 복사 + 파일로 저장 (PC: 내 문서/FishingPlanet/export, 안드로이드: Android/data/<패키지>/files)
           + 안드로이드는 공유 창(카톡·메일로 나에게 보내기)
가져오기 : 클립보드 → 없으면 위 폴더의 import.txt(또는 가장 최근 .txt)에서 코드를 찾는다.
           덮어쓰기 전 지금 슬롯을 backups/slotN_날짜.json 으로 자동 백업. 옛 버전 세이브도 불러올 때 마이그레이션된다.
"""
import base64
import json
import os
import shutil
import time
import zlib
from pathlib import Path

from src.core.paths import save_dir

PREFIX = "FPSAVE1:"


def _slot_path(slot: int) -> Path:
    return save_dir() / f"slot{slot}.json"


def export_code(slot: int) -> str | None:
    try:
        data = json.loads(_slot_path(slot).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    raw = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    crc = zlib.crc32(raw) & 0xFFFFFFFF
    return f"{PREFIX}{crc:08x}:" + base64.urlsafe_b64encode(zlib.compress(raw, 9)).decode("ascii")


def decode(code: str) -> dict:
    """코드 → 세이브 dict. 잘못되면 ValueError(이유)."""
    s = "".join(code.split())  # 메신저가 줄을 바꿔 붙여도 괜찮게
    i = s.find(PREFIX)
    if i < 0:
        raise ValueError("세이브 코드가 아니에요")
    try:
        crc_hex, payload = s[i + len(PREFIX):].split(":", 1)
        raw = zlib.decompress(base64.urlsafe_b64decode(payload.encode("ascii")))
    except Exception:
        raise ValueError("코드가 잘렸거나 손상됐어요 (전체를 복사했는지 확인)")
    if f"{zlib.crc32(raw) & 0xFFFFFFFF:08x}" != crc_hex:
        raise ValueError("코드가 손상됐어요 (검사값 불일치)")
    data = json.loads(raw.decode("utf-8"))
    if not isinstance(data, dict) or "dex" not in data or "money" not in data:
        raise ValueError("세이브 내용이 올바르지 않아요")
    return data


def export_dir() -> Path:
    from src.platform.detect import IS_ANDROID
    if IS_ANDROID:
        from src.platform import android
        d = android.shared_dir()
        if d is not None:
            return d
    return save_dir() / "export"


def write_export_file(slot: int, code: str) -> Path | None:
    try:
        d = export_dir()
        d.mkdir(parents=True, exist_ok=True)
        path = d / f"fishing_save_slot{slot}.txt"
        path.write_text(code + "\n", encoding="utf-8")
        return path
    except OSError:
        return None


def clipboard_put(text: str) -> bool:
    try:
        import pygame
        if hasattr(pygame.scrap, "put_text"):  # pygame-ce
            pygame.scrap.put_text(text)
            return True
        pygame.scrap.init()
        pygame.scrap.put(pygame.SCRAP_TEXT, text.encode("utf-8"))
        return True
    except Exception:
        return False


def clipboard_get() -> str:
    try:
        import pygame
        if hasattr(pygame.scrap, "get_text"):
            return pygame.scrap.get_text() or ""
        pygame.scrap.init()
        raw = pygame.scrap.get(pygame.SCRAP_TEXT)
        return raw.decode("utf-8", "ignore").rstrip("\0") if raw else ""
    except Exception:
        return ""


def find_import_code() -> tuple[str | None, str]:
    """(코드, 어디서 찾았는지)."""
    clip = clipboard_get()
    if PREFIX in clip:
        return clip, "클립보드"
    d = export_dir()
    cands = []
    for name in ("import.txt",):
        if (d / name).exists():
            cands.append(d / name)
    if d.exists():
        cands += sorted(d.glob("*.txt"), key=lambda p: p.stat().st_mtime, reverse=True)
    for p in cands:
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if PREFIX in text:
            return text, f"파일 {p.name}"
    return None, ""


def backup_slot(slot: int) -> Path | None:
    src = _slot_path(slot)
    if not src.exists():
        return None
    d = save_dir() / "backups"
    try:
        d.mkdir(parents=True, exist_ok=True)
        dst = d / f"slot{slot}_{time.strftime('%Y%m%d_%H%M%S')}.json"
        shutil.copyfile(src, dst)
        return dst
    except OSError:
        return None


def import_to_slot(slot: int, data: dict) -> Path | None:
    """백업 후 덮어쓰기. 돌려주는 값 = 백업 파일 (원래 비어 있던 슬롯이면 None)."""
    bak = backup_slot(slot)
    path = _slot_path(slot)
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)
    return bak
