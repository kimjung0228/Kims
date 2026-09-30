"""Shared accounting; no hidden state or simulator imports in submission code."""
import time

class BudgetExpired(Exception):
    pass

def check_time(deadline):
    if time.perf_counter() >= deadline:
        raise BudgetExpired()

def fallback(view):
    eng=any(b['type']=='ENG' and b['owner']==view.team for b in view.buildings)
    n=view.my_resource//(2 if eng else 3)
    return [f'SPAWN W {n}'] if n else []

class Ledger:
    """Past ownership counts revalued on discovery, with paired unknown scores."""
    def __init__(self):
        self.known={}
        self.counts={}
        self.last_turn=0
    def update(self,view):
        for b in view.buildings:
            p=(b['x'],b['y'])
            if b['score']>=0:
                self.known[p]=self.known[14-p[0],14-p[1]]=b['score']
            if view.turn>1 and view.turn!=self.last_turn and b['owner']!='N':
                key=(p,b['owner'])
                self.counts[key]=self.counts.get(key,0)+1
        self.last_turn=view.turn
    def bounds(self,b):
        p=(b['x'],b['y'])
        if p in self.known:return (self.known[p],)*2
        if b['type']=='PLAZA':return 3,3
        return (2,4) if 5<=p[0]<=9 else (1,2)
    def margin(self,buildings,team,occupation=False):
        # Combine symmetric coefficients before applying bounds, not independent intervals.
        pairs={}
        for b in buildings:
            p=(b['x'],b['y']);key=min(p,(14-p[0],14-p[1]))
            c=(self.counts.get((p,team),0)-self.counts.get((p,'K' if team=='Y' else 'Y'),0)) if occupation else (0 if b['owner']=='N' else 1 if b['owner']==team else -1)
            old=pairs.get(key,(0,self.bounds(b)))
            pairs[key]=(old[0]+c,self.bounds(b))
        lo=hi=0
        for c,(a,b) in pairs.values():
            lo+=c*(a if c>=0 else b);hi+=c*(b if c>=0 else a)
        return lo,hi

def final_flags(brain,view,plans,bmap,enemy,threat,warriors,cap_cost,resources):
    """Joint last-turn destinations: preserve flags, deny contest, spend capture budget once."""
    options=[]
    for i,(src,_,_) in enumerate(plans):
        for dest in brain.n1(src):
            b=bmap.get(dest)
            if not b or b['owner']==view.team:continue
            # Equal warriors preserve our flag, but need strict superiority to remove theirs.
            danger=threat.get(dest,0)
            if warriors.get(dest,0)<danger:continue
            if enemy['F'].get(dest,0) and warriors.get(dest,0)<=danger:continue
            score=sum(brain.ledger.bounds(b))/2
            gain=score*(2 if b['owner']==view.opp and enemy['F'].get(dest,0) else 1)
            options.append((gain,-cap_cost(b),i,dest))
    used=set();claimed=set();assign={}
    for gain,negcost,i,dest in sorted(options,reverse=True):
        if i in used or dest in claimed or -negcost>resources:continue
        assign[i]=dest;used.add(i);claimed.add(dest);resources+=negcost
    for i,plan in enumerate(plans):
        src=plan[0]
        if i in assign:
            plan[1]=assign[i];plan[2]=assign[i]
        else:
            # Leaving an owned building avoids neutralization on flag death.
            candidates=brain.n1(src)
            def safety(p):
                lethal=max(0,threat.get(p,0)-warriors.get(p,0))
                b=bmap.get(p)
                loss=sum(brain.ledger.bounds(b))/2 if b and b['owner']==view.team and lethal else 0
                return (loss,lethal,p in claimed,p!=src)
            plan[1]=min(candidates,key=safety);plan[2]=None
