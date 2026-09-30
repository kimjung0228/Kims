import sim, sys, os
from sim import play
from multiprocessing import Pool
# 고려(K) 진영 전용 평가: 실제 맵 20개 × 상대들 (+ 무작위 맵)
opps=os.environ.get('OPPS','rival_mimicA,rival_mimicB,rival_mimicC,rival_mimicD,rival_flank,rival_econ,bot3').split(',')
REP=int(os.environ.get('REP','2')); GEN=int(os.environ.get('GEN','20'))
def job(a):
    bot,o,real,seed=a
    sim.USE_REAL=real
    g,_=play(o,bot,seed); return bot,o,real,seed,g.winner=='K'
bots=sys.argv[1:]
jobs=[(b,o,True,i+20*k) for b in bots for o in opps for i in range(20) for k in range(int(os.environ.get('K0','1')),int(os.environ.get('K0','1'))+REP)]
jobs+=[(b,o,False,int(os.environ.get('G0','150000'))+s) for b in bots for o in opps for s in range(GEN)]
with Pool(2) as p: res=p.map(job,jobs)
for b in bots:
    rr=[f"{o}:{sum(w for bb,oo,re_,s,w in res if bb==b and oo==o and re_)}/{20*REP}+{sum(w for bb,oo,re_,s,w in res if bb==b and oo==o and not re_)}/{GEN}" for o in opps]
    tr=sum(w for bb,oo,re_,s,w in res if bb==b and re_); tg=sum(w for bb,oo,re_,s,w in res if bb==b and not re_)
    loss_maps=[15,16,17,18,19]
    lm=sum(w for bb,oo,re_,s,w in res if bb==b and re_ and s%20 in loss_maps)
    print(b,'| real',f"{tr}/{20*REP*len(opps)}",'gen',f"{tg}/{GEN*len(opps)}",'| new-loss-maps',f"{lm}/{5*REP*len(opps)}",'|',' '.join(rr),flush=True)
