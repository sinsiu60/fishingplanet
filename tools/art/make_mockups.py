"""
건물 내부 대화 화면 목업 (내부 해상도 480x270 → 2배 확대 960x540)
위: 가게 내부 배경 + 카운터 뒤의 NPC 초상화(2배) / 아래: 대화창 + 메뉴(커서는 찌 모양)
"""
import os, sys
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import make_portraits as MP

W, H, K = 480, 270, 2
FONT = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
FONT_B = "/usr/share/fonts/opentype/noto/NotoSansCJK-Black.ttc"


def c(h):
    return MP.c(h)


def bobber(d, x, y):
    d.rectangle([x, y, x + 5, y + 3], fill=c("#FFFFFF"))
    d.rectangle([x, y + 4, x + 5, y + 7], fill=c("#E84A4A"))
    d.line([(x + 2, y - 3), (x + 2, y)], fill=c("#DDDDDD"))


def haru_shop(d):
    d.rectangle([0, 0, W, 175], fill=c("#6B4A33"))
    for y in range(0, 175, 14):
        d.line([(0, y), (W, y)], fill=c("#5A3D2A"))
    for x in range(30, W, 70):
        d.line([(x, 0), (x, 175)], fill=c("#5A3D2A"))
    # 선반과 낚싯대
    for sx in (20, 350):
        d.rectangle([sx, 40, sx + 110, 44], fill=c("#8A5A3A"))
        d.rectangle([sx, 95, sx + 110, 99], fill=c("#8A5A3A"))
        for i, col in enumerate(["#C9A86A", "#4F7FB0", "#2B2B2B", "#B8B8C8", "#9C6A40"]):
            x = sx + 10 + i * 20
            d.line([(x, 8), (x + 4, 40)], fill=c(col), width=2)
        for i in range(4):
            d.ellipse([sx + 12 + i * 25, 80, sx + 26 + i * 25, 94], fill=c("#4A4A55"))
            d.ellipse([sx + 16 + i * 25, 84, sx + 22 + i * 25, 90], fill=c("#8A8A99"))
    # 등불
    for lx in (150, 330):
        d.line([(lx, 0), (lx, 18)], fill=c("#2A1E1A"))
        d.rectangle([lx - 6, 18, lx + 6, 32], fill=c("#F2C46B"))
    # 창문 (바다)
    d.rectangle([196, 14, 284, 60], fill=c("#8FD0E8"))
    d.rectangle([196, 44, 284, 60], fill=c("#3E7FB0"))
    d.line([(240, 14), (240, 60)], fill=c("#5A3D2A"), width=2)
    d.rectangle([194, 12, 286, 62], outline=c("#4A3020"), width=2)


def ella_shop(d):
    d.rectangle([0, 0, W, 175], fill=c("#1E2A44"))
    for y in range(0, 175, 18):
        for x in range((y // 18 % 2) * 20, W, 40):
            d.rectangle([x, y, x + 38, y + 16], outline=c("#283656"))
    # 빛나는 수정들
    for (x, y, s) in [(40, 60, 14), (70, 110, 10), (400, 50, 16), (440, 120, 10), (120, 30, 8), (360, 110, 9)]:
        for k, mix in ((2.0, 0.12), (1.3, 0.25)):  # 은은한 빛 (배경색과 섞은 색)
            col = tuple(int(30 + (t - b) * mix) if False else int(b + (t - b) * mix) for b, t in zip((30, 42, 68), (63, 191, 179))) + (255,)
            r = int(s * k)
            d.ellipse([x - r, y - r, x + r, y + r], fill=col)
        d.polygon([(x, y - s), (x + s // 2, y), (x, y + s), (x - s // 2, y)], fill=c("#3FBFB3"))
        d.point([(x - 1, y - s // 2)], fill=c("#C8FFF8"))
    # 수정 등불
    for lx in (160, 320):
        d.line([(lx, 0), (lx, 16)], fill=c("#D9B45A"))
        d.polygon([(lx, 16), (lx + 6, 24), (lx, 32), (lx - 6, 24)], fill=c("#7FE6DC"))
    d.arc([180, 6, 300, 90], 180, 360, fill=c("#D9B45A"), width=2)


def counter(d, top="#8A5A3A", front="#6A4128", line="#4A3020"):
    d.rectangle([0, 140, W, 175], fill=c(front))
    d.rectangle([0, 136, W, 143], fill=c(top))
    d.line([(0, 143), (W, 143)], fill=c(line))


def render(shop_fn, portrait, sign, text_lines, menu, name, counter_cols, out):
    base = Image.new("RGBA", (W, H), c("#000000"))
    d = ImageDraw.Draw(base)
    shop_fn(d)
    p = portrait.resize((128, 128), Image.NEAREST)
    base.alpha_composite(p, (176, 22))
    counter(d, *counter_cols)
    # 소품 (카운터 위)
    d.rectangle([60, 126, 92, 136], fill=c("#C9A86A"))
    d.rectangle([380, 122, 400, 136], fill=c("#4A4A55"))
    # 대화창
    d.rectangle([6, 180, 318, 264], fill=c("#000000"), outline=c("#FFFFFF"), width=2)
    d.rectangle([326, 180, 474, 264], fill=c("#000000"), outline=c("#FFFFFF"), width=2)
    bobber(d, 338, 194)
    big = base.resize((W * K, H * K), Image.NEAREST)
    D = ImageDraw.Draw(big)
    f = ImageFont.truetype(FONT, 26)
    fb = ImageFont.truetype(FONT_B, 22)
    # 간판
    D.rectangle([16, 14, 16 + 22 * len(sign) + 28, 54], fill=c("#2A1E1A"))
    D.text((30, 18), sign, font=fb, fill=c("#F2E6C8"))
    # 이름표
    D.text((30, 368), name, font=fb, fill=c("#F2C46B"))
    for i, line in enumerate(text_lines):
        D.text((30, 404 + i * 38), line, font=f, fill=c("#FFFFFF"))
    for i, m in enumerate(menu):
        D.text((700, 374 + i * 38), m, font=f, fill=c("#FFFFFF") if i else c("#F2C46B"))
    big.convert("RGB").save(out)


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else HERE
    render(haru_shop, MP.haru("happy"), "하루네 낚시점",
           ["어서 오라고! 오늘 들어온 카본 낚싯대,", "이거 손맛이 끝내준다니까?"],
           ["사기", "팔기", "대화", "나가기"], "하루 아저씨", ("#8A5A3A", "#6A4128", "#4A3020"),
           os.path.join(out, "mockup_haru_shop.png"))
    render(ella_shop, MP.ella("closed"), "아스테라 수정 공방",
           ["…바다가 오늘따라 조용하네요.", "무엇을 찾으러 오셨나요?"],
           ["사기", "팔기", "대화", "나가기"], "엘라", ("#3A4A6E", "#24304E", "#D9B45A"),
           os.path.join(out, "mockup_ella_shop.png"))
    print("ok")
