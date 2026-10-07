"""비늘석 스프라이트 (32x32, 등급 4종 + 빈 칸), 외곽선은 장비 그림과 같은 #362F53"""
import os, sys
from PIL import Image, ImageDraw
S=32; OUT=sys.argv[1] if len(sys.argv)>1 else "png"
OL=(54,47,83,255)
def c(h,a=255): h=h.lstrip('#'); return tuple(int(h[i:i+2],16) for i in (0,2,4))+(a,)
def outline(im):
    px=im.load(); o=im.copy(); op=o.load()
    for y in range(S):
        for x in range(S):
            if px[x,y][3]: continue
            for dx,dy in ((1,0),(-1,0),(0,1),(0,-1)):
                nx,ny=x+dx,y+dy
                if 0<=nx<S and 0<=ny<S and px[nx,ny][3]: op[x,y]=OL; break
    return o
GR={"common":["#FFFFFF","#D8DDE6","#9AA3B5","#6A7286"],
    "uncommon":["#D8FFE0","#7ED68A","#4FA562","#2E6E3E"],
    "rare":["#E0F2FF","#6FB7FF","#3F82D0","#25508A"],
    "legend":["#FFF6D0","#FFDC78","#E0A840","#A06A20"]}
def stone(g):
    hi,base,mid,dark=[c(v) for v in GR[g]]
    im=Image.new("RGBA",(S,S),(0,0,0,0)); d=ImageDraw.Draw(im)
    # 비늘 모양: 위는 둥글고 아래는 뾰족
    shape=[(16,4),(22,5),(26,9),(27,15),(25,21),(21,26),(16,29),(11,26),(7,21),(5,15),(6,9),(10,5)]
    d.polygon(shape,fill=base)
    d.polygon([(16,4),(22,5),(26,9),(27,15),(25,21),(21,26),(16,29),(18,20),(19,12)],fill=mid)
    d.polygon([(25,21),(21,26),(16,29),(18,22)],fill=dark)
    # 비늘 결 (곡선 3줄)
    for yy,xs in ((11,(13,19)),(16,(10,16,22)),(21,(13,19))):
        for cx in xs:
            d.arc([cx-3,yy-3,cx+3,yy+3],180,360,fill=dark if cx>=16 else mid)
    # 하이라이트
    d.line([(9,9),(12,6)],fill=hi); d.point([(8,11),(13,6),(10,13)],fill=hi)
    im=outline(im); d=ImageDraw.Draw(im)
    if g in("rare","legend"):
        d.point([(24,4),(23,3),(25,3),(24,2),(24,5) if g=="legend" else (24,4)],fill=c("#FFFFFF"))
    if g=="legend":
        d.point([(5,24),(4,25),(6,25),(5,26)],fill=c("#FFF6D0"))
    return im
def empty():
    im=Image.new("RGBA",(S,S),(0,0,0,0)); d=ImageDraw.Draw(im)
    shape=[(16,4),(22,5),(26,9),(27,15),(25,21),(21,26),(16,29),(11,26),(7,21),(5,15),(6,9),(10,5)]
    for i in range(len(shape)):
        a,b=shape[i],shape[(i+1)%len(shape)]
        if i%2==0: d.line([a,b],fill=c("#5A6896"))
    d.line([(16,12),(16,20)],fill=c("#5A6896")); d.line([(12,16),(20,16)],fill=c("#5A6896"))
    return im
os.makedirs(OUT,exist_ok=True)
for g in GR:
    st=stone(g); st.save(f"{OUT}/scalestone_{g}.png")
    st.resize((16,16),Image.BOX).save(f"{OUT}/scalestone_{g}_16.png")
empty().save(f"{OUT}/scalestone_slot_empty.png")
print("ok")
