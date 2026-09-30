"""테스트용 상대 rival_mimicA (제출용 아님): 패배 경기 상대를 흉내 낸 모방 봇(패배 경기 재현 확인).
전투병을 소규모(NET_K명) 그룹으로 넓게 펼쳐 그물처럼 배치.
my_bot3 — 깃발 대항전 전략 봇 (my_bot2 + 경제 중심 개선 + 2턴 위험 예측).

핵심 아이디어
 1. 자원은 거의 전부 쓴다 (점령 비용은 이번 턴 수입으로 낼 수 있으므로 예약을 최소화).
 2. 깃발병: 가치/거리 기준으로 건물마다 1명씩 배정. 적 전투병 위협이 있는 칸은 피하거나 호위를 붙인다.
 3. 전투병: ①깃발병 호위 ②내 건물 방어 ③적 깃발병 사냥 ④남는 병력은 한 지점으로 집결.
 4. 점령 순서는 PRIORITY 로 명시 (점수 높은 건물부터).
my_bot2 개선점
 5. 전투병 배치를 확정한 뒤 깃발병 이동을 다시 검사해, 호위가 부족한 칸이면 안전한 칸으로 바꾼다.
 6. 적 깃발병의 다음 이동 후보 칸 전부 + 목표 건물(매복)에 전투병을 보낸다.
 7. 전투병이 압도적이면 적 본진·병원 주변을 봉쇄해 즉시 승리를 노린다.
 8. 남는 전투병은 각자 가까운 고가치 지점으로 흩어져 집결한다.
 9. 초반 깃발병 8명, 학생회관 가중치 상향, 상대 소유 건물 가중치 하향 (시뮬레이션 튜닝).
my_bot3 개선점 (공식 리플레이 15경기 분석 기반)
 10. 건물 가치를 '점수 + 경제 가치'로 계산: 학생회관(+2/턴), 첫 공학관(전투병 1.5배)을
     전투병 생산량으로 환산하고, 상대의 유일한 공학관/학생회관을 뺏는 효과도 더한다.
 11. 초반 60턴은 내 본진에 가까운(지키기 쉬운) 건물을 우선한다.
 12. 학생회관·공학관·병원에 상시 수비대(3칸 내 적 전투병 + 1)를 둔다.
 13. 깃발병 목표를 턴 간에 기억해 목표가 흔들리지 않게 한다.
 14. 종반: 남은 턴 안에 점령이 끝날 수 없는 목표는 버리고, 마지막 턴에는 인접 건물로 무조건 진입.
 15. 역 순간이동(TELE): 적의 순간이동 위협을 위협 지도에 반영하고, 내 역 2개 이상이면 전투병을 전선 쪽 역으로 이동.
 17. 학생회관·공학관에 평소에도 최소 1명 수비대 (가까운 적 깃발병 기습 방지).
 18. 2턴 안에 올 수 있는 적 전투병까지 계산해 깃발병 경로를 고르고, 위험이 닿기 전에 전투병이 미리 호위.
 19. 경제 가중치 12, 중반 깃발병 최대 4명, 봉쇄 기준 상향, 집결 분산 완화.
 16. 파라미터 탐색(실제 맵 + 무작위 맵) 결과: 초반 깃발병 4명, 경제 가중치 9 등.
제출 규정 준수: 모든 값은 소스에 상수로 포함, 실행 중 파일 읽기·네트워크 접근 없음.
표준 라이브러리만 사용한다.
"""
from __future__ import annotations

import sys
from collections import deque

from protocol import BALANCE, DIRS, spawn, move, priority, tele, run

N = 15
INF = 10 ** 6
CFG = BALANCE
FC = CFG["units"]["F"]["cost"]
SC = CFG["units"]["S"]["cost"]
TOTAL_TURNS = CFG["total_turns"]

# 건물 기능 가치(점수 환산 가중치, 게임 진행에 따라 감쇠)
FUNC_BONUS = {
    "HALL": 1.0,
    "ENG": 0.5,
    "LIBRARY": 0.8,
    "HOSPITAL": 1.2,
    "WATCH": 0.3,
    "STATION": 0.2,
    "DEPOT": 0.0,   # 보급소는 별도 처리(미수령 시 큰 보너스)
    "PLAZA": 0.0,
}

_BRAINS = {}
SIEGE = True
AMBUSH = True
RALLY_SPLIT = True
SIEGE_MULT = 1.5
SIEGE_ADD = 30
ECON_K = 12.0
HOME_BIAS = 0.04
HOME_TURNS = 60
GARRISON = True
ENDGAME = True
INTERCEPT = False
MIN_GAR = 1
MIRROR_Y = True
NET_K = 4
NET_OWN = 0.4
RES_KEEP = 10
CAUT = True
MID_F_HI = 6
MID_F_LO = 3
RALLY_D = 5
INTERCEPT_R = 6
INTERCEPT_N = 2
TELE_ON = True
TELE_GAIN = 4
EARLY_F = 4
EARLY_T = 8
EO_MULT = 0.3
STICK = 1.5
GARRISON_R = 3


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
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < N and 0 <= ny < N and self.passable[ny][nx]:
                        lst.append((d, (nx, ny)))
                self.nbrs[(x, y)] = lst
        # 모든 칸 쌍 거리 (BFS 225회)
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
        self.bpos = {(b["x"], b["y"]): b for b in init.buildings}
        self.known = {}          # 좌표 -> 실제 점수 (대칭 추론 포함)
        self.depot_got = set()   # 내가 보너스를 받은 보급소 좌표
        self.fmem = {}           # 지난 턴 깃발병 도착 칸 -> [목표] (목표 유지용)

    def d(self, a, b):
        return self.dist[a][idx(*b)] if a in self.dist else INF

    def n1(self, c):
        """c 와 거리 1 이내 칸 (자기 자신 포함)."""
        return [c] + [n for _, n in self.nbrs.get(c, [])]

    def region(self, x):
        if x <= 4:
            return "sinchon"
        if x >= 10:
            return "anam"
        return "center"


def est_score(brain, b):
    p = (b["x"], b["y"])
    if p in brain.known:
        return brain.known[p]
    if b["type"] == "PLAZA":
        return 3
    return 3.0 if brain.region(b["x"]) == "center" else 1.5


def econ_wpt(brain, b):
    """이 건물을 내가 가지면(상대에게서 뺏으면) 늘어나는 '턴당 전투병 생산량 차이'."""
    c = brain.ctx
    t = b["type"]
    mine = b["owner"] == brain.me
    theirs = b["owner"] == brain.op
    g = 0.0
    if t == "HALL":
        g += 2.0 / c["wc"]
        if theirs:
            g += 2.0 / c["ewc"]
    elif t == "ENG":
        k = c["my_engs"] - (1 if mine else 0)   # 이 건물을 제외한 내 공학관 수
        if k == 0:
            g += c["income"] / 2.0 - c["income"] / 3.0
        if theirs and c["e_engs"] == 1:
            g += c["e_income"] / 2.0 - c["e_income"] / 3.0
    return g


def value(brain, b, turn):
    """건물 가치 = (예상) 점수 + 경제 가치(전투병 생산량 환산) + 기능 보너스."""
    v = est_score(brain, b)
    left = max(0.0, (TOTAL_TURNS - turn) / TOTAL_TURNS)
    v += FUNC_BONUS.get(b["type"], 0) * left
    v += ECON_K * econ_wpt(brain, b) * left
    if b["type"] == "DEPOT" and (b["x"], b["y"]) not in brain.depot_got:
        v += 2.5
    return v


_MIRROR = {}
_FLIP = {"U": "D", "D": "U", "L": "R", "R": "L"}


def _m(x, y):
    return N - 1 - x, N - 1 - y


def _mirror_init(init):
    """연세(Y) 진영일 때 판을 180도 돌려, 고려(K) 진영과 똑같은 관점으로 판단하게 한다."""
    from campus_bot import Init
    terrain = [[init.terrain[N - 1 - y][N - 1 - x] for x in range(N)] for y in range(N)]
    buildings = [dict(b, x=_m(b["x"], b["y"])[0], y=_m(b["x"], b["y"])[1]) for b in init.buildings]
    bases = {t: _m(*p) for t, p in init.bases.items()}
    return Init(init.width, init.height, init.team, terrain, buildings, bases)


def _mirror_view(view, minit):
    from campus_bot import View
    units = [dict(u, x=_m(u["x"], u["y"])[0], y=_m(u["x"], u["y"])[1]) for u in view.units]
    buildings = [dict(b, x=_m(b["x"], b["y"])[0], y=_m(b["x"], b["y"])[1]) for b in view.buildings]
    return View(view.turn, minit, view.my_resource, view.opp_resource, units, buildings)


def _unmirror_cmd(c):
    t = c.split()
    try:
        if t[0] == "SPAWN" and len(t) == 5:
            x, y = _m(int(t[3]), int(t[4]))
            return " ".join(t[:3] + [str(x), str(y)])
        if t[0] == "MOVE":
            x, y = _m(int(t[1]), int(t[2]))
            return " ".join([t[0], str(x), str(y), t[3], t[4], _FLIP[t[5]]])
        if t[0] == "MOVE2":
            x, y = _m(int(t[1]), int(t[2]))
            return " ".join([t[0], str(x), str(y), t[3], t[4], _FLIP[t[5]], _FLIP[t[6]]])
        if t[0] == "TELE":
            x, y = _m(int(t[1]), int(t[2]))
            tx, ty = _m(int(t[5]), int(t[6]))
            return " ".join([t[0], str(x), str(y), t[3], t[4], str(tx), str(ty)])
        if t[0] == "PRIORITY":
            v = list(map(int, t[1:]))
            out = []
            for i in range(0, len(v) - 1, 2):
                out += list(_m(v[i], v[i + 1]))
            return " ".join(["PRIORITY"] + [str(a) for a in out])
    except (ValueError, IndexError, KeyError):
        return c
    return c


def decide(view, init):
    try:
        if MIRROR_Y and init.team == "Y":
            minit = _MIRROR.get(id(init))
            if minit is None:
                minit = _MIRROR[id(init)] = _mirror_init(init)
            brain = _BRAINS.get(id(minit))
            if brain is None:
                brain = _BRAINS[id(minit)] = Brain(minit)
            return [_unmirror_cmd(c) for c in _decide(brain, _mirror_view(view, minit))]
        brain = _BRAINS.get(id(init))
        if brain is None:
            brain = _BRAINS[id(init)] = Brain(init)
        return _decide(brain, view)
    except Exception as e:  # 어떤 예외도 몰수패로 이어지지 않도록
        log("ERR", repr(e))
        return []


def _decide(brain, view):
    me, op = brain.me, brain.op
    turn = view.turn
    cmds = []

    # ------------------------------------------------ 상태 정리
    for b in view.buildings:
        p = (b["x"], b["y"])
        if b["score"] >= 0:
            brain.known[p] = b["score"]
            brain.known[(14 - p[0], 14 - p[1])] = b["score"]
        if b["type"] == "DEPOT" and b["owner"] == me:
            brain.depot_got.add(p)
    bmap = {(b["x"], b["y"]): b for b in view.buildings}

    my = {"F": {}, "W": {}, "S": {}}
    en = {"F": {}, "W": {}, "S": {}}
    for u in view.units:
        tgt = my if u["team"] == me else en
        p = (u["x"], u["y"])
        tgt[u["kind"]][p] = tgt[u["kind"]].get(p, 0) + u["count"]

    owned = [b for b in view.buildings if b["owner"] == me]
    eowned = [b for b in view.buildings if b["owner"] == op]
    my_halls = sum(b["type"] == "HALL" for b in owned)
    my_engs = sum(b["type"] == "ENG" for b in owned)
    my_lib = any(b["type"] == "LIBRARY" for b in owned)
    e_engs = sum(b["type"] == "ENG" for b in eowned)
    wc = max(CFG["buildings"]["eng_cost_floor"], CFG["units"]["W"]["cost"] - my_engs)
    ewc = max(CFG["buildings"]["eng_cost_floor"], CFG["units"]["W"]["cost"] - e_engs)
    income = CFG["resource"]["base_income"] + CFG["resource"]["hall_bonus"] * my_halls
    e_halls = sum(b["type"] == "HALL" for b in eowned)
    e_income = CFG["resource"]["base_income"] + CFG["resource"]["hall_bonus"] * e_halls
    brain.ctx = {"wc": wc, "ewc": ewc, "my_engs": my_engs, "e_engs": e_engs,
                 "income": income, "e_income": e_income}

    def cap_cost(b):
        c = CFG["capture"]["capture_cost"] * (CFG["capture"]["plaza_multiplier"] if b["type"] == "PLAZA" else 1)
        if my_lib:
            c = max(CFG["capture"]["min_capture_cost"], c - CFG["buildings"]["library_discount"])
        return c

    # ------------------------------------------------ 적 위협 지도
    e_spawn_pts = [brain.obase] + [(b["x"], b["y"]) for b in eowned if b["type"] == "HOSPITAL"]
    e_capW = view.opp_resource // ewc
    e_capF = view.opp_resource // FC

    ereach = {}   # 다음 턴 그 칸에 올 수 있는 적 전투병 최대 수
    eflag1 = {}   # 다음 턴 그 칸에 올 수 있는 적 깃발병 수
    for c in brain.nbrs:
        s = 0
        f = 0
        for n in brain.n1(c):
            s += en["W"].get(n, 0)
            f += en["F"].get(n, 0)
        if any(sp in brain.n1(c) for sp in e_spawn_pts):
            s += e_capW
            f += e_capF
        ereach[c] = s
        eflag1[c] = f
    # 2턴 내 위협(깃발병 경로 선택·사전 호위용)
    ereach2 = {}
    if CAUT:
        ew_items = list(en["W"].items())
        for c in brain.nbrs:
            s2 = sum(cnt for q, cnt in ew_items if brain.d(q, c) <= 2)
            if any(brain.d(sp, c) <= 2 for sp in e_spawn_pts):
                s2 += e_capW
            ereach2[c] = s2
    # 적 순간이동(TELE) 위협: 적 역이 2개 이상이면 다른 역의 병력 최대 5명이 역으로 올 수 있다
    e_st = [(b["x"], b["y"]) for b in eowned if b["type"] == "STATION"]
    if len(e_st) >= 2:
        for st in e_st:
            others_w = max((en["W"].get(o, 0) for o in e_st if o != st), default=0)
            others_f = max((en["F"].get(o, 0) for o in e_st if o != st), default=0)
            ereach[st] = ereach.get(st, 0) + min(5, others_w)
            eflag1[st] = eflag1.get(st, 0) + min(5, others_f)

    # ------------------------------------------------ 생산 계획
    open_targets = [b for b in view.buildings if b["owner"] != me]
    n_f = sum(my["F"].values())
    n_w = sum(my["W"].values())
    n_ew = sum(en["W"].values())

    # 이번 턴 점령 가능성이 있는 건물 비용 (수입으로 못 메우는 만큼만 예약)
    need_cap = 0
    seen_b = set()
    for p in my["F"]:
        for n in brain.n1(p):
            b = bmap.get(n)
            if b and b["owner"] != me and n not in seen_b:
                seen_b.add(n)
                need_cap += cap_cost(b)
    reserve = max(0, need_cap - income)
    budget = max(0, view.my_resource - reserve - (RES_KEEP if turn > 10 else 0))

    spawn_pts = [brain.base] + [(b["x"], b["y"]) for b in owned if b["type"] == "HOSPITAL"]

    def best_spawn(targets):
        if not targets:
            return brain.base
        return min(spawn_pts, key=lambda s: (min(brain.d(s, t) for t in targets), s != brain.base))

    # 원하는 깃발병 수
    if turn >= TOTAL_TURNS - 6:
        want_f = 0
    elif turn <= EARLY_T:
        want_f = min(len(open_targets), EARLY_F)
    else:
        want_f = min(len(open_targets), MID_F_HI if n_w >= 0.75 * n_ew else MID_F_LO)
        if n_w >= n_ew + 6:
            want_f = min(len(open_targets), 5)

    spawned = []  # (kind, count, pos)
    make_f = 0
    if n_f < want_f and budget >= FC:
        # 전투병이 너무 부족하면(적 전투병 대비) 깃발병 생산을 한 명으로 제한
        lim = want_f - n_f
        if turn > 12 and n_w < n_ew:
            lim = min(lim, 1)
        make_f = min(lim, budget // FC)
    if make_f:
        fpos = best_spawn([(b["x"], b["y"]) for b in open_targets])
        budget -= make_f * FC
        spawned.append(("F", make_f, fpos))
    make_w = budget // wc
    # 첫 턴은 자원 10으로 깃발병 2명이 최선
    if make_w:
        front = [p for p in en["F"]] + [(b["x"], b["y"]) for b in open_targets]
        wpos = best_spawn(front)
        spawned.append(("W", make_w, wpos))
    for kind, cnt, pos in spawned:
        if pos == brain.base:
            cmds.append(spawn(kind, cnt))
        else:
            cmds.append(spawn(kind, cnt, pos[0], pos[1]))
        my[kind][pos] = my[kind].get(pos, 0) + cnt

    # 내 전투병이 다음 턴 도달 가능한 수
    def my_cover(c):
        return sum(my["W"].get(n, 0) for n in brain.n1(c))

    # ------------------------------------------------ 깃발병 계획
    moves = {}  # (from, kind, dir) -> count
    f_dest = {}  # 도착 칸 -> 수
    f_target_of = {}

    def add_move(src, kind, dst, cnt=1):
        if src == dst:
            return
        for dname, n in brain.nbrs[src]:
            if n == dst:
                k = (src, kind, dname)
                moves[k] = moves.get(k, 0) + cnt
                return

    def danger(c):
        return ereach.get(c, 0) - my_cover(c)

    flags = []
    for p, c in my["F"].items():
        flags += [p] * c

    claimed = set()
    free_flags = []
    fplans = []  # [src, dest, target]
    for p in flags:
        b = bmap.get(p)
        if b and b["owner"] != me and p not in claimed:
            claimed.add(p)
            f_target_of_idx = len(f_target_of)
            f_target_of[f_target_of_idx] = p
            # 위험하면 후퇴, 아니면 점령을 위해 머문다
            if ereach.get(p, 0) > 0 and danger(p) >= 0 and ereach[p] >= my_cover(p):
                # 호위가 붙을 수 있는지 나중에 전투병 단계에서 확인. 일단 머무름.
                pass
            f_dest[p] = f_dest.get(p, 0) + 1
            fplans.append([p, p, p])
        else:
            free_flags.append(p)

    def target_eff(fp, b):
        tp = (b["x"], b["y"])
        dd = brain.d(fp, tp)
        if dd >= INF:
            return -1
        v = value(brain, b, turn)
        tl = TOTAL_TURNS - turn
        if ENDGAME and tl < 12:
            # 남은 턴 안에 점령(또는 중립화)이 끝날 수 없는 목표는 무의미
            if dd + (1 if b["owner"] == op else 0) > tl + 1 and not (b["owner"] == op and dd <= tl):
                return -1
        if b["owner"] == op:
            v *= EO_MULT  # 2턴 필요
        # 적 전투병이 버티는 건물은 불리
        ew_here = en["W"].get(tp, 0)
        mw_near = sum(my["W"].get(n, 0) for n in brain.n1(tp))
        if ew_here > mw_near:
            v *= 0.3
        # 적 깃발병이 이미 있고 전투병 지원이 없다면 경합만 된다
        if en["F"].get(tp, 0) and mw_near == 0:
            v *= 0.5
        # 적 본진 쪽으로 너무 깊이 들어가는 건 위험
        if brain.d(brain.obase, tp) < brain.d(brain.base, tp) and n_w <= n_ew:
            v *= 0.7
        # 초반에는 내 본진 쪽(지키기 쉬운) 건물부터
        if turn <= HOME_TURNS:
            safety = brain.d(brain.obase, tp) - brain.d(brain.base, tp)
            v *= max(0.3, 1.0 + HOME_BIAS * max(-8, min(8, safety)))
        return v / (dd + 2)

    remaining = [b for b in open_targets if (b["x"], b["y"]) not in claimed]
    pairs = []
    prev_t = {}
    for i, fp in enumerate(free_flags):
        lst = brain.fmem.get(fp)
        if lst:
            prev_t[i] = lst.pop()
    for i, fp in enumerate(free_flags):
        for b in remaining:
            e = target_eff(fp, b)
            if e > 0:
                if prev_t.get(i) == (b["x"], b["y"]):
                    e *= STICK
                pairs.append((e, i, (b["x"], b["y"])))
    pairs.sort(reverse=True)
    assign = {}
    used_t = set()
    for e, i, tp in pairs:
        if i in assign or tp in used_t:
            continue
        assign[i] = tp
        used_t.add(tp)

    for i, fp in enumerate(free_flags):
        tp = assign.get(i)
        if tp is None:
            # 할 일이 없으면 내 건물 위에서 벗어나 안전한 곳에서 대기
            b = bmap.get(fp)
            dest = fp
            if b and b["owner"] == me and ereach.get(fp, 0) > 0:
                opts = [n for _, n in brain.nbrs[fp] if n not in bmap]
                if opts:
                    dest = min(opts, key=lambda n: danger(n))
            fplans.append([fp, dest, None])
            f_dest[dest] = f_dest.get(dest, 0) + 1
            continue
        dcur = brain.d(fp, tp)
        steps = [n for _, n in brain.nbrs[fp] if brain.d(n, tp) == dcur - 1]
        safe_steps = [n for n in steps if ereach.get(n, 0) == 0 or my_cover(n) > ereach[n]]
        if safe_steps:
            dest = min(safe_steps, key=lambda n: (danger(n), ereach2.get(n, 0), n))
        elif ereach.get(fp, 0) == 0 or my_cover(fp) > ereach[fp]:
            dest = fp  # 제자리 대기(호위를 기다림)
        else:
            cand = [fp] + [n for _, n in brain.nbrs[fp]]
            dest = min(cand, key=lambda n: (danger(n), brain.d(n, tp)))
        fplans.append([fp, dest, tp])
        f_dest[dest] = f_dest.get(dest, 0) + 1
        f_target_of[len(f_target_of)] = tp

    # ------------------------------------------------ 전투병 계획
    wlist = []
    for p, c in my["W"].items():
        wlist += [p] * c
    w_used = [False] * len(wlist)
    w_dest = {}

    def commit(i, dest):
        w_used[i] = True
        add_move(wlist[i], "W", dest)
        w_dest[dest] = w_dest.get(dest, 0) + 1

    def arrive_need(cell, need, allow_partial=False):
        """cell 에 이번 턴 도착 가능한 전투병을 need 명 배정. 성공 여부 반환."""
        have = w_dest.get(cell, 0)
        if have >= need:
            return True
        cand = [i for i, p in enumerate(wlist) if not w_used[i] and brain.d(p, cell) <= 1]
        cand.sort(key=lambda i: brain.d(wlist[i], cell))
        if have + len(cand) < need and not allow_partial:
            return False
        for i in cand[:max(0, need - have)]:
            commit(i, cell)
        return w_dest.get(cell, 0) >= need

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

    demands = []  # (priority, kind, cell, need)
    # D1 호위: 깃발병 도착 칸에 적 전투병이 올 수 있으면
    for c, cnt in f_dest.items():
        t = ereach.get(c, 0)
        if t > 0:
            b = bmap.get(c)
            pr = 10 + (value(brain, b, turn) if b else 0) + cnt
            demands.append((pr, "escort", c, t + 1))
    # D1.5 사전 호위: 다음 다음 턴 위협이 있는 깃발병 도착 칸
    if CAUT:
        for c, cnt in f_dest.items():
            if ereach.get(c, 0) == 0 and ereach2.get(c, 0) > 0:
                demands.append((5 + cnt, "escort2", c, min(ereach2[c] + 1, 15)))
    # D2 방어: 적 깃발병이 1~2턴 안에 올 수 있는 내 건물
    for b in owned:
        p = (b["x"], b["y"])
        near1 = eflag1.get(p, 0) > 0
        near2 = any(brain.d(q, p) <= 2 for q in en["F"])
        if near1:
            demands.append((8 + value(brain, b, turn), "defend", p, ereach.get(p, 0) + 1))
        elif near2:
            demands.append((4 + value(brain, b, turn), "defend2", p, max(1, ereach.get(p, 0) + 1)))
    # D2.5 상시 수비대: 경제 핵심 건물(학생회관·공학관·병원)
    if GARRISON:
        for b in owned:
            if b["type"] not in ("HALL", "ENG", "HOSPITAL"):
                continue
            p = (b["x"], b["y"])
            thr = 0
            for q, c in en["W"].items():
                if brain.d(q, p) <= GARRISON_R:
                    thr += c
            if any(brain.d(sp, p) <= GARRISON_R for sp in e_spawn_pts):
                thr += e_capW
            ef = any(brain.d(q, p) <= GARRISON_R + 2 for q in en["F"])
            if thr == 0 and not ef:
                if MIN_GAR and b["type"] in ("HALL", "ENG") and turn > 6:
                    demands.append((3 + value(brain, b, turn), "garrison", p, MIN_GAR))
                continue
            need = min(thr + 1, 25)
            demands.append((6 + value(brain, b, turn), "garrison", p, need))

    # D3 사냥: 적 깃발병
    for q, cnt in en["F"].items():
        b = bmap.get(q)
        if b is not None:
            pr = 9 + value(brain, b, turn) + cnt
        else:
            pr = 5 + cnt
        demands.append((pr, "hunt", q, ereach.get(q, 0) + 1))
        # 건물 밖 깃발병은 다음 칸으로 이동할 가능성이 높으므로 예상 위치도 노린다
        if b is None:
            tg = [(bb["x"], bb["y"]) for bb in view.buildings if bb["owner"] != op]
            if tg:
                near = min(tg, key=lambda t: brain.d(q, t))
                dq = brain.d(q, near)
                nxt = [n for _, n in brain.nbrs[q] if brain.d(n, near) == dq - 1]
                for n in nxt:
                    demands.append((pr - 0.5 * len(nxt), "hunt", n, ereach.get(n, 0) + 1))
                if AMBUSH and dq <= 3:
                    demands.append((pr - 1.5, "hunt", near, ereach.get(near, 0) + 1))
            # 요격: 적 깃발병이 노릴 만한 내 건물에 깃발병보다 먼저 전투병을 세운다
            if INTERCEPT:
                mine_near = sorted(((brain.d(q, (bb["x"], bb["y"])), (bb["x"], bb["y"]), bb) for bb in owned
                                    if brain.d(q, (bb["x"], bb["y"])) <= INTERCEPT_R), key=lambda t: t[0])[:INTERCEPT_N]
                esc = sum(c2 for q2, c2 in en["W"].items() if brain.d(q, q2) <= 1)
                for dqb, bp, bb in mine_near:
                    demands.append((7 + value(brain, bb, turn) - 0.3 * dqb, "intercept", bp, esc + 1, dqb))

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
    for dm in demands:
        pr, kind, cell, need = dm[:4]
        if kind == "intercept":
            intercept(cell, need, dm[4])
            continue
        ok = arrive_need(cell, need, allow_partial=(kind in ("defend", "garrison")))
        if not ok and kind in ("hunt", "escort", "escort2", "defend", "defend2", "garrison"):
            approach(cell, need - w_dest.get(cell, 0), radius=4 if kind != "hunt" else 5)

    # D3.5 포위: 전투병이 압도적이면 적 생산 거점(본진·병원) 주변을 봉쇄
    n_w_now = len(wlist)
    if SIEGE and turn > 20 and n_w_now >= SIEGE_MULT * n_ew + SIEGE_ADD:
        e_next = min(CFG["resource"]["resource_cap"], view.opp_resource + 12)
        spawn_w = e_next // ewc
        cells = []
        for sp in e_spawn_pts:
            for _, n in brain.nbrs.get(sp, []):
                cells.append(n)
        for c in cells:
            need = spawn_w + sum(en["W"].get(n, 0) for n in brain.n1(c)) + 1
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

    # D4 집결: 남은 전투병은 한 지점으로
    free = [i for i in range(len(wlist)) if not w_used[i]]
    if free:
        cands = []
        for q, cnt in en["F"].items():
            cands.append((q, 3.0 + cnt))
        for b in view.buildings:
            p = (b["x"], b["y"])
            if b["owner"] != me:
                cands.append((p, value(brain, b, turn) + (1.0 if b["owner"] == op else 0.0)))
            elif ereach.get(p, 0) > 0 or any(brain.d(q, p) <= 3 for q in en["F"]):
                cands.append((p, value(brain, b, turn) * 0.8))
            elif NET_OWN > 0:
                cands.append((p, value(brain, b, turn) * NET_OWN))
        if not cands:
            cands = [(brain.obase, 1.0)]
        best = None
        for p, v in cands:
            avgd = sum(brain.d(wlist[i], p) for i in free) / len(free)
            sc = v / (avgd + 3)
            if best is None or sc > best[0]:
                best = (sc, p)
        rally0 = best[1]
        # 내 역이 2개 이상이면, 먼 역에 있는 자유 전투병을 집결지에 가까운 역으로 순간이동
        my_st = [(b["x"], b["y"]) for b in owned if b["type"] == "STATION"]
        if TELE_ON and len(my_st) >= 2:
            s_to = min(my_st, key=lambda st: brain.d(st, rally0))
            best_from = None
            for st in my_st:
                if st == s_to:
                    continue
                idxs = [i for i in free if wlist[i] == st and not w_used[i]]
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
                cmds.append(tele(st[0], st[1], "W", len(idxs), s_to[0], s_to[1]))
        load = {}
        for i in free:
            if w_used[i]:
                continue
            p = wlist[i]
            if NET_K > 0:
                ok = [pv for pv in cands if load.get(pv[0], 0) + w_dest.get(pv[0], 0) < NET_K]
                pool = ok if ok else cands
                rally = max(pool, key=lambda pv: pv[1] / (brain.d(p, pv[0]) + RALLY_D))[0]
                load[rally] = load.get(rally, 0) + 1
            else:
                rally = max(cands, key=lambda pv: pv[1] / (brain.d(p, pv[0]) + RALLY_D))[0] if RALLY_SPLIT else rally0
            dcur = brain.d(p, rally)
            if dcur == 0 or dcur >= INF:
                w_used[i] = True
                w_dest[p] = w_dest.get(p, 0) + 1
                continue
            steps = [n for _, n in brain.nbrs[p] if brain.d(n, rally) == dcur - 1]
            commit(i, min(steps, key=lambda n: (ereach.get(n, 0), n)))

    # ------------------------------------------------ 깃발병 안전 재검토 (전투병 배치 확정 후)
    def safe_final(c):
        t = ereach.get(c, 0)
        return t == 0 or w_dest.get(c, 0) > t

    f_dest = {}
    new_mem = {}
    for plan in fplans:
        src, dest, tp = plan
        if ENDGAME and TOTAL_TURNS - turn == 0 and tp is not None and brain.d(src, tp) <= 1:
            dest = tp  # 마지막 턴: 죽어도 손해 없음, 무조건 진입
        elif not safe_final(dest):
            cand = [src] + [n for _, n in brain.nbrs[src]]
            safe = [c for c in cand if safe_final(c)]
            if safe:
                if tp is not None:
                    dest = min(safe, key=lambda c: (brain.d(c, tp), c != src))
                else:
                    dest = min(safe, key=lambda c: (c in bmap, c != src))
            else:
                dest = min(cand, key=lambda c: (ereach.get(c, 0) - w_dest.get(c, 0), c != src))
            plan[1] = dest
        add_move(src, "F", dest)
        f_dest[dest] = f_dest.get(dest, 0) + 1
        if tp is not None and dest != tp:
            new_mem.setdefault(dest, []).append(tp)

    brain.fmem = new_mem

    # ------------------------------------------------ 명령 출력
    for (src, kind, dname), cnt in sorted(moves.items()):
        cmds.append(move(src[0], src[1], kind, cnt, dname))

    # 점령 우선순위: 이번 턴 깃발병이 서 있을 내 소유가 아닌 건물, 가치순
    pri = [c for c in f_dest if c in bmap and bmap[c]["owner"] != me]
    pri.sort(key=lambda c: -value(brain, bmap[c], turn))
    if pri:
        cmds.append(priority(pri))
    return cmds


if __name__ == "__main__":
    run(decide)
