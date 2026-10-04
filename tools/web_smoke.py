"""웹 버전 실행 확인 (CI): 브라우저(크로미움)를 아이폰 가로 화면처럼 열어 게임이 뜨는지 본다 (DESIGN.md 41).

  python tools/web_smoke.py http://localhost:8000/ <스크린샷 폴더>

- 아이폰(터치) 가로 844x390 + PC 브라우저 1280x720 두 번
- 몇 초마다 화면을 찍고, 첫 화면 '누르면 시작'을 탭, 제목 화면에서 화면 몇 곳을 눌러 본다
- 브라우저 콘솔 기록을 남기고, 파이썬 에러(Traceback)가 보이면 실패
"""
import os
import sys
import time

from playwright.sync_api import sync_playwright

IPHONE_UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 "
             "(KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1")


def run(p, url: str, out: str, name: str, touch: bool) -> list[str]:
    browser = p.chromium.launch(args=["--autoplay-policy=no-user-gesture-required"])
    if touch:
        ctx = browser.new_context(viewport={"width": 844, "height": 390}, device_scale_factor=2, is_mobile=True,
                                  has_touch=True, user_agent=IPHONE_UA)
    else:
        ctx = browser.new_context(viewport={"width": 1280, "height": 720})
    page = ctx.new_page()
    log: list[str] = []
    page.on("console", lambda m: log.append(f"[{m.type}] {m.text}"))
    page.on("pageerror", lambda e: log.append(f"[pageerror] {e}"))
    page.goto(url)
    vw, vh = page.viewport_size["width"], page.viewport_size["height"]

    def tap(fx: float, fy: float) -> None:
        x, y = int(vw * fx), int(vh * fy)
        if touch:
            page.touchscreen.tap(x, y)
        else:
            page.mouse.click(x, y)

    def shot(tag: str) -> None:
        page.screenshot(path=os.path.join(out, f"{name}-{tag}.png"))

    t0 = time.time()
    started = False
    n = 0
    while time.time() - t0 < 150:
        time.sleep(5)
        n += 1
        shot(f"{n:02d}")
        if any("Waiting for media user engagement" in s for s in log) and not started:
            tap(0.5, 0.5)   # '화면을 누르면 시작해요'
            started = True
        if started and n in (14, 17, 20):
            tap(0.5, 0.62)   # 제목 화면: 가운데 아래 (새 게임·이어하기 쪽)
        if any("Traceback" in s for s in log):
            time.sleep(2)
            shot("error")
            break
    shot("last")
    with open(os.path.join(out, f"{name}-console.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(log))
    browser.close()
    return log


def main() -> int:
    url, out = sys.argv[1], sys.argv[2]
    os.makedirs(out, exist_ok=True)
    bad = 0
    with sync_playwright() as p:
        for name, touch in (("iphone", True), ("pc", False)):
            log = run(p, url, out, name, touch)
            err = [s for s in log if "Traceback" in s or "Error" in s and "favicon" not in s]
            print(f"== {name}: 콘솔 {len(log)}줄, 에러 {len(err)}줄")
            for s in log[-60:]:
                print("  ", s[:300])
            if any("Traceback" in s for s in log):
                bad = 1
    return bad


if __name__ == "__main__":
    sys.exit(main())
