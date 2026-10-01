"""my_bot5 — 깃발 대항전 전략 봇 (my_bot4 + 상대 공학관 공략).

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
 23. (my_bot4) 상대 수 읽기: 상대 입장에서 우리 판단 로직을 돌려 적 깃발병·전투병의 다음 위치를 예측하고,
     위협 계산을 '최악 가정의 절반과 예측값 중 큰 값'으로 보정해 깃발병을 더 과감하게 운용, 예측 위치의 적 깃발병 사냥.
     응답 시간이 120ms를 넘으면 다음 턴은 예측을 생략(시간 초과 방지).
 24. (my_bot4) 호송대: 깃발병마다 전투병 5명이 함께 이동해, 전투병을 얇게 펼치는 상대의 그물 방어를 돌파.
 25. (my_bot5) 상대 공학관을 집중 공략(목표 가치 2배, 집결 2배).
 16. 파라미터 탐색(실제 맵 + 무작위 맵) 결과: 초반 깃발병 4명, 경제 가중치 9 등.
공식 리플레이 26경기 재분석(패배 경기 대부분이 게임 종료 시 학생회관+공학관 4개 전부를 상대가
독식) 기반 my_bot5 보완:
 26. 순환 함정 제거: STRIKE 발동 조건을 "내가 이미 1.1배 앞설 때"에서 "상대 공학관 수 > 내 공학관
     수이고 내 병력이 상대의 0.7배 이상일 때"로 바꿔, 밀리기 시작하기 전에 조기 개입한다.
 27. MIN_GAR 1→3, ENG_PR 0→2.0, RETAKE_MULT 1.0→1.6 재활성화: 학생회관·공학관 상시 수비대와
     우리 진영 공학관 탈환 우선순위를 실측된 상대 공세 규모(경기당 26~35회)에 맞게 올린다.
 28. 경제 핵심 건물 수비에 2턴 내 위협(ereach2)을 조기 반영해, 적이 반경 2칸에 들어온 뒤에야
     반응하던 지연을 줄인다.
 29. 집중 방어(outnumbered = 전체 전투병이 상대의 0.75배 미만): 호송 규모 축소, 사냥 우선순위
     하향, 예비 병력의 분산 집결을 끄고 본진 경제 건물로 모은다 — 힘을 여러 곳에 얇게 펼쳐
     각개격파당하던 패턴(리플레이에서 확인) 보완.
제출 규정 준수: 모든 값은 소스에 상수로 포함, 실행 중 파일 읽기·네트워크 접근 없음.
표준 라이브러리만 사용한다.
"""
from __future__ import annotations

import sys
import time
from strategy_common import Ledger, BudgetExpired, check_time, fallback, final_flags
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
HOME_BIAS = 0.08
HOME_TURNS = 60
GARRISON = True
ENDGAME = True
INTERCEPT = False
MIN_GAR = 2
MIRROR_Y = True
LOCAL3 = False
LOCAL3_MIN = 0.15
POLICE = False
POLICE_PR = 8.0
GAR_RADIUS = 30
PREDICT = True
PRED_PR = 9.5
PRED_ALPHA = 0.5
CONVOY_N = 5
ENG_R = 2
ENG_PR = 2.0
RETAKE_MULT = 1.6
LEAD_M = 0
LEAD_DEEP = 0.5
ENG_STRIKE = True
STRIKE_MULT = 0.7
STRIKE_TGT = 2.0
STRIKE_RALLY = 2.0
CONCENTRATE_TH = 0.7
GARRISON_BOOST = 2.0
FORTRESS_MIN = 1
FORTRESS_RETAKE_MULT = 1.8
SPOIL_ON = True
FORTRESS_ON = False
CONVOY_PR = 6.5
CONVOY_R = 6
PRED_TIME_LIMIT = 0.12
CAUT = True
MID_F_HI = 4
MID_F_LO = 2
RALLY_D = 5
INTERCEPT_R = 6
INTERCEPT_N = 2
TELE_ON = True
TELE_GAIN = 4
EARLY_F = 4
EARLY_T = 8
EO_MULT = 0.3
STICK = 1.5
GARRISON_R = 2
SUPPLY_FIX = True
CONTROL_FIX = False
PRESSURE_FIX = False
HOSPITAL_FIX = True
EXPAND_FIX = False
GUARD_FIX = False
BREACH_FIX = False
BOARD_FIX = True
ADAPT_FIX = False
DENY_FIX_OWNER = False
DENY_FIX_NEUTRAL = False
WATCH_FIX = False
AUCTION_FIX = False
KNAPSACK_FIX = True
MATCH_FIX = False
MATCH_FIX_CAP = 10
IMPATIENT_FIX = False
IMPATIENT_TURNS = 2
IMPATIENT_RISK = 1
SAFE_THREAT_FIX = True
RALLY_FIX = False
DETOUR_FIX = False
FGEN_FIX = False


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
        self.near = {p: [p] + [n for _, n in ns] for p, ns in self.nbrs.items()}
        self.near2 = {p: set(q for n in self.near[p] for q in self.near[n]) for p in self.nbrs}
        self.predicted_flags = {}
        self.prediction_error = 0.0
        self.stalled = {}
        self.ledger = Ledger()
        self.deadline = float("inf")
        self.bpos = {(b["x"], b["y"]): b for b in init.buildings}
        self.known = {}          # 좌표 -> 실제 점수 (대칭 추론 포함)
        self.depot_got = set()   # 내가 보너스를 받은 보급소 좌표
        self.opp_brain = None
        self.fmem = {}           # 지난 턴 깃발병 도착 칸 -> [목표] (목표 유지용)
        # 요새: 본진에서 제일 가까운 건물 하나. 게임 내내 항상 두텁게 지켜 즉시패(점수 0)를 막는다.
        self.fortress = min(self.bpos, key=lambda p: self.d(self.base, p))

    def d(self, a, b):
        return self.dist[a][idx(*b)] if a in self.dist else INF

    def n1(self, c):
        """c 와 거리 1 이내 칸 (자기 자신 포함)."""
        return self.near.get(c, [c])

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
    if HOSPITAL_FIX and b["type"] == "HOSPITAL":
        target = (b["x"], b["y"])
        others = [brain.base] + [p for p in brain.ctx.get("hospitals", []) if p != target]
        savings = [max(0, min(brain.d(sp, p) for sp in others) - brain.d(target, p)) for p in brain.bpos]
        v += min(12.0, sum(savings) / len(savings) * 1.5) * left
    if b["type"] == "DEPOT" and (b["x"], b["y"]) not in brain.depot_got:
        v += 2.5
    if WATCH_FIX and b["type"] == "WATCH":
        # 반경 3칸 안의 모르는 건물 점수를 밝혀주는 파급 효과(이후 모든 턴의 가치 판단이
        # 더 정확해짐)를 밝혀질 건물 수에 비례해 반영한다.
        p = (b["x"], b["y"])
        unknown = sum(1 for q in brain.bpos if q not in brain.known and cheb(p, q) <= 3)
        v += min(3.0, unknown * 0.4) * left
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
    import time
    t0 = time.perf_counter()
    try:
        return _decide_entry(view, init)
    finally:
        dt = time.perf_counter() - t0
        for b in _BRAINS.values():
            # 응답 시간이 길어지면(느린 채점 서버 대비) 다음 턴은 상대 예측을 끈다
            b.slow = dt > PRED_TIME_LIMIT and view.turn > 1


def _decide_entry(view, init):
    try:
        if MIRROR_Y and init.team == "Y":
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
    except Exception as e:  # 어떤 예외도 몰수패로 이어지지 않도록
        log("ERR", repr(e))
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
        ob.me, ob.op = brain.op, brain.me
        ob.base, ob.obase = brain.obase, brain.base
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
        if u["team"] == brain.op:
            k = (u["kind"], (u["x"], u["y"]))
            units[k] = units.get(k, 0) + u["count"]
    ob_base = brain.obase
    for c in out:
        t = c.split()
        if t[0] == "SPAWN":
            pos = (int(t[3]), int(t[4])) if len(t) == 5 else ob_base
            units[(t[1], pos)] = units.get((t[1], pos), 0) + int(t[2])
    moved = {}
    for c in out:
        t = c.split()
        if t[0] == "MOVE":
            src = (int(t[1]), int(t[2])); k = t[3]; n = int(t[4])
            dx, dy = DIRS[t[5]]
            dst = (src[0] + dx, src[1] + dy)
            have = units.get((k, src), 0)
            m = min(n, have)
            if m <= 0:
                continue
            units[(k, src)] = have - m
            moved[(k, dst)] = moved.get((k, dst), 0) + m
    for k, v in moved.items():
        units[k] = units.get(k, 0) + v
    pf = {p: c for (k, p), c in units.items() if k == "F" and c > 0}
    pw = {p: c for (k, p), c in units.items() if k == "W" and c > 0}
    return pf, pw


def _decide(brain, view):
    me, op = brain.me, brain.op
    turn = view.turn
    cmds = []

    check_time(brain.deadline)
    brain.ledger.update(view)
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
                 "income": income, "e_income": e_income,
                 "hospitals": [(b["x"], b["y"]) for b in owned if b["type"] == "HOSPITAL"]}

    def cap_cost(b):
        c = CFG["capture"]["capture_cost"] * (CFG["capture"]["plaza_multiplier"] if b["type"] == "PLAZA" else 1)
        if my_lib:
            c = max(CFG["capture"]["min_capture_cost"], c - CFG["buildings"]["library_discount"])
        return c

    if ADAPT_FIX and not _PREDICTING[0] and brain.predicted_flags and en["F"]:
        matched = sum(min(n, brain.predicted_flags.get(p, 0)) for p, n in en["F"].items())
        error = 1 - matched / sum(en["F"].values())
        brain.prediction_error = 0.8 * brain.prediction_error + 0.2 * error
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
    ereach_raw = dict(ereach)  # 자기모델 할인 전 '진짜 최악의 경우' — 생존이 걸린 판단엔 이걸 쓴다
    # 상대 행동 예측으로 위협 보정(최악 가정의 ALPHA 배 이상, 예측된 도착 수 이상)
    pf_pred, pw_pred = ({}, {})
    if PREDICT and not _PREDICTING[0] and not getattr(brain, "slow", False):
        pf_pred, pw_pred = predict_enemy(brain, view)
        alpha = min(0.9, PRED_ALPHA + 0.4 * brain.prediction_error) if ADAPT_FIX else PRED_ALPHA
        if ADAPT_FIX:
            brain.predicted_flags = dict(pf_pred)
        if alpha < 1.0:
            for c in list(ereach.keys()):
                ereach[c] = max(pw_pred.get(c, 0), int(ereach[c] * alpha + 0.999))
    # 2턴 내 위협(깃발병 경로 선택·사전 호위용)
    ereach2 = {}
    if CAUT:
        ew_items = list(en["W"].items())
        for c in brain.nbrs:
            check_time(brain.deadline)
            s2 = sum(en["W"].get(q, 0) for q in brain.near2[c])
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
            ereach_raw[st] = ereach_raw.get(st, 0) + min(5, others_w)
            eflag1[st] = eflag1.get(st, 0) + min(5, others_f)

    # ------------------------------------------------ 생산 계획
    open_targets = [b for b in view.buildings if b["owner"] != me]
    my_sc = sum(est_score(brain, b) for b in owned)
    en_sc = sum(est_score(brain, b) for b in eowned)
    leading = LEAD_M > 0 and turn > 20 and my_sc >= en_sc + LEAD_M
    n_w0 = sum(my["W"].values()); n_ew0 = sum(en["W"].values())
    # 상대가 이미 앞서야만(1.1배) 발동하던 예전 조건은, 정작 밀리기 시작하면 영영 못 켜지는
    # 순환 함정이었다. "상대 공학관 수가 나보다 많으면" 자체를 트리거로 바꿔 조기에 개입한다.
    strike = ENG_STRIKE and turn > 10 and e_engs > my_engs and n_w0 >= STRIKE_MULT * n_ew0
    n_f = sum(my["F"].values())
    n_w = sum(my["W"].values())
    n_ew = sum(en["W"].values())
    # 전체 전투병 수에서 밀리는 중이면(경제 건물 소유 격차의 전조), 확산 대신 집중 방어로 전환
    outnumbered = n_ew > 0 and n_w < CONCENTRATE_TH * n_ew

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
    budget = max(0, view.my_resource - reserve)

    spawn_pts = [brain.base] + [(b["x"], b["y"]) for b in owned if b["type"] == "HOSPITAL"]

    def best_spawn(targets):
        if not targets:
            return brain.base
        return min(spawn_pts, key=lambda s: (min(brain.d(s, t) for t in targets), s != brain.base))

    # 원하는 깃발병 수
    useful_targets = [b for b in open_targets if min(brain.d(s, (b["x"], b["y"])) for s in spawn_pts) <= TOTAL_TURNS - turn + 1]
    if not useful_targets:
        want_f = 0
    elif turn <= EARLY_T:
        want_f = min(len(open_targets), EARLY_F)
    else:
        want_f = min(len(open_targets), MID_F_HI if n_w >= 0.75 * n_ew else MID_F_LO)
        if n_w >= n_ew + 6:
            want_f = min(len(open_targets), 5)
        if FGEN_FIX and n_w < 0.75 * n_ew:
            # 열세라고 무조건 목표를 2로 줄이지 말고, 실제로 당장 안전하게(도달 가능한 적
            # 위협이 없는) 갈 수 있는 목표가 있으면 그만큼은 생산한다 — "가치만 올리는" 게
            # 아니라 "실제로 할 수 있는 일의 개수"로 상한을 다시 정하는 것.
            safe_n = sum(1 for b in useful_targets if ereach_raw.get((b["x"], b["y"]), 0) == 0)
            if safe_n > want_f:
                want_f = min(len(open_targets), MID_F_HI, safe_n)

    if EXPAND_FIX and useful_targets and turn < 140:
        # Extra flags keep multiple fronts active; do not halve capture capacity just
        # because the current standing army is slightly smaller.
        want_f = min(len(useful_targets), 6 if turn <= 16 else 5)
    spawned = []  # (kind, count, pos)
    make_f = 0
    if n_f < want_f and budget >= FC:
        # 전투병이 너무 부족하면(적 전투병 대비) 깃발병 생산을 한 명으로 제한
        lim = want_f - n_f
        if turn > 12 and n_w < n_ew:
            lim = min(lim, 1)
        make_f = min(lim, budget // FC)
    if make_f:
        fpos = best_spawn([(b["x"], b["y"]) for b in useful_targets])
        budget -= make_f * FC
        spawned.append(("F", make_f, fpos))
    make_w = budget // wc
    # 첫 턴은 자원 10으로 깃발병 2명이 최선
    if make_w:
        front = [p for p in en["F"]] + [(b["x"], b["y"]) for b in open_targets]
        if SUPPLY_FIX:
            tasks = []
            for b in owned:
                p = (b["x"], b["y"])
                fd = min((brain.d(q, p) for q in en["F"]), default=INF)
                if fd <= 5:
                    radius = max(1, min(3, fd))
                    threat = sum(c for q, c in en["W"].items() if brain.d(q, p) <= radius)
                    have = sum(c / max(1, brain.d(q, p)) for q, c in my["W"].items() if brain.d(q, p) <= radius)
                    tasks.append((p, max(0, threat + 2 - have), (8 + value(brain, b, turn)) / (fd + 1)))
            for p, nf in my["F"].items():
                if not open_targets:
                    continue
                tp = min(open_targets, key=lambda b: brain.d(p, (b["x"], b["y"])))
                target = (tp["x"], tp["y"])
                need = max(3, min(12, ereach2.get(p, 0) + 1))
                have = sum(c for q, c in my["W"].items() if brain.d(q, p) <= 2)
                tasks.append((p, max(0, need - have), 5 + value(brain, tp, turn) / (brain.d(p, target) + 2)))
            allocations = {}
            for _ in range(make_w):
                best = None
                for sp in spawn_pts:
                    benefit = 0.0
                    for p, need, weight in tasks:
                        supplied = sum(n / (brain.d(origin, p) + 1) for origin, n in allocations.items())
                        deficit = max(0.0, need - supplied)
                        benefit += weight * min(1.0, deficit) / (brain.d(sp, p) + 1)
                    if best is None or benefit > best[0]:
                        best = (benefit, sp)
                wp = best[1] if best and best[0] > 0 else best_spawn(front)
                allocations[wp] = allocations.get(wp, 0) + 1
            for wp, amount in allocations.items():
                spawned.append(("W", amount, wp))
        else:
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

    def threat(c):
        # 생존이 걸린 판단(깃발병 안전, 수비 병력 규모)은 자기모델 할인 전 진짜 최악의 경우를 쓴다.
        # 실제 상대는 우리처럼 생각하지 않는 경우가 많아, 할인된 ereach만 믿으면 과소평가로
        # 깃발병이 죽거나 수비가 뚫리는 사례가 실전 리플레이에서 반복 확인됨.
        return ereach_raw.get(c, 0) if SAFE_THREAT_FIX else ereach.get(c, 0)

    def danger(c):
        return threat(c) - my_cover(c)

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
            if threat(p) > 0 and danger(p) >= 0 and threat(p) >= my_cover(p):
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
        if PRESSURE_FIX:
            v /= 1.0 + 0.5 * brain.stalled.get((fp, tp), 0)
        tl = TOTAL_TURNS - turn
        if ENDGAME and tl < 12:
            # 남은 턴 안에 점령(또는 중립화)이 끝날 수 없는 목표는 무의미
            if dd + (1 if b["owner"] == op else 0) > tl + 1 and not (b["owner"] == op and dd <= tl):
                return -1
        if b["type"] == "ENG" and brain.d(brain.base, tp) < brain.d(brain.obase, tp) and b["owner"] != me:
            v *= RETAKE_MULT  # 우리 진영 공학관 탈환 최우선
        if FORTRESS_ON and tp == brain.fortress and b["owner"] == op:
            v *= FORTRESS_RETAKE_MULT  # 요새를 상대에게 뺏겼으면 최우선으로 되찾는다(중립 최초 점령엔 미적용)
        if strike and b["type"] == "ENG" and b["owner"] == op:
            v *= STRIKE_TGT
        if leading and brain.d(brain.obase, tp) < brain.d(brain.base, tp):
            v *= LEAD_DEEP
        if b["owner"] == op:
            if DENY_FIX_OWNER:
                # 1단계(중립화)만 해도 상대 점수를 확실히 깎는다 — 그 몫은 할인하지 않고,
                # 끝까지 지켜야 생기는 나머지(경제·기능 이득)만 불확실성 할인을 적용한다.
                deny_gain = est_score(brain, b)
                v = deny_gain + (v - deny_gain) * (0.7 if PRESSURE_FIX else EO_MULT)
            else:
                # Two stages cost time, but successful neutralization also removes enemy score.
                v *= (0.7 if PRESSURE_FIX else EO_MULT)
        # 적 전투병이 버티는 건물은 불리
        ew_here = en["W"].get(tp, 0)
        mw_near = sum(my["W"].get(n, 0) for n in brain.n1(tp))
        if ew_here > mw_near:
            v *= 0.3
        # 적 깃발병이 이미 있고 전투병 지원이 없다면 경합만 된다
        if en["F"].get(tp, 0) and mw_near == 0:
            if DENY_FIX_NEUTRAL and b["owner"] == "N":
                # 점령은 못 해도 경합으로 이번 턴 상대 획득을 막는 것 자체에 가치가 있다
                v = max(v * 0.5, est_score(brain, b) * 0.5)
            else:
                v *= 0.5
        # 목표 주변 3칸의 전투병 균형: 적이 우세한 곳(특히 적 본진 옆)은 현실성이 낮다
        if LOCAL3:
            ew3 = sum(c for q, c in en["W"].items() if brain.d(q, tp) <= 3)
            if any(brain.d(sp, tp) <= 3 for sp in e_spawn_pts):
                ew3 += e_capW
            mw3 = sum(c for q, c in my["W"].items() if brain.d(q, tp) <= 3)
            if ew3 > mw3:
                v *= max(LOCAL3_MIN, (mw3 + 1.0) / (ew3 + 1.0))
        # 적 본진 쪽으로 너무 깊이 들어가는 건 위험
        if brain.d(brain.obase, tp) < brain.d(brain.base, tp) and n_w <= n_ew:
            v *= 0.7
        # 초반에는 내 본진 쪽(지키기 쉬운) 건물부터
        if turn <= HOME_TURNS:
            safety = brain.d(brain.obase, tp) - brain.d(brain.base, tp)
            v *= max(0.3, 1.0 + HOME_BIAS * max(-8, min(8, safety)))
        return v / (dd + 2)

    remaining = [b for b in open_targets if (b["x"], b["y"]) not in claimed]
    prev_t = {}
    for i, fp in enumerate(free_flags):
        lst = brain.fmem.get(fp)
        if lst:
            prev_t[i] = lst.pop()

    assign = {}
    F = len(free_flags)
    T = len(remaining)
    if MATCH_FIX and 0 < F <= MATCH_FIX_CAP and T > 0:
        # 전역 최적 배정: 고정된 소수(깃발병 x 목표) 후보 중 총 가치가 최대인 조합을
        # 비트마스크 DP로 정확히 찾는다(기존 그리디는 국소최적에 그칠 수 있음).
        check_time(brain.deadline)
        eff = [[0.0] * T for _ in range(F)]
        for i, fp in enumerate(free_flags):
            for j, b in enumerate(remaining):
                e = target_eff(fp, b)
                if e > 0:
                    if prev_t.get(i) == (b["x"], b["y"]):
                        e *= STICK
                    eff[i][j] = e
        dp_states = [{0: 0.0}]
        parent = [None]
        for j in range(T):
            if j % 6 == 0:
                check_time(brain.deadline)
            cur = dp_states[j]
            nxt = {}
            par = {}
            for mask, val in cur.items():
                if val > nxt.get(mask, -1.0):
                    nxt[mask] = val
                    par[mask] = (mask, -1)
                for i in range(F):
                    if mask & (1 << i):
                        continue
                    e = eff[i][j]
                    if e <= 0:
                        continue
                    nmask = mask | (1 << i)
                    cand = val + e
                    if cand > nxt.get(nmask, -1.0):
                        nxt[nmask] = cand
                        par[nmask] = (mask, i)
            dp_states.append(nxt)
            parent.append(par)
        final = dp_states[T]
        best_mask = max(final, key=lambda m: final[m])
        mask = best_mask
        for j in range(T, 0, -1):
            prev_mask, i = parent[j][mask]
            if i != -1:
                b = remaining[j - 1]
                assign[i] = (b["x"], b["y"])
            mask = prev_mask
    else:
        pairs = []
        for i, fp in enumerate(free_flags):
            for b in remaining:
                e = target_eff(fp, b)
                if e > 0:
                    if prev_t.get(i) == (b["x"], b["y"]):
                        e *= STICK
                    pairs.append((e, i, (b["x"], b["y"])))
        pairs.sort(reverse=True)
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
            if b and b["owner"] == me and threat(fp) > 0:
                opts = [n for _, n in brain.nbrs[fp] if n not in bmap]
                if opts:
                    dest = min(opts, key=lambda n: danger(n))
            fplans.append([fp, dest, None])
            f_dest[dest] = f_dest.get(dest, 0) + 1
            continue
        dcur = brain.d(fp, tp)
        steps = [n for _, n in brain.nbrs[fp] if brain.d(n, tp) == dcur - 1]
        safe_steps = [n for n in steps if threat(n) == 0 or my_cover(n) > threat(n)]
        if safe_steps:
            dest = min(safe_steps, key=lambda n: (danger(n), ereach2.get(n, 0), n))
        elif PRESSURE_FIX:
            detours = [n for _, n in brain.nbrs[fp] if brain.d(n, tp) <= dcur + 1
                       and (threat(n) == 0 or my_cover(n) > threat(n))]
            dest = min(detours, key=lambda n: (ereach2.get(n, 0), brain.d(n, tp))) if detours else fp
        elif threat(fp) == 0 or my_cover(fp) > threat(fp):
            dest = fp  # 제자리 대기(호위를 기다림)
            if (DETOUR_FIX or IMPATIENT_FIX) and brain.stalled.get((fp, tp), 0) >= IMPATIENT_TURNS:
                if DETOUR_FIX:
                    # 최단경로 방향이 위험해도, 거리가 늘지 않는 완전히 안전한 우회로가
                    # 있으면 그쪽으로(위험을 감수하지 않고) 돈다.
                    side_steps = [n for _, n in brain.nbrs[fp]
                                  if n not in steps and brain.d(n, tp) <= dcur + 1
                                  and (threat(n) == 0 or my_cover(n) > threat(n))]
                    if side_steps:
                        dest = min(side_steps, key=lambda n: (brain.d(n, tp), n))
                if dest == fp and IMPATIENT_FIX and steps:
                    # 안전한 우회로가 없으면, 근처에 지원 올 전투병이 있어서 위험 부담이
                    # 작은(danger<=허용치) 전진로가 있을 때만 움직인다.
                    # (호위 없이 무작정 미는 건 이미 역효과로 확인된 패턴 — 위험이 안 줄면 그냥 대기)
                    best_step = min(steps, key=lambda n: (danger(n), brain.d(n, tp)))
                    if danger(best_step) <= IMPATIENT_RISK:
                        dest = best_step
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
    # D1.2 호송: 깃발병마다 전투병 몇 명이 항상 함께 이동(얇게 퍼진 적 전투병 그물을 뚫기 위함)
    conv_n = CONVOY_N if not outnumbered else max(1, CONVOY_N // 2)
    if conv_n > 0 and turn > 6:
        for c, cnt in f_dest.items():
            b = bmap.get(c)
            if b is not None and b["owner"] == me:
                continue
            extra = 0
            urgency = 0
            if BREACH_FIX:
                for src, dest, target in fplans:
                    if dest != c or target is None or c == target:
                        continue
                    distance = brain.d(c, target)
                    next_steps = [p for _, p in brain.nbrs[c] if brain.d(p, target) < distance]
                    if next_steps:
                        extra = max(extra, min(18, min(ereach.get(p, 0) for p in next_steps) + 1))
                        if src == dest:
                            urgency = max(urgency, min(6, brain.stalled.get((src, target), 0)))
            demands.append((CONVOY_PR + cnt + urgency, "convoy", c, max(conv_n * cnt, extra)))
    # D1.5 사전 호위: 다음 다음 턴 위협이 있는 깃발병 도착 칸
    if CAUT:
        for c, cnt in f_dest.items():
            if threat(c) == 0 and ereach2.get(c, 0) > 0:
                demands.append((5 + cnt, "escort2", c, min(ereach2[c] + 1, 15)))
    # D2 방어: 적 깃발병이 1~2턴 안에 올 수 있는 내 건물
    for b in owned:
        p = (b["x"], b["y"])
        near1 = eflag1.get(p, 0) > 0
        near2 = any(brain.d(q, p) <= 2 for q in en["F"])
        if near1:
            demands.append(((30 if GUARD_FIX else 8) + value(brain, b, turn), "defend", p, threat(p) + 1))
        elif near2:
            demands.append(((16 if GUARD_FIX else 4) + value(brain, b, turn), "defend2", p, max(1, threat(p) + 1)))
    if CONTROL_FIX:
        for b in owned:
            p = (b["x"], b["y"])
            incoming = [(brain.d(q, p), q, cnt) for q, cnt in en["F"].items() if brain.d(q, p) <= 5]
            if not incoming:
                continue
            eta, fq, count = min(incoming)
            escort_n = sum(c for q, c in en["W"].items() if brain.d(q, fq) <= 1)
            # Reposition the reserve before the last possible defense turn.
            demands.append((11 + value(brain, b, turn) - 0.6 * eta, "intercept", p, escort_n + 1, max(1, eta)))

    # D2.5 상시 수비대: 경제 핵심 건물(학생회관·공학관·병원)
    if GARRISON:
        for b in owned:
            if b["type"] not in ("HALL", "ENG", "HOSPITAL") and not leading:
                continue
            p = (b["x"], b["y"])
            gr = ENG_R if b["type"] == "ENG" else GARRISON_R
            thr = 0
            for q, c in en["W"].items():
                if brain.d(q, p) <= gr:
                    thr += c
            if any(brain.d(sp, p) <= gr for sp in e_spawn_pts):
                thr += e_capW
            ef = any(brain.d(q, p) <= gr + 2 for q in en["F"])
            # 2턴 내 도달 가능한 위협(ereach2)을 경제 핵심 건물엔 조기 반영해, 적이 반경 2칸에
            # 들어오기 전에 미리 증원을 부른다(반응이 항상 한 박자 늦던 문제 보완).
            early_thr = ereach2.get(p, 0) if b["type"] in ("HALL", "ENG") else 0
            if thr == 0 and early_thr == 0 and not ef:
                if MIN_GAR and b["type"] in ("HALL", "ENG") and turn > 6:
                    demands.append((3 + value(brain, b, turn), "garrison", p, MIN_GAR))
                continue
            need = min(max(thr, early_thr) + 1, 25)
            boost = GARRISON_BOOST if outnumbered else 0.0
            demands.append((6 + value(brain, b, turn) + (ENG_PR if b["type"] == "ENG" else 0) + boost,
                             "garrison", p, need))

    # D2.6 요새: 본진에서 제일 가까운 건물 하나는 위협 여부와 무관하게 항상 최소 인원을 지킨다.
    # 즉시패(내 점수 0)를 막기 위한 최후 보루 — 패배 15경기 중 12경기가 즉시패였다.
    fp = brain.fortress
    fb = bmap.get(fp)
    if FORTRESS_ON and fb is not None and fb["owner"] == me:
        thr_f = sum(c for q, c in en["W"].items() if brain.d(q, fp) <= GARRISON_R + 1)
        if any(brain.d(sp, fp) <= GARRISON_R + 1 for sp in e_spawn_pts):
            thr_f += e_capW
        # 실제 위협이 보일 때만 기존 수비대보다 살짝 강하게 반응한다(상시 인원 예약은 하지 않음 —
        # 상시 예약판은 시뮬레이션에서 오히려 성적이 떨어져서 뺐다).
        if thr_f > 0:
            demands.append((7 + value(brain, fb, turn), "garrison", fp, thr_f + 1))

    # D2.9 예측 사냥: 상대 관점으로 예측한 적 깃발병의 다음 위치
    if pf_pred or pw_pred:
        pf, pw = pf_pred, pw_pred
        for c, cnt in pf.items():
            if c not in brain.nbrs:
                continue
            b = bmap.get(c)
            pr = PRED_PR + cnt + (value(brain, b, turn) if b is not None else 0)
            if ADAPT_FIX:
                pr *= 1 - 0.5 * brain.prediction_error
            demands.append((pr, "phunt", c, pw.get(c, 0) + 1))

    # D3 사냥: 적 깃발병
    for q, cnt in en["F"].items():
        b = bmap.get(q)
        if b is not None:
            pr = 9 + value(brain, b, turn) + cnt
        else:
            pr = 5 + cnt
        if outnumbered:
            pr *= 0.6  # 열세일 땐 원정 사냥보다 본진 방어에 병력을 남긴다
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

    # D3.2 자기 진영 경찰: 내 쪽 절반에 들어온 적 깃발병은 거리와 무관하게 추적
    if POLICE:
        for q, cnt in en["F"].items():
            if brain.d(brain.base, q) >= brain.d(brain.obase, q):
                continue
            esc = sum(c2 for q2, c2 in en["W"].items() if brain.d(q, q2) <= 1)
            mine_b = [(brain.d(q, (bb["x"], bb["y"])), (bb["x"], bb["y"])) for bb in owned]
            mine_b = [t for t in mine_b if t[0] <= 6]
            cell = min(mine_b)[1] if mine_b else q
            demands.append((POLICE_PR + cnt, "police", cell, esc + 1))

    demands.sort(key=lambda d: -d[0])
    deferred_auction = []  # AUCTION_FIX: defend류 중 1칸 이내로 못 채운 몫을 나중에 경매로
    for dm in demands:
        check_time(brain.deadline)
        pr, kind, cell, need = dm[:4]
        if kind == "intercept":
            intercept(cell, need, dm[4])
            continue
        defend_kind = kind in ("defend", "defend2", "garrison", "police")
        partial = defend_kind
        if CONTROL_FIX and ereach.get(cell, 0) >= my_cover(cell):
            partial = False
        ok = arrive_need(cell, need, allow_partial=partial)
        if kind == "phunt":
            continue
        if not ok and kind == "convoy":
            approach(cell, need - w_dest.get(cell, 0), radius=CONVOY_R)
            continue
        if not ok and defend_kind and AUCTION_FIX:
            # 우선순위 자리는 그대로 지키되(이미 1칸 이내 병력은 위에서 배정됨), 먼 곳에서
            # 끌어와야 하는 몫만 나중에 한꺼번에 경매로 처리한다.
            deferred_auction.append((cell, need - w_dest.get(cell, 0), pr, kind))
        elif not ok and kind in ("garrison", "police"):
            approach(cell, need - w_dest.get(cell, 0), radius=GAR_RADIUS)
        elif not ok and kind in ("hunt", "escort", "escort2", "defend", "defend2"):
            approach(cell, need - w_dest.get(cell, 0), radius=4 if kind != "hunt" else 5)

    # D3.95 방어 수요 경매: 가까운 병력으로 못 채운 defend류 잔여 수요를, 남은 모든 자유
    # 병력과 한 번에 놓고 한계효용(우선순위/이미 배정 인원/거리)이 제일 큰 (유닛,수요) 쌍부터
    # 배정한다 — 기존 우선순위 순서는 위 루프에서 이미 지켰고, "부족분을 누가 메울지"만 바꾼다.
    if AUCTION_FIX and deferred_auction:
        check_time(brain.deadline)
        tasks = [list(t) for t in deferred_auction]
        AUCTION_R = 8
        cand = [i for i, p in enumerate(wlist)
                if not w_used[i] and min((brain.d(p, t[0]) for t in tasks), default=INF) <= AUCTION_R]
        got = [0] * len(tasks)
        assigned = {}
        rounds = min(sum(t[1] for t in tasks), len(cand))
        for r in range(rounds):
            if r % 20 == 0:
                check_time(brain.deadline)
            best = None
            for i in cand:
                if i in assigned:
                    continue
                p = wlist[i]
                for ti, t in enumerate(tasks):
                    if got[ti] >= t[1]:
                        continue
                    dist = brain.d(p, t[0])
                    if dist > AUCTION_R:
                        continue
                    mv = t[2] / (1 + got[ti]) / (dist + 1)
                    if best is None or mv > best[0]:
                        best = (mv, i, ti)
            if best is None:
                break
            _, i, ti = best
            assigned[i] = ti
            got[ti] += 1
        for i, ti in assigned.items():
            cell = tasks[ti][0]
            p = wlist[i]
            dcur = brain.d(p, cell)
            if dcur <= 1:
                commit(i, cell)
            else:
                steps = [n for _, n in brain.nbrs[p] if brain.d(n, cell) == dcur - 1]
                if steps:
                    commit(i, min(steps, key=lambda n: (ereach.get(n, 0), n)))

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
                vv = value(brain, b, turn) + (1.0 if b["owner"] == op else 0.0)
                if strike and b["owner"] == op and b["type"] == "ENG":
                    vv *= STRIKE_RALLY
                cands.append((p, vv))
            elif ereach.get(p, 0) > 0 or any(brain.d(q, p) <= 3 for q in en["F"]):
                cands.append((p, value(brain, b, turn) * 0.8))
        if outnumbered:
            # 열세일 땐 당장 위협이 안 보여도 경제 핵심 건물을 집결 후보에 넣어
            # 예비 병력이 원정 대신 본진 쪽으로 모이게 한다.
            for b in owned:
                if b["type"] in ("HALL", "ENG", "HOSPITAL"):
                    cands.append(((b["x"], b["y"]), value(brain, b, turn) * 1.2))
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
        rally_load = {p: w_dest.get(p, 0) for p, _ in cands}
        for i in free:
            check_time(brain.deadline)
            if w_used[i]:
                continue
            p = wlist[i]
            # 열세일 땐 예비 병력을 여러 목표로 분산시키지 않고 한 곳(대개 본진 경제 건물)으로 모은다.
            rally = max(cands, key=lambda pv: pv[1] / (brain.d(p, pv[0]) + RALLY_D))[0] if (RALLY_SPLIT and not outnumbered) else rally0
            if BOARD_FIX and not (RALLY_FIX and outnumbered):
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

    # ------------------------------------------------ 깃발병 안전 재검토 (전투병 배치 확정 후)
    def safe_final(c):
        t = ereach.get(c, 0)
        return t == 0 or w_dest.get(c, 0) > t

    if ENDGAME and turn == TOTAL_TURNS:
        spent = sum(cnt * (FC if kind == "F" else wc) for kind, cnt, _ in spawned)
        funds = min(CFG["resource"]["resource_cap"], view.my_resource - spent + income)
        final_flags(brain, view, fplans, bmap, en, ereach_raw if SAFE_THREAT_FIX else ereach,
                    w_dest, cap_cost, funds)

    f_dest = {}
    new_mem = {}
    for plan in fplans:
        src, dest, tp = plan
        if not (ENDGAME and turn == TOTAL_TURNS) and not safe_final(dest):
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

    if PRESSURE_FIX or BREACH_FIX or IMPATIENT_FIX or DETOUR_FIX:
        stalled = {}
        for src, dest, tp in fplans:
            if tp is not None and brain.d(dest, tp) >= brain.d(src, tp):
                stalled[(dest, tp)] = brain.stalled.get((src, tp), 0) + 1
        brain.stalled = stalled
    brain.fmem = new_mem

    # ------------------------------------------------ 명령 출력
    for (src, kind, dname), cnt in sorted(moves.items()):
        cmds.append(move(src[0], src[1], kind, cnt, dname))

    # 점령 우선순위: 자원이 빠듯하면 가치순 그리디가 최적이 아닐 수 있어(배낭 문제),
    # 예산이 부족할 때만 0/1 배낭 DP로 가치 합이 최대인 조합을 먼저 배치한다.
    pri = [c for c in f_dest if c in bmap and bmap[c]["owner"] != me]
    if pri:
        items = [(c, cap_cost(bmap[c]), value(brain, bmap[c], turn)) for c in pri]
        if KNAPSACK_FIX and len(items) <= 20:
            spent = sum(cnt * (FC if kind == "F" else wc) for kind, cnt, pos in spawned)
            cap_budget = max(0, min(CFG["resource"]["resource_cap"],
                                     view.my_resource - spent + income))
            total_cost = sum(int(cost) for _, cost, _ in items)
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
                pri = (sorted(chosen, key=lambda c: -value(brain, bmap[c], turn)) +
                       sorted(rest, key=lambda c: -value(brain, bmap[c], turn)))
            else:
                pri.sort(key=lambda c: -value(brain, bmap[c], turn))
        else:
            pri.sort(key=lambda c: -value(brain, bmap[c], turn))
        cmds.append(priority(pri))
    return cmds


if __name__ == "__main__":
    run(decide)
