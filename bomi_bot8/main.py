"""BomiBot 8: joint capture missions and feasible warrior allocation.

Warrior assignments can exchange sources while preserving earlier coverage.
Flag destinations are admitted only when their escorts can coexist, including
immediate defense obligations. Runtime uses public observations only.
"""
from __future__ import annotations
import sys
import time
from strategy_common import Ledger, BudgetExpired, check_time, fallback, final_flags
from collections import deque
from coupled import plan as coupled_plan
from protocol import BALANCE, DIRS, spawn, move, priority, tele, run
N = 15
INF = 10 ** 6
CFG = BALANCE
FC = CFG['units']['F']['cost']
TOTAL_TURNS = CFG['total_turns']
FUNC_BONUS = {'HALL': 1.0, 'ENG': 0.5, 'LIBRARY': 0.8, 'HOSPITAL': 1.2, 'WATCH': 0.3, 'STATION': 0.2, 'DEPOT': 0.0, 'PLAZA': 0.0}
_BRAINS = {}
SIEGE_MULT = 1.5
SIEGE_ADD = 30
ECON_K = 12.0
HOME_BIAS = 0.08
HOME_TURNS = 60
MIN_GAR = 2
LOCAL3_MIN = 0.15
GAR_RADIUS = 30
PRED_PR = 9.5
PRED_ALPHA = 0.5
CONVOY_N = 5
ENG_R = 2
ENG_PR = 2.0
RETAKE_MULT = 1.6
LEAD_M = 0
LEAD_DEEP = 0.5
STRIKE_MULT = 0.7
STRIKE_TGT = 2.0
STRIKE_RALLY = 2.0
CONCENTRATE_TH = 0.7
GARRISON_BOOST = 2.0
CONVOY_PR = 6.5
CONVOY_R = 6
PRED_TIME_LIMIT = 0.12
MID_F_HI = 4
MID_F_LO = 2
RALLY_D = 5
TELE_GAIN = 4
EARLY_F = 4
EARLY_T = 8
EO_MULT = 0.75
STICK = 1.5
GARRISON_R = 2

def log(*a):
    print(*a, file=sys.stderr)

def idx(x, y):
    return y * N + x

def cheb(a, b):
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))

class Brain:
    """게임당 한 번 만드는 고정 정보 + 턴 간 기억."""

    def __init__(self, init):
        self.init = init
        self.me = init.team
        self.op = init.opp
        self.base = init.bases[self.me]
        self.obase = init.bases[self.op]
        self.passable = [[init.passable(x, y) for x in range(N)] for y in range(N)]
        self.nbrs = {}
        for y in range(N):
            for x in range(N):
                if not self.passable[y][x]:
                    continue
                lst = []
                for d, (dx, dy) in DIRS.items():
                    nx, ny = (x + dx, y + dy)
                    if 0 <= nx < N and 0 <= ny < N and self.passable[ny][nx]:
                        lst.append((d, (nx, ny)))
                self.nbrs[x, y] = lst
        self.dist = {}
        for src in self.nbrs:
            dd = [INF] * (N * N)
            dd[idx(*src)] = 0
            q = deque([src])
            while q:
                c = q.popleft()
                dc = dd[idx(*c)]
                for _, n in self.nbrs[c]:
                    i = idx(*n)
                    if dd[i] == INF:
                        dd[i] = dc + 1
                        q.append(n)
            self.dist[src] = dd
        self.near = {p: [p] + [n for _, n in ns] for p, ns in self.nbrs.items()}
        self.near2 = {p: set((q for n in self.near[p] for q in self.near[n])) for p in self.nbrs}
        self.predicted_flags = {}
        self.prediction_error = 0.0
        self.stalled = {}
        self.ledger = Ledger()
        self.deadline = float('inf')
        self.bpos = {(b['x'], b['y']): b for b in init.buildings}
        self.known = {}
        self.depot_got = set()
        self.opp_brain = None
        self.fmem = {}
        self.fortress = min(self.bpos, key=lambda p: self.d(self.base, p))

    def d(self, a, b):
        return self.dist[a][idx(*b)] if a in self.dist else INF

    def n1(self, c):
        """c 와 거리 1 이내 칸 (자기 자신 포함)."""
        return self.near.get(c, [c])

    def region(self, x):
        if x <= 4:
            return 'sinchon'
        if x >= 10:
            return 'anam'
        return 'center'

def est_score(brain, b):
    p = (b['x'], b['y'])
    if p in brain.known:
        return brain.known[p]
    if b['type'] == 'PLAZA':
        return 3
    return 3.0 if brain.region(b['x']) == 'center' else 1.5

def econ_wpt(brain, b):
    """이 건물을 내가 가지면(상대에게서 뺏으면) 늘어나는 '턴당 전투병 생산량 차이'."""
    c = brain.ctx
    t = b['type']
    mine = b['owner'] == brain.me
    theirs = b['owner'] == brain.op
    g = 0.0
    if t == 'HALL':
        g += 2.0 / c['wc']
        if theirs:
            g += 2.0 / c['ewc']
    elif t == 'ENG':
        k = c['my_engs'] - (1 if mine else 0)
        if k == 0:
            g += c['income'] / 2.0 - c['income'] / 3.0
        if theirs and c['e_engs'] == 1:
            g += c['e_income'] / 2.0 - c['e_income'] / 3.0
    return g

def value(brain, b, turn):
    """건물 가치 = (예상) 점수 + 경제 가치(전투병 생산량 환산) + 기능 보너스."""
    v = est_score(brain, b)
    left = max(0.0, (TOTAL_TURNS - turn) / TOTAL_TURNS)
    v += FUNC_BONUS.get(b['type'], 0) * left
    v += ECON_K * econ_wpt(brain, b) * left
    if b['type'] == 'HOSPITAL':
        target = (b['x'], b['y'])
        others = [brain.base] + [p for p in brain.ctx.get('hospitals', []) if p != target]
        savings = [max(0, min((brain.d(sp, p) for sp in others)) - brain.d(target, p)) for p in brain.bpos]
        v += min(12.0, sum(savings) / len(savings) * 1.5) * left
    if b['type'] == 'DEPOT' and (b['x'], b['y']) not in brain.depot_got:
        v += 2.5
    return v
_MIRROR = {}
_FLIP = {'U': 'D', 'D': 'U', 'L': 'R', 'R': 'L'}

def _m(x, y):
    return (N - 1 - x, N - 1 - y)

def _mirror_init(init):
    """연세(Y) 진영일 때 판을 180도 돌려, 고려(K) 진영과 똑같은 관점으로 판단하게 한다."""
    from campus_bot import Init
    terrain = [[init.terrain[N - 1 - y][N - 1 - x] for x in range(N)] for y in range(N)]
    buildings = [dict(b, x=_m(b['x'], b['y'])[0], y=_m(b['x'], b['y'])[1]) for b in init.buildings]
    bases = {t: _m(*p) for t, p in init.bases.items()}
    return Init(init.width, init.height, init.team, terrain, buildings, bases)

def _mirror_view(view, minit):
    from campus_bot import View
    units = [dict(u, x=_m(u['x'], u['y'])[0], y=_m(u['x'], u['y'])[1]) for u in view.units]
    buildings = [dict(b, x=_m(b['x'], b['y'])[0], y=_m(b['x'], b['y'])[1]) for b in view.buildings]
    return View(view.turn, minit, view.my_resource, view.opp_resource, units, buildings)

def _unmirror_cmd(c):
    t = c.split()
    try:
        if t[0] == 'SPAWN' and len(t) == 5:
            x, y = _m(int(t[3]), int(t[4]))
            return ' '.join(t[:3] + [str(x), str(y)])
        if t[0] == 'MOVE':
            x, y = _m(int(t[1]), int(t[2]))
            return ' '.join([t[0], str(x), str(y), t[3], t[4], _FLIP[t[5]]])
        if t[0] == 'MOVE2':
            x, y = _m(int(t[1]), int(t[2]))
            return ' '.join([t[0], str(x), str(y), t[3], t[4], _FLIP[t[5]], _FLIP[t[6]]])
        if t[0] == 'TELE':
            x, y = _m(int(t[1]), int(t[2]))
            tx, ty = _m(int(t[5]), int(t[6]))
            return ' '.join([t[0], str(x), str(y), t[3], t[4], str(tx), str(ty)])
        if t[0] == 'PRIORITY':
            v = list(map(int, t[1:]))
            out = []
            for i in range(0, len(v) - 1, 2):
                out += list(_m(v[i], v[i + 1]))
            return ' '.join(['PRIORITY'] + [str(a) for a in out])
    except (ValueError, IndexError, KeyError):
        return c
    return c

def decide(view, init):
    import time
    t0 = time.perf_counter()
    try:
        return _decide_entry(view, init)
    finally:
        dt = time.perf_counter() - t0
        for b in _BRAINS.values():
            b.slow = dt > PRED_TIME_LIMIT and view.turn > 1

def _decide_entry(view, init):
    try:
        if init.team == 'Y':
            minit = _MIRROR.get(id(init))
            if minit is None:
                minit = _MIRROR[id(init)] = _mirror_init(init)
            brain = _BRAINS.get(id(minit))
            if brain is None:
                brain = _BRAINS[id(minit)] = Brain(minit)
            brain.deadline = time.perf_counter() + (2.5 if view.turn == 1 else 0.15)
            return [_unmirror_cmd(c) for c in _decide(brain, _mirror_view(view, minit))]
        brain = _BRAINS.get(id(init))
        if brain is None:
            brain = _BRAINS[id(init)] = Brain(init)
        brain.deadline = time.perf_counter() + (2.5 if view.turn == 1 else 0.15)
        return _decide(brain, view)
    except BudgetExpired:
        return fallback(view)
    except Exception as e:
        log('ERR', repr(e))
        return []
_PREDICTING = [False]

def predict_enemy(brain, view):
    """상대도 우리와 비슷하게 생각한다고 가정하고, 상대 관점에서 우리 로직을 돌려 다음 이동을 예측한다."""
    from campus_bot import Init, View
    if brain.opp_brain is None:
        oi = brain.init
        oinit = Init(oi.width, oi.height, brain.op, oi.terrain, oi.buildings, oi.bases)
        import copy
        ob = copy.copy(brain)
        ob.init = oinit
        ob.me, ob.op = (brain.op, brain.me)
        ob.base, ob.obase = (brain.obase, brain.base)
        ob.known = dict(brain.known)
        ob.depot_got = set()
        ob.ledger = Ledger()
        ob.fmem = {}
        ob.opp_brain = None
        ob.slow = False
        brain.opp_brain = ob
    ob = brain.opp_brain
    ob.deadline = brain.deadline
    oview = View(view.turn, ob.init, view.opp_resource, view.my_resource, view.units, view.buildings)
    _PREDICTING[0] = True
    try:
        out = _decide(ob, oview)
    except BudgetExpired:
        raise
    except Exception:
        out = []
    finally:
        _PREDICTING[0] = False
    units = {}
    for u in view.units:
        if u['team'] == brain.op:
            k = (u['kind'], (u['x'], u['y']))
            units[k] = units.get(k, 0) + u['count']
    ob_base = brain.obase
    for c in out:
        t = c.split()
        if t[0] == 'SPAWN':
            pos = (int(t[3]), int(t[4])) if len(t) == 5 else ob_base
            units[t[1], pos] = units.get((t[1], pos), 0) + int(t[2])
    moved = {}
    for c in out:
        t = c.split()
        if t[0] == 'MOVE':
            src = (int(t[1]), int(t[2]))
            k = t[3]
            n = int(t[4])
            dx, dy = DIRS[t[5]]
            dst = (src[0] + dx, src[1] + dy)
            have = units.get((k, src), 0)
            m = min(n, have)
            if m <= 0:
                continue
            units[k, src] = have - m
            moved[k, dst] = moved.get((k, dst), 0) + m
    for k, v in moved.items():
        units[k] = units.get(k, 0) + v
    pf = {p: c for (k, p), c in units.items() if k == 'F' and c > 0}
    pw = {p: c for (k, p), c in units.items() if k == 'W' and c > 0}
    return (pf, pw)

def _decide(brain, view):
    me, op = (brain.me, brain.op)
    turn = view.turn
    cmds = []
    check_time(brain.deadline)
    brain.ledger.update(view)
    for b in view.buildings:
        p = (b['x'], b['y'])
        if b['score'] >= 0:
            brain.known[p] = b['score']
            brain.known[14 - p[0], 14 - p[1]] = b['score']
        if b['type'] == 'DEPOT' and b['owner'] == me:
            brain.depot_got.add(p)
    bmap = {(b['x'], b['y']): b for b in view.buildings}
    my = {'F': {}, 'W': {}, 'S': {}}
    en = {'F': {}, 'W': {}, 'S': {}}
    for u in view.units:
        tgt = my if u['team'] == me else en
        p = (u['x'], u['y'])
        tgt[u['kind']][p] = tgt[u['kind']].get(p, 0) + u['count']
    owned = [b for b in view.buildings if b['owner'] == me]
    eowned = [b for b in view.buildings if b['owner'] == op]
    my_halls = sum((b['type'] == 'HALL' for b in owned))
    my_engs = sum((b['type'] == 'ENG' for b in owned))
    my_lib = any((b['type'] == 'LIBRARY' for b in owned))
    e_engs = sum((b['type'] == 'ENG' for b in eowned))
    wc = max(CFG['buildings']['eng_cost_floor'], CFG['units']['W']['cost'] - my_engs)
    ewc = max(CFG['buildings']['eng_cost_floor'], CFG['units']['W']['cost'] - e_engs)
    income = CFG['resource']['base_income'] + CFG['resource']['hall_bonus'] * my_halls
    e_halls = sum((b['type'] == 'HALL' for b in eowned))
    e_income = CFG['resource']['base_income'] + CFG['resource']['hall_bonus'] * e_halls
    brain.ctx = {'wc': wc, 'ewc': ewc, 'my_engs': my_engs, 'e_engs': e_engs, 'income': income, 'e_income': e_income, 'hospitals': [(b['x'], b['y']) for b in owned if b['type'] == 'HOSPITAL']}

    def cap_cost(b):
        c = CFG['capture']['capture_cost'] * (CFG['capture']['plaza_multiplier'] if b['type'] == 'PLAZA' else 1)
        if my_lib:
            c = max(CFG['capture']['min_capture_cost'], c - CFG['buildings']['library_discount'])
        return c
    e_spawn_pts = [brain.obase] + [(b['x'], b['y']) for b in eowned if b['type'] == 'HOSPITAL']
    e_capW = view.opp_resource // ewc
    e_capF = view.opp_resource // FC
    ereach = {}
    eflag1 = {}
    for c in brain.nbrs:
        s = 0
        f = 0
        for n in brain.n1(c):
            s += en['W'].get(n, 0)
            f += en['F'].get(n, 0)
        if any((sp in brain.n1(c) for sp in e_spawn_pts)):
            s += e_capW
            f += e_capF
        ereach[c] = s
        eflag1[c] = f
    ereach_raw = dict(ereach)
    pf_pred, pw_pred = ({}, {})
    if not _PREDICTING[0] and (not getattr(brain, 'slow', False)):
        pf_pred, pw_pred = predict_enemy(brain, view)
        alpha = PRED_ALPHA
        if alpha < 1.0:
            for c in list(ereach.keys()):
                ereach[c] = max(pw_pred.get(c, 0), int(ereach[c] * alpha + 0.999))
    ereach2 = {}
    ew_items = list(en['W'].items())
    for c in brain.nbrs:
        check_time(brain.deadline)
        s2 = sum((en['W'].get(q, 0) for q in brain.near2[c]))
        if any((brain.d(sp, c) <= 2 for sp in e_spawn_pts)):
            s2 += e_capW
        ereach2[c] = s2
    e_st = [(b['x'], b['y']) for b in eowned if b['type'] == 'STATION']
    if len(e_st) >= 2:
        for st in e_st:
            others_w = max((en['W'].get(o, 0) for o in e_st if o != st), default=0)
            others_f = max((en['F'].get(o, 0) for o in e_st if o != st), default=0)
            ereach[st] = ereach.get(st, 0) + min(5, others_w)
            ereach_raw[st] = ereach_raw.get(st, 0) + min(5, others_w)
            eflag1[st] = eflag1.get(st, 0) + min(5, others_f)
    open_targets = [b for b in view.buildings if b['owner'] != me]
    my_sc = sum((est_score(brain, b) for b in owned))
    en_sc = sum((est_score(brain, b) for b in eowned))
    leading = LEAD_M > 0 and turn > 20 and (my_sc >= en_sc + LEAD_M)
    n_w0 = sum(my['W'].values())
    n_ew0 = sum(en['W'].values())
    strike = turn > 10 and e_engs > my_engs and (n_w0 >= STRIKE_MULT * n_ew0)
    n_f = sum(my['F'].values())
    n_w = sum(my['W'].values())
    n_ew = sum(en['W'].values())
    outnumbered = n_ew > 0 and n_w < CONCENTRATE_TH * n_ew
    need_cap = 0
    seen_b = set()
    for p in my['F']:
        for n in brain.n1(p):
            b = bmap.get(n)
            if b and b['owner'] != me and (n not in seen_b):
                seen_b.add(n)
                need_cap += cap_cost(b)
    reserve = max(0, need_cap - income)
    budget = max(0, view.my_resource - reserve)
    spawn_pts = [brain.base] + [(b['x'], b['y']) for b in owned if b['type'] == 'HOSPITAL']

    def best_spawn(targets):
        if not targets:
            return brain.base
        return min(spawn_pts, key=lambda s: (min((brain.d(s, t) for t in targets)), s != brain.base))
    useful_targets = [b for b in open_targets if min((brain.d(s, (b['x'], b['y'])) for s in spawn_pts)) <= TOTAL_TURNS - turn + 1]
    if not useful_targets:
        want_f = 0
    elif turn <= EARLY_T:
        want_f = min(len(open_targets), EARLY_F)
    else:
        want_f = min(len(open_targets), MID_F_HI if n_w >= 0.75 * n_ew else MID_F_LO)
        if n_w >= n_ew + 6:
            want_f = min(len(open_targets), 5)
    spawned = []
    make_f = 0
    if n_f < want_f and budget >= FC:
        lim = want_f - n_f
        if turn > 12 and n_w < n_ew:
            lim = min(lim, 1)
        make_f = min(lim, budget // FC)
    if make_f:
        fpos = best_spawn([(b['x'], b['y']) for b in useful_targets])
        budget -= make_f * FC
        spawned.append(('F', make_f, fpos))
    make_w = budget // wc
    if make_w:
        front = [p for p in en['F']] + [(b['x'], b['y']) for b in open_targets]
        tasks = []
        for b in owned:
            p = (b['x'], b['y'])
            fd = min((brain.d(q, p) for q in en['F']), default=INF)
            if fd <= 5:
                radius = max(1, min(3, fd))
                threat = sum((c for q, c in en['W'].items() if brain.d(q, p) <= radius))
                have = sum((c / max(1, brain.d(q, p)) for q, c in my['W'].items() if brain.d(q, p) <= radius))
                tasks.append((p, max(0, threat + 2 - have), (8 + value(brain, b, turn)) / (fd + 1)))
        for p, nf in my['F'].items():
            if not open_targets:
                continue
            tp = min(open_targets, key=lambda b: brain.d(p, (b['x'], b['y'])))
            target = (tp['x'], tp['y'])
            need = max(3, min(12, ereach2.get(p, 0) + 1))
            have = sum((c for q, c in my['W'].items() if brain.d(q, p) <= 2))
            tasks.append((p, max(0, need - have), 5 + value(brain, tp, turn) / (brain.d(p, target) + 2)))
        allocations = {}
        for _ in range(make_w):
            best = None
            for sp in spawn_pts:
                benefit = 0.0
                for p, need, weight in tasks:
                    supplied = sum((n / (brain.d(origin, p) + 1) for origin, n in allocations.items()))
                    deficit = max(0.0, need - supplied)
                    benefit += weight * min(1.0, deficit) / (brain.d(sp, p) + 1)
                if best is None or benefit > best[0]:
                    best = (benefit, sp)
            wp = best[1] if best and best[0] > 0 else best_spawn(front)
            allocations[wp] = allocations.get(wp, 0) + 1
        for wp, amount in allocations.items():
            spawned.append(('W', amount, wp))
    for kind, cnt, pos in spawned:
        if pos == brain.base:
            cmds.append(spawn(kind, cnt))
        else:
            cmds.append(spawn(kind, cnt, pos[0], pos[1]))
        my[kind][pos] = my[kind].get(pos, 0) + cnt

    def my_cover(c):
        return sum((my['W'].get(n, 0) for n in brain.n1(c)))
    moves = {}
    f_dest = {}
    f_target_of = {}

    def add_move(src, kind, dst, cnt=1):
        if src == dst:
            return
        for dname, n in brain.nbrs[src]:
            if n == dst:
                k = (src, kind, dname)
                moves[k] = moves.get(k, 0) + cnt
                return

    def threat(c):
        return ereach_raw.get(c, 0)

    def danger(c):
        return threat(c) - my_cover(c)
    flags = []
    for p, c in my['F'].items():
        flags += [p] * c
    claimed = set()
    free_flags = []
    fplans = []
    for p in flags:
        b = bmap.get(p)
        if b and b['owner'] != me and (p not in claimed):
            claimed.add(p)
            f_target_of_idx = len(f_target_of)
            f_target_of[f_target_of_idx] = p
            if threat(p) > 0 and danger(p) >= 0 and (threat(p) >= my_cover(p)):
                pass
            f_dest[p] = f_dest.get(p, 0) + 1
            fplans.append([p, p, p])
        else:
            free_flags.append(p)

    def target_eff(fp, b):
        tp = (b['x'], b['y'])
        dd = brain.d(fp, tp)
        if dd >= INF:
            return -1
        v = value(brain, b, turn)
        tl = TOTAL_TURNS - turn
        if tl < 12:
            if dd + (1 if b['owner'] == op else 0) > tl + 1 and (not (b['owner'] == op and dd <= tl + 1)):
                return -1
        if b['type'] == 'ENG' and brain.d(brain.base, tp) < brain.d(brain.obase, tp) and (b['owner'] != me):
            v *= RETAKE_MULT
        if strike and b['type'] == 'ENG' and (b['owner'] == op):
            v *= STRIKE_TGT
        if leading and brain.d(brain.obase, tp) < brain.d(brain.base, tp):
            v *= LEAD_DEEP
        if b['owner'] == op:
            v *= EO_MULT
        ew_here = en['W'].get(tp, 0)
        mw_near = sum((my['W'].get(n, 0) for n in brain.n1(tp)))
        if ew_here > mw_near:
            v *= 0.3
        if en['F'].get(tp, 0) and mw_near == 0:
            v *= 0.5
        ew3 = sum((c for q, c in en['W'].items() if brain.d(q, tp) <= 3))
        if any((brain.d(sp, tp) <= 3 for sp in e_spawn_pts)):
            ew3 += e_capW
        mw3 = sum((c for q, c in my['W'].items() if brain.d(q, tp) <= 3))
        if ew3 > mw3:
            v *= max(LOCAL3_MIN, (mw3 + 1.0) / (ew3 + 1.0))
        if brain.d(brain.obase, tp) < brain.d(brain.base, tp) and n_w <= n_ew:
            v *= 0.7
        if turn <= HOME_TURNS:
            safety = brain.d(brain.obase, tp) - brain.d(brain.base, tp)
            v *= max(0.3, 1.0 + HOME_BIAS * max(-8, min(8, safety)))
        return v / (dd + 2)
    remaining = [b for b in open_targets if (b['x'], b['y']) not in claimed]
    prev_t = {}
    for i, fp in enumerate(free_flags):
        lst = brain.fmem.get(fp)
        if lst:
            prev_t[i] = lst.pop()
    assign = {}
    F = len(free_flags)
    T = len(remaining)
    pairs = []
    for i, fp in enumerate(free_flags):
        for b in remaining:
            e = target_eff(fp, b)
            if e > 0:
                if prev_t.get(i) == (b['x'], b['y']):
                    e *= STICK
                pairs.append((e, i, (b['x'], b['y'])))
    # Exact small bipartite assignment, one flag per capture mission.
    if F <= 10:
        by_target={}
        for utility,i,target in pairs:
            by_target.setdefault(target,[]).append((i,utility))
        dp={0:(0.0,{})}
        for target,options in by_target.items():
            ndp=dict(dp)
            for mask,(utility,chosen) in dp.items():
                for i,gain in options:
                    bit=1<<i
                    if mask & bit:continue
                    new=mask|bit;score=utility+gain
                    if score>ndp.get(new,(-1,None))[0]:
                        ndp[new]=(score,dict(chosen,**{}) | {i:target})
            dp=ndp
        assign=max(dp.values(),key=lambda row:row[0])[1]
    else:
        pairs.sort(reverse=True)
        used_t=set()
        for utility,i,tp in pairs:
            if i not in assign and tp not in used_t:
                assign[i]=tp;used_t.add(tp)
    for i, fp in enumerate(free_flags):
        tp = assign.get(i)
        if tp is None:
            b = bmap.get(fp)
            dest = fp
            if b and b['owner'] == me and (threat(fp) > 0):
                opts = [n for _, n in brain.nbrs[fp] if n not in bmap]
                if opts:
                    dest = min(opts, key=lambda n: danger(n))
            fplans.append([fp, dest, None])
            f_dest[dest] = f_dest.get(dest, 0) + 1
            continue
        dcur = brain.d(fp, tp)
        steps = [n for _, n in brain.nbrs[fp] if brain.d(n, tp) == dcur - 1]
        safe_steps = [n for n in steps if threat(n) == 0 or my_cover(n) >= threat(n)]
        if safe_steps:
            dest = min(safe_steps, key=lambda n: (danger(n), ereach2.get(n, 0), n))
        elif threat(fp) == 0 or my_cover(fp) >= threat(fp):
            dest = fp
        else:
            cand = [fp] + [n for _, n in brain.nbrs[fp]]
            dest = min(cand, key=lambda n: (danger(n), brain.d(n, tp)))
        fplans.append([fp, dest, tp])
        f_dest[dest] = f_dest.get(dest, 0) + 1
        f_target_of[len(f_target_of)] = tp
    fplans, hard_coverage = coupled_plan(brain,fplans,my,en,bmap,ereach_raw,
                                         lambda b:value(brain,b,turn),check_time)
    f_dest={}
    for src,dest,target in fplans:f_dest[dest]=f_dest.get(dest,0)+1
    wlist = []
    for p, c in my['W'].items():
        wlist += [p] * c
    w_used = [False] * len(wlist)
    w_dest = {}
    w_assignment = [None] * len(wlist)

    def commit(i, dest):
        w_assignment[i] = dest
        w_used[i] = True
        add_move(wlist[i], 'W', dest)
        w_dest[dest] = w_dest.get(dest, 0) + 1

    reachable={p:[i for i,q in enumerate(wlist) if brain.d(q,p)<=1] for p in brain.nbrs}

    def release(i):
        old=w_assignment[i];src=wlist[i]
        if src!=old:
            direction=next(d for d,p in brain.nbrs[src] if p==old)
            key=src,'W',direction
            moves[key]-=1
            if not moves[key]:del moves[key]
        w_dest[old]-=1
        w_assignment[i]=None;w_used[i]=False

    def augment(cell,seen):
        if cell in seen:return False
        seen.add(cell)
        for i in reachable[cell]:
            if not w_used[i]:commit(i,cell);return True
        for i in reachable[cell]:
            old=w_assignment[i]
            if old is None or old==cell:continue
            if augment(old,seen):
                release(i);commit(i,cell);return True
        return False

    def arrive_need(cell,need,allow_partial=False):
        if w_dest.get(cell,0)>=need:return True
        saved=(list(w_used),list(w_assignment),dict(w_dest),dict(moves)) if not allow_partial else None
        while w_dest.get(cell,0)<need:
            if augment(cell,set()):continue
            if saved is not None:
                w_used[:],w_assignment[:]=saved[:2]
                w_dest.clear();w_dest.update(saved[2]);moves.clear();moves.update(saved[3])
            return False
        return True

    def approach(cell, need, radius=4):
        """cell 쪽으로 가까운 전투병을 need 명 이동."""
        cand = [i for i, p in enumerate(wlist) if not w_used[i] and 1 < brain.d(p, cell) <= radius]
        cand.sort(key=lambda i: brain.d(wlist[i], cell))
        for i in cand[:need]:
            p = wlist[i]
            dcur = brain.d(p, cell)
            steps = [n for _, n in brain.nbrs[p] if brain.d(n, cell) == dcur - 1]
            if steps:
                commit(i, min(steps, key=lambda n: (ereach.get(n, 0), n)))
    for cell,amount in hard_coverage.items():
        if amount:arrive_need(cell,amount)
    demands = []
    for c, cnt in f_dest.items():
        t = threat(c)
        if t > 0:
            b = bmap.get(c)
            pr = 10 + (value(brain, b, turn) if b else 0) + cnt
            demands.append((pr, 'escort', c, t + (1 if en['F'].get(c,0) else 0)))
    conv_n = CONVOY_N if not outnumbered else max(1, CONVOY_N // 2)
    if conv_n > 0 and turn > 6:
        for c, cnt in f_dest.items():
            b = bmap.get(c)
            if b is not None and b['owner'] == me:
                continue
            extra = 0
            urgency = 0
            demands.append((CONVOY_PR + cnt + urgency, 'convoy', c, max(conv_n * cnt, extra)))
    for c, cnt in f_dest.items():
        if threat(c) == 0 and ereach2.get(c, 0) > 0:
            demands.append((5 + cnt, 'escort2', c, min(ereach2[c] + 1, 15)))
    for b in owned:
        p = (b['x'], b['y'])
        near1 = eflag1.get(p, 0) > 0
        near2 = any((brain.d(q, p) <= 2 for q in en['F']))
        if near1:
            demands.append((8 + value(brain, b, turn), 'defend', p, threat(p) + 1))
        elif near2:
            demands.append((4 + value(brain, b, turn), 'defend2', p, max(1, threat(p) + 1)))
    for b in owned:
        if b['type'] not in ('HALL', 'ENG', 'HOSPITAL') and (not leading):
            continue
        p = (b['x'], b['y'])
        gr = ENG_R if b['type'] == 'ENG' else GARRISON_R
        thr = 0
        for q, c in en['W'].items():
            if brain.d(q, p) <= gr:
                thr += c
        if any((brain.d(sp, p) <= gr for sp in e_spawn_pts)):
            thr += e_capW
        ef = any((brain.d(q, p) <= gr + 2 for q in en['F']))
        early_thr = ereach2.get(p, 0) if b['type'] in ('HALL', 'ENG') else 0
        if thr == 0 and early_thr == 0 and (not ef):
            if MIN_GAR and b['type'] in ('HALL', 'ENG') and (turn > 6):
                demands.append((3 + value(brain, b, turn), 'garrison', p, MIN_GAR))
            continue
        need = min(max(thr, early_thr) + 1, 25)
        boost = GARRISON_BOOST if outnumbered else 0.0
        demands.append((6 + value(brain, b, turn) + (ENG_PR if b['type'] == 'ENG' else 0) + boost, 'garrison', p, need))
    fp = brain.fortress
    fb = bmap.get(fp)
    if pf_pred or pw_pred:
        pf, pw = (pf_pred, pw_pred)
        for c, cnt in pf.items():
            if c not in brain.nbrs:
                continue
            b = bmap.get(c)
            pr = PRED_PR + cnt + (value(brain, b, turn) if b is not None else 0)
            demands.append((pr, 'phunt', c, pw.get(c, 0) + 1))
    for q, cnt in en['F'].items():
        b = bmap.get(q)
        if b is not None:
            pr = 9 + value(brain, b, turn) + cnt
        else:
            pr = 5 + cnt
        if outnumbered:
            pr *= 0.6
        demands.append((pr, 'hunt', q, ereach.get(q, 0) + 1))
        if b is None:
            tg = [(bb['x'], bb['y']) for bb in view.buildings if bb['owner'] != op]
            if tg:
                near = min(tg, key=lambda t: brain.d(q, t))
                dq = brain.d(q, near)
                nxt = [n for _, n in brain.nbrs[q] if brain.d(n, near) == dq - 1]
                for n in nxt:
                    demands.append((pr - 0.5 * len(nxt), 'hunt', n, ereach.get(n, 0) + 1))
                if dq <= 3:
                    demands.append((pr - 1.5, 'hunt', near, ereach.get(near, 0) + 1))

    def intercept(cell, need, maxd):
        have = w_dest.get(cell, 0)
        if have >= need:
            return
        cand = [i for i, p in enumerate(wlist) if not w_used[i] and brain.d(p, cell) <= maxd]
        cand.sort(key=lambda i: brain.d(wlist[i], cell))
        for i in cand[:need - have]:
            p = wlist[i]
            dcur = brain.d(p, cell)
            if dcur == 0:
                w_used[i] = True
                w_dest[p] = w_dest.get(p, 0) + 1
                continue
            steps = [n for _, n in brain.nbrs[p] if brain.d(n, cell) == dcur - 1]
            commit(i, min(steps, key=lambda n: (ereach.get(n, 0), n)))
    demands.sort(key=lambda d: -d[0])
    deferred_auction = []
    for dm in demands:
        check_time(brain.deadline)
        pr, kind, cell, need = dm[:4]
        if kind == 'intercept':
            intercept(cell, need, dm[4])
            continue
        defend_kind = kind in ('defend', 'defend2', 'garrison', 'police')
        partial = defend_kind
        ok = arrive_need(cell, need, allow_partial=partial)
        if kind == 'phunt':
            continue
        if not ok and kind == 'convoy':
            approach(cell, need - w_dest.get(cell, 0), radius=CONVOY_R)
            continue
        if not ok and kind in ('garrison', 'police'):
            approach(cell, need - w_dest.get(cell, 0), radius=GAR_RADIUS)
        elif not ok and kind in ('hunt', 'escort', 'escort2', 'defend', 'defend2'):
            approach(cell, need - w_dest.get(cell, 0), radius=4 if kind != 'hunt' else 5)
    n_w_now = len(wlist)
    if turn > 20 and n_w_now >= SIEGE_MULT * n_ew + SIEGE_ADD:
        e_next = min(CFG['resource']['resource_cap'], view.opp_resource + 12)
        spawn_w = e_next // ewc
        cells = []
        for sp in e_spawn_pts:
            for _, n in brain.nbrs.get(sp, []):
                cells.append(n)
        for c in cells:
            need = spawn_w + sum((en['W'].get(n, 0) for n in brain.n1(c))) + 1
            have = w_dest.get(c, 0)
            if have >= need:
                continue
            cand = [i for i, p in enumerate(wlist) if not w_used[i]]
            cand.sort(key=lambda i: brain.d(wlist[i], c))
            for i in cand[:need - have]:
                p = wlist[i]
                dcur = brain.d(p, c)
                if dcur >= INF:
                    continue
                if dcur == 0:
                    w_used[i] = True
                    w_dest[p] = w_dest.get(p, 0) + 1
                    continue
                steps = [n for _, n in brain.nbrs[p] if brain.d(n, c) == dcur - 1]
                commit(i, min(steps, key=lambda n: (ereach.get(n, 0), n)))
    free = [i for i in range(len(wlist)) if not w_used[i]]
    if free:
        cands = []
        for q, cnt in en['F'].items():
            cands.append((q, 3.0 + cnt))
        for b in view.buildings:
            p = (b['x'], b['y'])
            if b['owner'] != me:
                vv = value(brain, b, turn) + (1.0 if b['owner'] == op else 0.0)
                if strike and b['owner'] == op and (b['type'] == 'ENG'):
                    vv *= STRIKE_RALLY
                cands.append((p, vv))
            elif ereach.get(p, 0) > 0 or any((brain.d(q, p) <= 3 for q in en['F'])):
                cands.append((p, value(brain, b, turn) * 0.8))
        if outnumbered:
            for b in owned:
                if b['type'] in ('HALL', 'ENG', 'HOSPITAL'):
                    cands.append(((b['x'], b['y']), value(brain, b, turn) * 1.2))
        if not cands:
            cands = [(brain.obase, 1.0)]
        best = None
        for p, v in cands:
            avgd = sum((brain.d(wlist[i], p) for i in free)) / len(free)
            sc = v / (avgd + 3)
            if best is None or sc > best[0]:
                best = (sc, p)
        rally0 = best[1]
        my_st = [(b['x'], b['y']) for b in owned if b['type'] == 'STATION']
        if len(my_st) >= 2:
            s_to = min(my_st, key=lambda st: brain.d(st, rally0))
            best_from = None
            for st in my_st:
                if st == s_to:
                    continue
                idxs = [i for i in free if wlist[i] == st and (not w_used[i])]
                gain = brain.d(st, rally0) - brain.d(s_to, rally0)
                if idxs and gain >= TELE_GAIN:
                    key = (min(5, len(idxs)) * gain, st)
                    if best_from is None or key > best_from[0]:
                        best_from = (key, st, idxs[:5])
            if best_from is not None:
                _, st, idxs = best_from
                for i in idxs:
                    w_used[i] = True
                    w_dest[s_to] = w_dest.get(s_to, 0) + 1
                cmds.append(tele(st[0], st[1], 'W', len(idxs), s_to[0], s_to[1]))
        rally_load = {p: w_dest.get(p, 0) for p, _ in cands}
        for i in free:
            check_time(brain.deadline)
            if w_used[i]:
                continue
            p = wlist[i]
            rally = max(cands, key=lambda pv: pv[1] / (brain.d(p, pv[0]) + RALLY_D))[0] if not outnumbered else rally0
            if not False:

                def marginal(pv):
                    target, utility = pv
                    need = max(3, min(18, ereach2.get(target, 0) + 2))
                    load = rally_load.get(target, 0)
                    return utility / (brain.d(p, target) + RALLY_D) / (1.0 + (load / need) ** 2)
                rally = max(cands, key=marginal)[0]
                rally_load[rally] = rally_load.get(rally, 0) + 1
            dcur = brain.d(p, rally)
            if dcur == 0 or dcur >= INF:
                w_used[i] = True
                w_dest[p] = w_dest.get(p, 0) + 1
                continue
            steps = [n for _, n in brain.nbrs[p] if brain.d(n, rally) == dcur - 1]
            commit(i, min(steps, key=lambda n: (ereach.get(n, 0), n)))

    def safe_final(c):
        t = threat(c)
        return t == 0 or w_dest.get(c, 0) >= t
    if turn == TOTAL_TURNS:
        spent = sum((cnt * (FC if kind == 'F' else wc) for kind, cnt, _ in spawned))
        funds = min(CFG['resource']['resource_cap'], view.my_resource - spent + income)
        final_flags(brain, view, fplans, bmap, en, ereach_raw, w_dest, cap_cost, funds, fix=True)
    f_dest = {}
    new_mem = {}
    for plan in fplans:
        src, dest, tp = plan
        if not turn == TOTAL_TURNS and (not safe_final(dest)):
            cand = [src] + [n for _, n in brain.nbrs[src]]
            safe = [c for c in cand if safe_final(c)]
            if safe:
                if tp is not None:
                    dest = min(safe, key=lambda c: (brain.d(c, tp), c != src))
                else:
                    dest = min(safe, key=lambda c: (c in bmap, c != src))
            else:
                dest = min(cand, key=lambda c: (threat(c) - w_dest.get(c, 0), c != src))
            plan[1] = dest
        add_move(src, 'F', dest)
        f_dest[dest] = f_dest.get(dest, 0) + 1
        if tp is not None and dest != tp:
            new_mem.setdefault(dest, []).append(tp)
    brain.fmem = new_mem
    for (src, kind, dname), cnt in sorted(moves.items()):
        cmds.append(move(src[0], src[1], kind, cnt, dname))
    pri = [c for c in f_dest if c in bmap and bmap[c]['owner'] != me]
    if pri:
        items = [(c, cap_cost(bmap[c]), value(brain, bmap[c], turn)) for c in pri]
        if len(items) <= 20:
            spent = sum((cnt * (FC if kind == 'F' else wc) for kind, cnt, pos in spawned))
            cap_budget = max(0, min(CFG['resource']['resource_cap'], view.my_resource - spent + income))
            total_cost = sum((int(cost) for _, cost, _ in items))
            if total_cost > cap_budget:
                check_time(brain.deadline)
                B = int(cap_budget)
                dp = [0.0] * (B + 1)
                took = [[False] * (B + 1) for _ in items]
                for idx, (_, cost, val) in enumerate(items):
                    cost = int(cost)
                    for b in range(B, cost - 1, -1):
                        if dp[b - cost] + val > dp[b]:
                            dp[b] = dp[b - cost] + val
                            took[idx][b] = True
                chosen = set()
                b = B
                for idx in range(len(items) - 1, -1, -1):
                    if took[idx][b]:
                        chosen.add(items[idx][0])
                        b -= int(items[idx][1])
                rest = [c for c, _, _ in items if c not in chosen]
                pri = sorted(chosen, key=lambda c: -value(brain, bmap[c], turn)) + sorted(rest, key=lambda c: -value(brain, bmap[c], turn))
            else:
                pri.sort(key=lambda c: -value(brain, bmap[c], turn))
        else:
            pri.sort(key=lambda c: -value(brain, bmap[c], turn))
        cmds.append(priority(pri))
    return cmds
if __name__ == '__main__':
    run(decide)
