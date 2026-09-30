import sys, multiprocessing as mp
import sim, os
from sim import play
sim.USE_REAL = os.environ.get('REAL') == '1'
def one(args):
    a,b,seed,i = args
    if i%2==0:
        g,_=play(a,b,seed); at='Y'
    else:
        g,_=play(b,a,seed); at='K'
    bt='K' if at=='Y' else 'Y'
    r = 0.5 if g.winner=='D' else (1.0 if g.winner==at else 0.0)
    return r, g.score(at)-g.score(bt), g.reason, g.turn
if __name__=='__main__':
    a,b=sys.argv[1],sys.argv[2]; n=int(sys.argv[3]) if len(sys.argv)>3 else 60
    s0=int(sys.argv[4]) if len(sys.argv)>4 else 1000
    # each seed played both sides
    jobs=[(a,b,s0+i//2,i) for i in range(n)]
    with mp.Pool(2) as p: res=p.map(one,jobs)
    w=sum(r for r,*_ in res); d=sum(x for _,x,_,_ in res)/n
    inst=sum(1 for r,_,rs,_ in res if rs=='instant' and r==1.0); at=sum(t for *_,t in res)/n
    print(f"{a} vs {b}: {w}/{n} = {w/n:.2f}  avg diff {d:+.1f}  instant-wins {inst} avg-turn {at:.0f}")
