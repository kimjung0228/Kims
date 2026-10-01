"""Joint flag destinations and warrior capacity, using Hall's matching condition."""


def plan(brain, original, my, enemy, bmap, reach, value, check_time):
    sources=list(my['W'])
    amounts=[my['W'][p] for p in sources]
    masks={}
    capacity={0:0}

    def available(mask):
        if mask not in capacity:
            v=0;bits=mask
            while bits:
                bit=bits & -bits;bits-=bit
                v+=amounts[bit.bit_length()-1]
            capacity[mask]=v
        return capacity[mask]

    def feasible(requirements):
        demands=[(p,n) for p,n in requirements.items() if n]
        unions=[0];needs=[0]
        for p,n in demands:
            if p not in masks:masks[p]=sum(1<<i for i,q in enumerate(sources) if brain.d(p,q)<=1)
            mask=masks[p]
            old=len(unions)
            for i in range(old):
                if not i & 255:
                    check_time(brain.deadline)
                union=unions[i]|mask;need=needs[i]+n
                if available(union)<need:return False
                unions.append(union);needs.append(need)
        return True

    mandatory={}
    dangers=[]
    for p,b in bmap.items():
        if b['owner']!=brain.me:continue
        if not any(brain.d(p,q)<=1 for q in enemy['F']):continue
        dangers.append((value(b),p,reach.get(p,0)+1))
    for _,p,n in sorted(dangers,reverse=True):
        proposed=dict(mandatory);proposed[p]=n
        if feasible(proposed):mandatory=proposed
    beam=[(0.0,[],mandatory)]
    for src,dest,target in original:
        options=[]
        for q in brain.n1(src):
            need=reach.get(q,0)
            building=bmap.get(q)
            if building and building['owner']!=brain.me and enemy['F'].get(q,0):need+=1
            if not feasible({q:need}):continue
            score=0.0
            if target is not None:
                d=brain.d(src,target);nd=brain.d(q,target)
                score=(d-nd)*value(bmap[target])/(d+2)
                if q==target:score+=value(bmap[target])/(2 if bmap[target]['owner']==brain.op else 1)
            if q==src:score+=.01
            score-=.035*need
            options.append((score,q,need))
        if not options:
            # No safe move exists; keep the original least-loss fallback.
            options=[(-100.0,dest,0)]
        options.sort(reverse=True)
        # A small beam handles co-located flags and scarce shared defenders.
        next_beam=[]
        for score,choices,requirements in beam:
            for gain,q,need in options[:4]:
                req=dict(requirements);req[q]=max(req.get(q,0),need)
                if feasible(req):next_beam.append((score+gain,choices+[[src,q,target]],req))
        if not next_beam:
            return original,{}
        next_beam.sort(key=lambda row:row[0],reverse=True)
        beam=next_beam[:24]
        check_time(brain.deadline)
    if not beam:return original,{}
    _,choices,requirements=beam[0]
    return choices,requirements
