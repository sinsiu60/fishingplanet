"""
주요 NPC 초상화 (64x64 픽셀아트, 표정 3종씩 + 표정마다 눈 감은 프레임(_blink)·입 벌린 말하기 프레임(_talk)·둘 다(_blink_talk))
- 백 노인은 입이 수염에 가려서, 말할 때 수염이 1px 내려가고 콧수염 아래가 살짝 벌어짐
- 하루 아저씨 (윤슬 마을 상점), 백 노인 (오두막), 엘라 (아스테라 상점), 오렌 (서재)
- 게임 내부 해상도(480x270)에서 2배로 확대해 128x128로 표시하는 것을 기준으로 함
사용: python make_portraits.py [출력 폴더]
"""
import os, sys
from PIL import Image, ImageDraw

S = 64
OUTLINE = (34, 26, 30, 255)


def new():
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    return img, ImageDraw.Draw(img)


def c(hexs, a=255):
    hexs = hexs.lstrip("#")
    return tuple(int(hexs[i:i + 2], 16) for i in (0, 2, 4)) + (a,)


def outline(img, color=OUTLINE):
    """불투명 영역 바깥 테두리 1px"""
    px = img.load()
    w, h = img.size
    mask = [[px[x, y][3] > 0 for x in range(w)] for y in range(h)]
    out = img.copy()
    op = out.load()
    for y in range(h):
        for x in range(w):
            if mask[y][x]:
                continue
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = x + dx, y + dy
                if 0 <= nx < w and 0 <= ny < h and mask[ny][nx]:
                    op[x, y] = color
                    break
    return out


def P(d, pts, col):
    d.point(pts, fill=col)


# ---------------------------------------------------------------- 하루 아저씨
def haru(expr="neutral", blink=False, talk=False):
    img, d = new()
    skin, skin_s = c("#E2A87A"), c("#C98B5E")
    shirt, shirt_s = c("#4F7FB0"), c("#3E6690")
    hair = c("#3B2A20")
    beard = c("#5A3E2B")
    dark = c("#2A1E1A")
    # 몸통 (작업복 + 앞치마 끈)
    d.polygon([(6, 64), (12, 51), (22, 46), (42, 46), (52, 51), (58, 64)], fill=shirt)
    d.polygon([(40, 47), (52, 51), (58, 64), (44, 64)], fill=shirt_s)
    d.line([(24, 47), (22, 64)], fill=c("#D9C7A3"), width=2)
    d.line([(40, 47), (42, 64)], fill=c("#D9C7A3"), width=2)
    d.rectangle([27, 40, 37, 48], fill=skin_s)
    # 귀
    d.ellipse([16, 25, 21, 33], fill=skin)
    d.ellipse([43, 25, 48, 33], fill=skin_s)
    # 머리
    d.ellipse([19, 9, 45, 21], fill=hair)
    # 얼굴
    d.ellipse([19, 12, 45, 44], fill=skin)
    d.ellipse([33, 14, 45, 43], fill=skin_s)
    d.ellipse([20, 12, 42, 43], fill=skin)
    # 구레나룻 + 턱수염
    d.rectangle([19, 19, 21, 30], fill=hair)
    d.rectangle([43, 19, 45, 30], fill=hair)
    d.polygon([(21, 33), (24, 41), (29, 45), (35, 45), (40, 41), (43, 33), (40, 38), (35, 40), (29, 40), (24, 38)], fill=beard)
    # 두건 (흰 바탕 + 파란 줄)
    d.rectangle([18, 13, 46, 18], fill=c("#F2F2EE"))
    d.line([(18, 15), (46, 15)], fill=c("#3A6EA5"))
    d.line([(18, 17), (46, 17)], fill=c("#3A6EA5"))
    d.polygon([(45, 12), (51, 9), (50, 15), (52, 20), (46, 18)], fill=c("#F2F2EE"))
    P(d, [(48, 12), (49, 16)], c("#3A6EA5"))
    # 코
    d.rectangle([31, 28, 33, 32], fill=skin_s)
    P(d, [(30, 32), (34, 32)], skin_s)
    # 표정
    mouth = c("#6B2020")
    if expr == "neutral":
        d.rectangle([23, 21, 29, 22], fill=dark)
        d.rectangle([35, 21, 41, 22], fill=dark)
        if blink:
            d.line([(24, 27), (28, 27)], fill=dark)
            d.line([(36, 27), (40, 27)], fill=dark)
        else:
            d.rectangle([25, 25, 27, 28], fill=dark)
            d.rectangle([37, 25, 39, 28], fill=dark)
            P(d, [(26, 25), (38, 25)], c("#FFFFFF"))
        if talk:
            d.rectangle([29, 35, 35, 38], fill=mouth)
            d.line([(30, 35), (34, 35)], fill=c("#FFFFFF"))
        else:
            d.line([(28, 36), (36, 36)], fill=c("#7A3B2E"))
            P(d, [(27, 35), (37, 35)], c("#7A3B2E"))
    elif expr == "happy":
        d.rectangle([23, 20, 29, 21], fill=dark)
        d.rectangle([35, 20, 41, 21], fill=dark)
        if blink:   # 웃는 눈을 더 꼭 감음
            d.line([(24, 27), (28, 27)], fill=dark)
            d.line([(36, 27), (40, 27)], fill=dark)
        else:
            d.line([(24, 27), (26, 25), (28, 27)], fill=dark)
            d.line([(36, 27), (38, 25), (40, 27)], fill=dark)
        if talk:    # 크게 웃던 입을 반쯤 닫음
            d.rectangle([27, 34, 37, 37], fill=mouth)
            d.rectangle([28, 34, 36, 35], fill=c("#FFFFFF"))
        else:
            d.rectangle([26, 34, 38, 39], fill=mouth)
            d.rectangle([27, 34, 37, 35], fill=c("#FFFFFF"))
            d.rectangle([29, 38, 35, 39], fill=c("#C4504E"))
        P(d, [(23, 31), (24, 31), (40, 31), (41, 31)], c("#E77C6B"))
    else:  # surprised
        d.rectangle([23, 18, 29, 19], fill=dark)
        d.rectangle([35, 18, 41, 19], fill=dark)
        if blink:
            d.line([(24, 26), (28, 26)], fill=dark)
            d.line([(36, 26), (40, 26)], fill=dark)
        else:
            d.rectangle([24, 23, 28, 28], fill=c("#FFFFFF"))
            d.rectangle([36, 23, 40, 28], fill=c("#FFFFFF"))
            d.rectangle([25, 25, 27, 27], fill=dark)
            d.rectangle([37, 25, 39, 27], fill=dark)
        if talk:
            d.ellipse([30, 35, 34, 39], fill=mouth)
        else:
            d.ellipse([29, 34, 35, 41], fill=mouth)
    return outline(img)


# ---------------------------------------------------------------- 백 노인
def baek(expr="neutral", blink=False, talk=False):
    img, d = new()
    skin, skin_s = c("#C99572"), c("#A87652")
    white, white_s = c("#ECE8DE"), c("#BDB8AC")
    straw, straw_s = c("#C9A86A"), c("#A0823F")
    cape, cape_s = c("#6B7448"), c("#535B37")
    dark = c("#2A1E1A")
    # 도롱이 (짚 우비)
    d.polygon([(4, 64), (10, 46), (22, 40), (42, 40), (54, 46), (60, 64)], fill=cape)
    for x in range(8, 58, 4):
        d.line([(x, 48 + (x % 3)), (x + 1, 64)], fill=cape_s)
    # 얼굴
    d.ellipse([20, 16, 44, 44], fill=skin)
    d.ellipse([34, 18, 44, 43], fill=skin_s)
    d.ellipse([21, 16, 41, 43], fill=skin)
    # 긴 흰 수염 (말할 때 1px 아래로 — 턱이 움직이며 수염이 살짝 흔들림)
    by = 1 if talk else 0
    if talk:   # 콧수염 아래로 살짝 벌어진 입
        d.rectangle([29, 37, 35, 39], fill=c("#4A2A22"))
    d.polygon([(21, 34 + by), (43, 34 + by), (41, 46 + by), (37, 56 + by), (33, 63), (30, 63), (26, 55 + by), (22, 46 + by)],
              fill=white)
    for x in (26, 30, 34, 38):
        d.line([(x, 40 + by), (x + (1 if x > 32 else -1), 56 + by)], fill=white_s)
    if talk:
        d.rectangle([29, 37, 35, 38], fill=c("#4A2A22"))
    # 콧수염
    d.polygon([(23, 33), (31, 32), (33, 32), (41, 33), (43, 38), (38, 35), (32, 35), (26, 35), (21, 38)], fill=white)
    d.rectangle([30, 27, 33, 32], fill=skin_s)
    # 눈썹
    d.rectangle([23, 24, 29, 26], fill=white)
    d.rectangle([35, 24, 41, 26], fill=white)
    # 삿갓
    d.polygon([(2, 22), (32, 2), (62, 22), (56, 24), (8, 24)], fill=straw)
    for i in range(0, 30, 5):
        d.line([(32, 3), (6 + i, 22)], fill=straw_s)
        d.line([(32, 3), (58 - i, 22)], fill=straw_s)
    d.line([(4, 23), (60, 23)], fill=straw_s)
    d.line([(14, 17), (50, 17)], fill=c("#8A6B2F"))  # 끈
    # 볼 주름
    P(d, [(22, 31), (22, 32), (42, 31), (42, 32)], skin_s)
    # 표정
    if expr == "neutral":
        if blink:   # 원래 가는 눈 → 꼭 감으며 눈썹이 살짝 내려옴
            d.line([(25, 30), (27, 30)], fill=dark)
            d.line([(37, 30), (39, 30)], fill=dark)
            d.line([(23, 27), (29, 27)], fill=white_s)
            d.line([(35, 27), (41, 27)], fill=white_s)
        else:
            d.line([(24, 29), (28, 29)], fill=dark)
            d.line([(36, 29), (40, 29)], fill=dark)
    elif expr == "smile":
        if blink:
            d.line([(24, 30), (28, 30)], fill=dark)
            d.line([(36, 30), (40, 30)], fill=dark)
        else:
            d.line([(24, 30), (26, 28), (28, 30)], fill=dark)
            d.line([(36, 30), (38, 28), (40, 30)], fill=dark)
        if not talk:
            d.line([(29, 37), (35, 37)], fill=c("#7A3B2E"))
            P(d, [(28, 36), (36, 36)], c("#7A3B2E"))
    else:  # sharp (진지, 한쪽 눈을 뜸)
        d.line([(24, 29), (28, 29)], fill=dark)
        if blink:
            d.line([(36, 29), (40, 29)], fill=dark)
        else:
            d.rectangle([36, 27, 40, 30], fill=c("#FFFFFF"))
            d.rectangle([37, 28, 39, 30], fill=dark)
            P(d, [(37, 28)], c("#F2E6A0"))
        d.line([(35, 24), (41, 26)], fill=white_s)
    return outline(img)


# ---------------------------------------------------------------- 엘라
def ella(expr="neutral", blink=False, talk=False):
    img, d = new()
    skin, skin_s = c("#F1D4C2"), c("#DDB7A2")
    hair, hair_s, hair_h = c("#D8DEE6"), c("#A9B3C2"), c("#F4F7FB")
    cloak, cloak_s = c("#2B3A67"), c("#202C4F")
    gold = c("#D9B45A")
    teal, teal_h = c("#3FBFB3"), c("#C8FFF8")
    dark = c("#262238")
    # 뒷머리
    d.polygon([(14, 16), (50, 16), (55, 60), (46, 64), (18, 64), (9, 60)], fill=hair)
    d.polygon([(44, 18), (50, 16), (55, 60), (48, 62)], fill=hair_s)
    # 망토 (높은 깃)
    d.polygon([(6, 64), (12, 50), (22, 45), (42, 45), (52, 50), (58, 64)], fill=cloak)
    d.polygon([(42, 45), (52, 50), (58, 64), (46, 64)], fill=cloak_s)
    d.polygon([(20, 44), (26, 41), (32, 50), (38, 41), (44, 44), (40, 52), (32, 56), (24, 52)], fill=cloak)
    d.line([(20, 44), (24, 52), (32, 56), (40, 52), (44, 44)], fill=gold)
    # 목
    d.rectangle([28, 39, 36, 46], fill=skin_s)
    # 수정 펜던트
    d.polygon([(32, 49), (34, 52), (32, 56), (30, 52)], fill=teal)
    P(d, [(31, 51)], teal_h)
    # 얼굴
    d.ellipse([21, 13, 43, 42], fill=skin)
    d.ellipse([35, 15, 43, 41], fill=skin_s)
    d.ellipse([22, 13, 40, 41], fill=skin)
    # 앞머리
    d.polygon([(19, 13), (32, 8), (45, 13), (45, 24), (41, 18), (37, 21), (33, 17), (28, 21), (24, 18), (19, 25)], fill=hair)
    d.line([(26, 11), (24, 18)], fill=hair_s)
    d.line([(37, 11), (37, 20)], fill=hair_s)
    P(d, [(29, 10), (30, 10), (31, 9)], hair_h)
    # 옆머리
    d.polygon([(19, 20), (22, 22), (21, 44), (17, 48)], fill=hair)
    d.polygon([(45, 20), (42, 22), (43, 44), (47, 48)], fill=hair_s)
    # 수정 머리핀
    d.polygon([(43, 11), (46, 14), (43, 18), (40, 14)], fill=teal)
    P(d, [(42, 13), (43, 12)], teal_h)
    # 표정
    d.rectangle([30, 28, 31, 30], fill=skin_s)
    lip, lip_in = c("#B5636B"), c("#7A3440")
    if expr in ("neutral", "smile"):
        for ex in (25, 35):
            d.line([(ex - 1, 24), (ex + 4, 24)], fill=dark)
            if blink:
                d.line([(ex, 27), (ex + 3, 27)], fill=dark)
            else:
                d.rectangle([ex, 25, ex + 3, 27], fill=c("#FFFFFF"))
                d.rectangle([ex + 1, 25, ex + 2, 27], fill=c("#2E8B8B"))
                P(d, [(ex + 1, 25)], teal_h)
        if talk:
            d.rectangle([30, 34, 33, 36], fill=lip_in)
            d.line([(30, 34), (33, 34)], fill=lip)
        elif expr == "neutral":
            d.line([(30, 35), (33, 35)], fill=lip)
        else:
            d.line([(29, 34), (30, 35), (33, 35), (34, 34)], fill=lip)
        if expr == "smile":
            P(d, [(24, 31), (25, 31), (39, 31), (40, 31)], c("#F2A7A7"))
    else:  # closed (눈 감고 미소, 신비로움) — 이미 감은 눈이라 깜빡임은 같은 그림
        d.line([(24, 26), (26, 27), (28, 26)], fill=dark)
        d.line([(35, 26), (37, 27), (39, 26)], fill=dark)
        if talk:
            d.rectangle([30, 34, 33, 36], fill=lip_in)
            d.line([(29, 34), (34, 34)], fill=lip)
        else:
            d.line([(29, 34), (30, 35), (33, 35), (34, 34)], fill=lip)
        P(d, [(24, 30), (25, 30), (39, 30), (40, 30)], c("#F2A7A7"))
    return outline(img)


# ---------------------------------------------------------------- 오렌
def oren(expr="neutral", blink=False, talk=False):
    img, d = new()
    skin, skin_s = c("#E8B896"), c("#CF9A78")
    hair, hair_h, hair_s = c("#7A4E2D"), c("#9C6A40"), c("#5E3B21")
    robe, robe_s, robe_l = c("#2F5D4A"), c("#244A3A"), c("#4E8A6E")
    glass = c("#3A3A44")
    dark = c("#2A1E1A")
    # 로브 + 스카프
    d.polygon([(6, 64), (12, 50), (22, 45), (42, 45), (52, 50), (58, 64)], fill=robe)
    d.polygon([(42, 45), (52, 50), (58, 64), (46, 64)], fill=robe_s)
    d.polygon([(22, 44), (42, 44), (40, 50), (32, 53), (24, 50)], fill=c("#B8863B"))
    d.line([(32, 53), (32, 64)], fill=robe_l)
    d.rectangle([28, 39, 36, 45], fill=skin_s)
    # 곱슬머리 (뒤)
    for (x, y, r) in [(20, 16, 6), (26, 11, 6), (33, 9, 6), (40, 12, 6), (45, 18, 5), (18, 24, 5), (46, 26, 5)]:
        d.ellipse([x - r, y - r, x + r, y + r], fill=hair)
    # 얼굴
    d.ellipse([21, 15, 43, 44], fill=skin)
    d.ellipse([35, 17, 43, 43], fill=skin_s)
    d.ellipse([22, 15, 40, 43], fill=skin)
    # 곱슬머리 (앞)
    for (x, y, r) in [(24, 16, 4), (30, 13, 4), (36, 14, 4), (41, 18, 3)]:
        d.ellipse([x - r, y - r, x + r, y + r], fill=hair)
    for (x, y) in [(23, 14), (29, 11), (35, 12), (20, 18)]:
        P(d, [(x, y), (x + 1, y)], hair_h)
    P(d, [(42, 20), (43, 22)], hair_s)
    # 주근깨
    P(d, [(25, 33), (27, 34), (37, 33), (39, 34)], skin_s)
    d.rectangle([31, 30, 32, 33], fill=skin_s)
    # 안경
    d.ellipse([22, 24, 30, 32], fill=c("#E4F1FF"))
    d.ellipse([34, 24, 42, 32], fill=c("#E4F1FF"))
    d.ellipse([22, 24, 30, 32], outline=glass)
    d.ellipse([34, 24, 42, 32], outline=glass)
    d.line([(30, 27), (34, 27)], fill=glass)
    P(d, [(24, 26), (36, 26)], c("#FFFFFF"))
    # 표정
    mouth, lipc = c("#6B2020"), c("#8A4A3A")
    if expr == "neutral":
        d.line([(23, 21), (29, 21)], fill=hair_s)
        d.line([(35, 21), (41, 21)], fill=hair_s)
        if blink:
            d.line([(24, 28), (27, 28)], fill=dark)
            d.line([(36, 28), (39, 28)], fill=dark)
        else:
            d.rectangle([25, 27, 26, 29], fill=dark)
            d.rectangle([37, 27, 38, 29], fill=dark)
        if talk:
            d.rectangle([29, 36, 34, 39], fill=mouth)
            d.line([(30, 36), (33, 36)], fill=c("#FFFFFF"))
        else:
            d.line([(29, 37), (34, 37)], fill=lipc)
    elif expr == "excited":
        d.line([(23, 20), (29, 19)], fill=hair_s)
        d.line([(35, 19), (41, 20)], fill=hair_s)
        for ex in (26, 38):  # 반짝이는 눈
            if blink:
                d.line([(ex - 2, 28), (ex, 27), (ex + 2, 28)], fill=dark)
            else:
                P(d, [(ex, 26), (ex, 27), (ex, 28), (ex, 29), (ex - 1, 27), (ex + 1, 27), (ex - 1, 28), (ex + 1, 28)], dark)
                P(d, [(ex, 27)], c("#FFFFFF"))
        if talk:   # 크게 벌린 입을 반쯤 닫음
            d.ellipse([29, 36, 34, 39], fill=mouth)
            d.line([(30, 36), (33, 36)], fill=c("#FFFFFF"))
        else:
            d.ellipse([28, 35, 35, 41], fill=mouth)
            d.rectangle([29, 35, 34, 36], fill=c("#FFFFFF"))
        P(d, [(24, 34), (40, 34)], c("#E8877A"))
    else:  # thinking (고민)
        d.line([(23, 22), (29, 20)], fill=hair_s)
        d.line([(35, 20), (41, 21)], fill=hair_s)
        if blink:
            d.line([(26, 27), (29, 27)], fill=dark)
            d.line([(38, 27), (41, 27)], fill=dark)
        else:
            d.rectangle([27, 26, 28, 28], fill=dark)
            d.rectangle([39, 26, 40, 28], fill=dark)
        if talk:
            d.rectangle([30, 37, 34, 39], fill=mouth)
        else:
            d.line([(29, 38), (33, 37), (35, 37)], fill=lipc)
    return outline(img)


CHARS = {
    "haru": (haru, ["neutral", "happy", "surprised"]),
    "baek": (baek, ["neutral", "smile", "sharp"]),
    "ella": (ella, ["neutral", "smile", "closed"]),
    "oren": (oren, ["neutral", "excited", "thinking"]),
}

if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "png")
    os.makedirs(out, exist_ok=True)
    for name, (fn, exprs) in CHARS.items():
        for e in exprs:
            fn(e).save(os.path.join(out, f"npc_{name}_{e}.png"))
            fn(e, blink=True).save(os.path.join(out, f"npc_{name}_{e}_blink.png"))   # 눈 감은 프레임 (깜빡임)
            fn(e, talk=True).save(os.path.join(out, f"npc_{name}_{e}_talk.png"))     # 입 벌린 말하기 프레임
            fn(e, blink=True, talk=True).save(os.path.join(out, f"npc_{name}_{e}_blink_talk.png"))
    print("saved to", out)
