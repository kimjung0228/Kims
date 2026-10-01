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

FINAL_F_CAP=8  # exact joint optimization only below this many flag bearers; else greedy fallback

def _f_exposed(brain,enemy,p):
    # True if an enemy flag bearer could walk onto p this same final turn (contest lost if we
    # are not there to meet it: "equal warriors preserve our flag" only holds while we're present).
    return any(brain.d(q,p)<=1 for q in enemy['F'])

def final_flags(brain,view,plans,bmap,enemy,threat,warriors,cap_cost,resources,fix=False):
    """Joint last-turn destinations: preserve flags, deny contest, spend capture budget once.

    fix=False reproduces the original (unmodified) behavior exactly, for callers that don't
    know about the newer accounting (e.g. an unrelated bot sharing this module as a baseline).
    fix=True additionally prices in the score lost by abandoning a currently-held building
    (vacate_loss) and picks a jointly-optimal (not just greedy) assignment under a size cap.
    """
    vacate_loss={}
    if fix:
        # Score lost if flag bearer i abandons src this turn: an owned building left unattended
        # with an enemy flag bearer able to reach it this same turn is neutralized for free.
        for i,(src,_,_) in enumerate(plans):
            b=bmap.get(src)
            if b and b['owner']==view.team and _f_exposed(brain,enemy,src):
                vacate_loss[i]=sum(brain.ledger.bounds(b))/2

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
            if not fix:
                options.append((gain,-cap_cost(b),i,dest));continue
            net=gain-vacate_loss.get(i,0)
            if net<=0:continue  # not worth abandoning src for this
            options.append((net,cap_cost(b),i,dest))

    assign={}
    if not fix:
        used=set();claimed=set()
        for gain,negcost,i,dest in sorted(options,reverse=True):
            if i in used or dest in claimed or -negcost>resources:continue
            assign[i]=dest;used.add(i);claimed.add(dest);resources+=negcost
    elif options and len(plans)<=FINAL_F_CAP:
        by_dest={}
        for net,cost,i,dest in options:
            by_dest.setdefault(dest,[]).append((i,net,cost))
        dests=list(by_dest)
        B=min(int(resources),40)
        dp_states=[{(0,0):0.0}]
        parent=[None]
        for dest in dests:
            check_time(brain.deadline)
            cur=dp_states[-1]
            nxt={}
            par={}
            for state,val in cur.items():
                if val>nxt.get(state,-1.0):
                    nxt[state]=val
                    par[state]=(state,None)
                for i,net,cost in by_dest[dest]:
                    mask,bud=state
                    bit=1<<i
                    if mask&bit:continue
                    nb=bud+cost
                    if nb>B:continue
                    nm=mask|bit
                    cand=val+net
                    if cand>nxt.get((nm,nb),-1.0):
                        nxt[(nm,nb)]=cand
                        par[(nm,nb)]=(state,(i,dest))
            dp_states.append(nxt)
            parent.append(par)
        final=dp_states[-1]
        state=max(final,key=lambda s:final[s])
        for step in range(len(dests),0,-1):
            prev,choice=parent[step][state]
            if choice is not None:
                i,dest=choice
                assign[i]=dest
            state=prev
    elif options:
        # Too many flag bearers for exact DP: fall back to the original greedy order.
        used=set();claimed=set();resv=resources
        for net,cost,i,dest in sorted(options,reverse=True):
            if i in used or dest in claimed or cost>resv:continue
            assign[i]=dest;used.add(i);claimed.add(dest);resv+=-cost

    claimed=set(assign.values())
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
