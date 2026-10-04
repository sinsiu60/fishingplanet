"""웹 버전(아이폰·아이패드·PC 브라우저) 빌드 준비·마무리 (DESIGN.md 41).

  python tools/web_build.py stage  <폴더>   게임 파일만 모은 폴더 (pygbag 이 이 폴더를 통째로 묶는다)
  python tools/web_build.py finish <build/web 폴더>
      아이콘(favicon · 홈 화면 아이콘 192) 넣고 index.html 손보기:
      한국어 제목·안내, 홈 화면에 추가하면 주소창 없이 전체 화면, 게임 화면비 그대로 꽉 채우기(픽셀 그대로),
      세로로 들면 '가로로 돌려 주세요'
웹엔 전설·환상 전용 곡(assets/music_generated/boss, 전설별 전설의 노래)을 넣지 않는다 — 대신 예전 보스 테마·대륙판 전설의 노래.
"""
import os
import re
import shutil
import sys

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

KEEP = ["main.py", "src", "data", "assets"]

HEAD = """
<meta name="apple-mobile-web-app-title" content="미니 피싱">
<meta name="apple-mobile-web-app-status-bar-style" content="black">
<meta name="theme-color" content="#000000">
<link rel="apple-touch-icon" href="icon192.png">
<link rel="manifest" href="manifest.json">
<style>
  html, body { background: #000 !important; overflow: hidden; touch-action: none;
               -webkit-user-select: none; user-select: none; -webkit-touch-callout: none; }
  /* 게임 화면비(--ar, 게임이 시작할 때 정함) 그대로 화면 가운데 꽉 차게, 픽셀은 흐리지 않게 */
  canvas#canvas { width: min(100vw, calc(100vh * var(--ar, 1.7778))) !important;
                  height: min(100vh, calc(100vw / var(--ar, 1.7778))) !important;
                  margin: auto !important; inset: 0 !important; position: absolute !important;
                  image-rendering: pixelated; image-rendering: crisp-edges; }
  #infobox { background: #10203a !important; color: #ffe496 !important; border-radius: 10px;
             font-family: sans-serif; font-size: 18px; }
  #mf-rotate { display: none; position: fixed; inset: 0; z-index: 1000000; background: #0c1426;
               color: #ffe496; font: bold 22px sans-serif; align-items: center; justify-content: center;
               text-align: center; line-height: 1.6; }
  @media (orientation: portrait) and (pointer: coarse) { #mf-rotate { display: flex; } }
</style>
"""
BODY = '<div id="mf-rotate">📱↻<br>휴대폰을 가로로 돌려 주세요</div>\n'
MANIFEST = """{
  "name": "미니 피싱",
  "short_name": "미니 피싱",
  "display": "fullscreen",
  "orientation": "landscape",
  "background_color": "#000000",
  "theme_color": "#000000",
  "start_url": "./",
  "icons": [{"src": "icon192.png", "sizes": "192x192", "type": "image/png"}]
}
"""


def stage(out: str) -> None:
    if os.path.exists(out):
        shutil.rmtree(out)
    os.makedirs(out)
    for name in KEEP:
        src = os.path.join(ROOT, name)
        if os.path.isdir(src):
            # 전설·환상 전용 곡(약 160MB)은 웹에선 뺀다 — 브라우저(특히 아이폰 사파리) 메모리·첫 로딩. 없으면 예전 보스 테마 (DESIGN.md 43)
            shutil.copytree(src, os.path.join(out, name), ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "boss", "legend_catch_*_L[0-9][0-9].ogg"))
        else:
            shutil.copy2(src, out)
    print("모은 파일:", sum(len(f) for _, _, f in os.walk(out)))


def finish(web: str) -> None:
    import pygame
    from src.render.icon import icon_surface
    pygame.init()
    pygame.image.save(icon_surface(192), os.path.join(web, "icon192.png"))
    pygame.image.save(icon_surface(32), os.path.join(web, "favicon.png"))
    with open(os.path.join(web, "manifest.json"), "w", encoding="utf-8") as f:
        f.write(MANIFEST)
    p = os.path.join(web, "index.html")
    html = open(p, encoding="utf-8").read()
    html = html.replace("Ready to start ! Please click/touch page", "화면을 누르면 시작해요")
    html = html.replace("Loading, please wait ...", "불러오는 중이에요…")
    html = html.replace('<html lang="en-us">', '<html lang="ko">', 1)
    html = re.sub(r"<title>.*?</title>", "<title>미니 피싱</title>", html, count=1, flags=re.S)
    html = html.replace("</head>", HEAD + "</head>", 1)
    html = re.sub(r"(<body[^>]*>)", lambda m: m.group(1) + "\n" + BODY, html, count=1)
    assert "mf-rotate" in html and "apple-touch-icon" in html, "index.html 구조가 달라서 못 고침"
    open(p, "w", encoding="utf-8").write(html)
    print("index.html 손봄:", p)


if __name__ == "__main__":
    {"stage": stage, "finish": finish}[sys.argv[1]](sys.argv[2])
