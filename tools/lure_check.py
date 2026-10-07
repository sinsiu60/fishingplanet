"""입질 대기 측정 (DESIGN.md 47장). 루어 액션은 삭제됨 (LURE_ACTION.md 개편은 진행하지 않음) — 대기는 기다리기만.

  python tools/lure_check.py baseline [n]     낚시터별 대기(접근 시작) · '쑥'까지 · 등급 분포 (낮 · 맑음, 비밀은 밤)
                                              → tools/lure_baseline_la1.json (루어 삭제 전 '아무것도 안 함' 기준과 비교용)
"""
import random, statistics, sys, os, json
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
from collections import Counter
from src.core.config import load_json
from src.fishing.bite import BiteController, BiteState
N=int(sys.argv[2]) if len(sys.argv)>2 else 300
out={}
for sp in [s["id"] for s in load_json("spots.json")["spots"]]:
    rnd=random.Random(42)
    b=BiteController(rnd)
    from src.fishing.bite import pick_fish
    per="day" if pick_fish("day","clear",20,random.Random(1),sp) else "night"   # 비밀 낚시터는 밤만
    b.set_conditions(per,"clear",sp)
    waits=[]; bites=[]; fish=Counter(); rar=Counter(); none=0
    for i in range(N):
        b.stop(); b.start((0.0,20.0),20.0)
        t=0.0; tw=None
        while t<60:
            b.update(1/60); t+=1/60
            if tw is None and b.state==BiteState.APPROACH: tw=t
            if b.state==BiteState.BITE: break
            b.events.clear()
        if b.state!=BiteState.BITE: none+=1; continue
        waits.append(tw); bites.append(t); fish[b.fish["id"]]+=1; rar[b.fish["rarity"]]+=1
    n=len(bites)
    out[sp]={"wait":statistics.mean(waits),"bite":statistics.mean(bites),"rar":{k:v/n for k,v in rar.items()},"fish":{k:v/n for k,v in fish.items()}}
    print(f"{sp:13s}{'(밤)' if per=='night' else '    '} 접근 시작 {statistics.mean(waits):5.2f}s · 쑥 {statistics.mean(bites):5.2f}s (중앙 {statistics.median(bites):.2f}) · 등급 "+
          " ".join(f"{k} {v/n*100:4.1f}%" for k,v in sorted(rar.items()))+ (f" · 입질 없음 {none}" if none else ""), flush=True)
json.dump(out,open(os.path.join("tools","lure_baseline_la1.json"),"w"),ensure_ascii=False,indent=1)
