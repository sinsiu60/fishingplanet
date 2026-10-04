"""
시우 공방 로고 (픽셀아트)
- 지붕 = ㅅ, 둥근 창 = ㅇ  → '시우'의 첫소리 ㅅㅇ을 작은 공방 모양에 숨김
- 굴뚝 연기 = 무언가를 만들고 있는 공방
"""
import os, sys
from PIL import Image, ImageDraw, ImageFont

FONT_DIR = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] != "splash" else "/home/claude/galmuri/package/dist"
OUT = os.path.dirname(os.path.abspath(__file__))
c = lambda h, a=255: tuple(int(h.lstrip('#')[i:i+2], 16) for i in (0, 2, 4)) + (a,)

INK = c("#1C1626")
ROOF, ROOF_L, ROOF_D = c("#C8573E"), c("#E07A5A"), c("#8E3A2A")
WALL, WALL_D = c("#F2EBD8"), c("#D6C8A8")
WOOD, WOOD_D = c("#8A5A3A"), c("#5A3A22")
LIGHT, LIGHT_H, LIGHT_D = c("#FFDC78"), c("#FFF4C8"), c("#E8A840")
SMOKE = c("#C8CCD8")
NAVY = c("#16203A")


def outline(im, col=INK):
    px = im.load(); w, h = im.size
    out = im.copy(); op = out.load()
    for y in range(h):
        for x in range(w):
            if px[x, y][3]:
                continue
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = x + dx, y + dy
                if 0 <= nx < w and 0 <= ny < h and px[nx, ny][3]:
                    op[x, y] = col; break
    return out


def mark():
    im = Image.new("RGBA", (32, 32), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    # 굴뚝 + 연기
    d.rectangle([21, 6, 23, 12], fill=WOOD); d.line([(21, 6), (21, 12)], fill=WOOD_D)
    d.point([(23, 3), (24, 2), (22, 1), (25, 4)], fill=SMOKE)
    # 박공(지붕 아래 삼각형) + 벽
    d.polygon([(16, 7), (7, 16), (25, 16)], fill=WALL)
    d.polygon([(16, 7), (21, 12), (21, 16), (25, 16)], fill=WALL_D)
    d.point([(16, 11), (15, 12), (16, 12), (17, 12)], fill=WOOD)
    d.rectangle([8, 15, 24, 27], fill=WALL)
    d.rectangle([21, 15, 24, 27], fill=WALL_D)
    # 바닥 받침
    d.rectangle([6, 27, 26, 28], fill=WOOD); d.line([(6, 28), (26, 28)], fill=WOOD_D)
    # 지붕 = ㅅ (왼쪽 획 위에서 왼쪽 아래로, 오른쪽 획은 중간에서 오른쪽 아래로)
    for k, col in ((0, ROOF_L), (1, ROOF), (2, ROOF), (3, ROOF_D)):
        d.line([(16, 4 + k), (4, 16 + k)], fill=col)
    for k, col in ((0, ROOF_L), (1, ROOF), (2, ROOF), (3, ROOF_D)):
        d.line([(16, 4 + k), (28, 16 + k)], fill=col)
    # 둥근 창 = ㅇ (따뜻한 불빛)
    d.ellipse([11, 16, 21, 26], fill=WOOD)
    d.ellipse([12, 17, 20, 25], fill=LIGHT_D)
    d.ellipse([12, 17, 19, 24], fill=LIGHT)
    d.point([(14, 19), (15, 19), (14, 20)], fill=LIGHT_H)
    # 창살
    d.line([(16, 18), (16, 24)], fill=WOOD)
    d.line([(13, 21), (19, 21)], fill=WOOD)
    return outline(im)


def save_scaled(im, name, scale):
    im.resize((im.width * scale, im.height * scale), Image.NEAREST).save(os.path.join(OUT, name))


def lockup(mk, bg=None, fg=c("#F2EBD8"), sub=c("#8C94AA")):
    f14 = ImageFont.truetype(os.path.join(FONT_DIR, "Galmuri14.ttf"), 15)
    f7 = ImageFont.truetype(os.path.join(FONT_DIR, "Galmuri7.ttf"), 8)
    W, H = 112, 36
    im = Image.new("RGBA", (W, H), bg if bg else (0, 0, 0, 0)); d = ImageDraw.Draw(im); d.fontmode = "1"
    im.alpha_composite(mk, (2, 2))
    d.text((39, 6), "시우 공방", font=f14, fill=fg)
    d.text((40, 24), "SIU GONGBANG", font=f7, fill=sub)
    return im


if __name__ == "__main__" and (len(sys.argv) < 2 or sys.argv[1] != "splash"):
    mk = mark()
    mk.save(os.path.join(OUT, "siu_mark_32.png"))
    for s in (4, 8, 16):
        save_scaled(mk, f"siu_mark_{32*s}.png", s)
    # 앱·프로필용 정사각 (남색 배경)
    sq = Image.new("RGBA", (40, 40), NAVY); sq.alpha_composite(mk, (4, 4))
    save_scaled(sq, "siu_icon_square_640.png", 16)
    # 로고 + 글자
    lk = lockup(mk)
    save_scaled(lk, "siu_logo_horizontal.png", 6)
    lk_bg = lockup(mk, bg=NAVY)
    save_scaled(lk_bg, "siu_logo_horizontal_navy.png", 6)
    # 시작 화면 (게임 해상도 480x270, 세로 배치)
    sp = Image.new("RGBA", (480, 270), c("#0E1220")); d = ImageDraw.Draw(sp); d.fontmode = "1"
    big = mk.resize((64, 64), Image.NEAREST)
    sp.alpha_composite(big, (240 - 32, 82))
    f14 = ImageFont.truetype(os.path.join(FONT_DIR, "Galmuri14.ttf"), 15)
    f7 = ImageFont.truetype(os.path.join(FONT_DIR, "Galmuri7.ttf"), 8)
    d.text((240, 156), "시우 공방", font=f14, fill=c("#F2EBD8"), anchor="ma")
    d.text((240, 176), "SIU GONGBANG", font=f7, fill=c("#6E7691"), anchor="ma")
    save_scaled(sp, "siu_splash_1440x810.png", 3)
    print("ok")


# ── 게임 시작 화면용 (SPLASH.md) ──
#   python tools/art/make_logo.py splash <갈무리 dist 폴더>
#   assets/branding/ 에: 불 꺼진 창 로고, 연기 뺀 로고 + 연기 3프레임(위로 1px씩), 글자 띠(480x60, 화면 y=150 부터)
DIM = c("#5A3A22")
TEXT_Y = 150


def _smoke_pixels(mk):
    """원본 로고의 연기 픽셀: 연기색 + 연기에만 붙은 테두리."""
    px = mk.load(); w, h = mk.size
    smoke = {(x, y) for y in range(h) for x in range(w) if px[x, y] == SMOKE}
    out = set(smoke)
    for y in range(h):
        for x in range(w):
            if px[x, y] != INK:
                continue
            nb = [(x + dx, y + dy) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
                  if 0 <= x + dx < w and 0 <= y + dy < h and px[x + dx, y + dy][3] and px[x + dx, y + dy] != INK]
            if nb and all(p in smoke for p in nb):
                out.add((x, y))
    return out


def splash(font_dir, dest):
    os.makedirs(dest, exist_ok=True)
    mk = Image.open(os.path.join(dest, "siu_mark_32.png")).convert("RGBA")
    # 불 꺼진 창: 창의 노란 불빛(밝은·보통·어두운) → #5A3A22
    dark = mk.copy(); dp = dark.load()
    for y in range(32):
        for x in range(32):
            if dp[x, y] in (LIGHT, LIGHT_H, LIGHT_D):
                dp[x, y] = DIM
    dark.save(os.path.join(dest, "siu_mark_32_dark.png"))
    # 연기 빼고 / 연기 3프레임 (0·1·2px 위로)
    sp = _smoke_pixels(mk); src = mk.load()
    base = mk.copy(); bp = base.load()
    for p in sp:
        bp[p] = (0, 0, 0, 0)
    base.save(os.path.join(dest, "siu_mark_32_base.png"))
    dbase = dark.copy(); dbp = dbase.load()
    for p in sp:
        dbp[p] = (0, 0, 0, 0)
    dbase.save(os.path.join(dest, "siu_mark_32_dark_base.png"))
    for k in range(3):
        fr = Image.new("RGBA", (32, 32), (0, 0, 0, 0)); fp = fr.load()
        for (x, y) in sp:
            if y - k >= 0:
                fp[x, y - k] = src[x, y]
        fr.save(os.path.join(dest, f"siu_smoke_{k}.png"))
    # 글자 띠 (make_logo 의 시작 화면 목업과 같은 자리·색)
    band = Image.new("RGBA", (480, 60), (0, 0, 0, 0)); d = ImageDraw.Draw(band); d.fontmode = "1"
    f14 = ImageFont.truetype(os.path.join(font_dir, "Galmuri14.ttf"), 15)
    f7 = ImageFont.truetype(os.path.join(font_dir, "Galmuri7.ttf"), 8)
    d.text((240, 156 - TEXT_Y), "시우 공방", font=f14, fill=c("#F2EBD8"), anchor="ma")
    d.text((240, 176 - TEXT_Y), "SIU GONGBANG", font=f7, fill=c("#6E7691"), anchor="ma")
    band.save(os.path.join(dest, "siu_splash_text.png"))
    print("splash ok", len(sp), "연기 픽셀")


if __name__ == "__main__" and len(sys.argv) > 2 and sys.argv[1] == "splash":
    splash(sys.argv[2], os.path.join(os.path.dirname(os.path.dirname(OUT)), "assets", "branding"))
