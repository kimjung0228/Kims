"""깃발 대항전 로컬 시뮬레이터 (규칙서 기반 근사 구현, 테스트용).

사용 예:
    python sim.py main example_lv2 --games 20
    python sim.py main main --games 10 --seed 5
    python sim.py main example_lv2 --subprocess   # 실제 stdin/stdout 프로세스로 대전 (시간 측정)

봇 인자는 이 폴더 안의 모듈 이름(.py 제외)이다. 각 봇 모듈은 decide(view, init)를 가져야 한다.
주의: 공식 엔진이 아니므로 세부 판정이 다를 수 있다.
"""
from __future__ import annotations

import argparse
import importlib.util
import io
import os
import random
import subprocess
import sys
import time
from collections import deque

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from _generated import BALANCE  # noqa: E402
import campus_bot  # noqa: E402

W = H = 15
DIRS = {"U": (0, -1), "D": (0, 1), "L": (-1, 0), "R": (1, 0)}
KINDS = ("F", "W", "S")
TEAMS = ("Y", "K")
CFG = BALANCE


def mirror(x, y):
    return 14 - x, 14 - y


# ------------------------------------------------------------------ 맵 생성

def gen_map(seed):
    rng = random.Random(seed)
    while True:
        terrain = [["."] * W for _ in range(H)]
        used = set()
        # 본진
        while True:
            bx, by = rng.randint(0, 4), rng.randint(0, 14)
            kx, ky = mirror(bx, by)
            if abs(bx - kx) + abs(by - ky) >= 12:
                break
        bases = {"Y": (bx, by), "K": (kx, ky)}
        for t, (x, y) in bases.items():
            terrain[y][x] = "H"
            used.add((x, y))
        buildings = []  # dict x,y,type,score
        used.add((7, 7))
        buildings.append({"x": 7, "y": 7, "type": "PLAZA", "score": 3})
        side_types = ["HALL", "LIBRARY", "ENG", "HOSPITAL", "STATION"]
        for bt in side_types:
            while True:
                x, y = rng.randint(0, 4), rng.randint(0, 14)
                if (x, y) not in used and mirror(x, y) not in used:
                    break
            s = rng.randint(1, 2)
            for (px, py) in ((x, y), mirror(x, y)):
                used.add((px, py))
                buildings.append({"x": px, "y": py, "type": bt, "score": s})
        for bt in ["STATION", "WATCH", "DEPOT"]:
            while True:
                x, y = rng.randint(5, 9), rng.randint(2, 12)
                mx, my = mirror(x, y)
                if (x, y) not in used and (mx, my) not in used and (x, y) != (mx, my):
                    break
            s = rng.randint(2, 4)
            for (px, py) in ((x, y), mirror(x, y)):
                used.add((px, py))
                buildings.append({"x": px, "y": py, "type": bt, "score": s})
        for b in buildings:
            terrain[b["y"]][b["x"]] = "B"
        ok = True
        n = 0
        tries = 0
        while n < 10 and tries < 4000:
            tries += 1
            x, y = rng.randint(0, 14), rng.randint(0, 14)
            mx, my = mirror(x, y)
            if (x, y) in used or (mx, my) in used or (x, y) == (mx, my):
                continue
            terrain[y][x] = terrain[my][mx] = "#"
            if connected(terrain, buildings, bases):
                used.add((x, y)); used.add((mx, my)); n += 1
            else:
                terrain[y][x] = terrain[my][mx] = "."
        if n < 10:
            continue
        buildings.sort(key=lambda b: (b["y"], b["x"]))
        for i, b in enumerate(buildings):
            b["id"] = i
        return terrain, buildings, bases


def connected(terrain, buildings, bases):
    start = bases["Y"]
    seen = {start}
    q = deque([start])
    while q:
        x, y = q.popleft()
        for dx, dy in DIRS.values():
            nx, ny = x + dx, y + dy
            if 0 <= nx < W and 0 <= ny < H and (nx, ny) not in seen and terrain[ny][nx] != "#":
                seen.add((nx, ny)); q.append((nx, ny))
    return all((b["x"], b["y"]) in seen for b in buildings) and bases["K"] in seen


# ------------------------------------------------------------------ 게임 상태

class Game:
    def __init__(self, seed):
        self.terrain, bl, self.bases = gen_map(seed)
        self.b = []
        for b in bl:
            self.b.append(dict(b, owner="N", stage=0))
        self.bpos = {(b["x"], b["y"]): b for b in self.b}
        self.res = {"Y": CFG["resource"]["start_resource"], "K": CFG["resource"]["start_resource"]}
        self.units = {}  # (team,kind,x,y) -> count
        self.revealed = {"Y": set(), "K": set()}
        self.depot_got = {"Y": set(), "K": set()}
        self.occ = {"Y": 0, "K": 0}
        self.turn = 0
        self.total = sum(b["score"] for b in self.b)
        self.winner = None
        self.reason = ""

    def passable(self, x, y):
        return 0 <= x < W and 0 <= y < H and self.terrain[y][x] != "#"

    def owned(self, team, bt=None):
        return [b for b in self.b if b["owner"] == team and (bt is None or b["type"] == bt)]

    def score(self, team):
        return sum(b["score"] for b in self.owned(team))

    # --------------------------- 입력 텍스트
    def init_text(self, team):
        L = [f"INIT {W} {H}", f"TEAM {team}"]
        for y in range(H):
            L.append("MAP " + "".join(self.terrain[y]))
        L.append(f"BUILDINGS {len(self.b)}")
        for b in self.b:
            L.append(f"{b['id']} {b['x']} {b['y']} {b['type']}")
        L.append(f"BASE Y {self.bases['Y'][0]} {self.bases['Y'][1]}")
        L.append(f"BASE K {self.bases['K'][0]} {self.bases['K'][1]}")
        return L

    def turn_text(self, team):
        opp = "K" if team == "Y" else "Y"
        L = [f"TURN {self.turn}", f"RESOURCE {self.res[team]} {self.res[opp]}"]
        us = sorted(((t, k, x, y, c) for (t, k, x, y), c in self.units.items() if c > 0),
                    key=lambda u: (TEAMS.index(u[0]), KINDS.index(u[1]), u[3], u[2]))
        L.append(f"UNITS {len(us)}")
        for t, k, x, y, c in us:
            L.append(f"{t} {k} {x} {y} {c}")
        L.append(f"BUILDINGS {len(self.b)}")
        for b in self.b:
            s = b["score"] if b["id"] in self.revealed[team] else -1
            L.append(f"{b['id']} {b['x']} {b['y']} {b['type']} {b['owner']} {b['stage']} {s}")
        return L

    # --------------------------- 명령 파싱
    @staticmethod
    def parse_cmds(lines):
        out = []
        for ln in lines:
            t = ln.split()
            if not t:
                continue
            try:
                if t[0] == "SPAWN" and len(t) in (3, 5) and t[1] in KINDS and int(t[2]) > 0:
                    out.append(("SPAWN", t[1], int(t[2]), *(map(int, t[3:]))))
                elif t[0] == "MOVE" and len(t) == 6 and t[3] in KINDS and int(t[4]) > 0 and t[5] in DIRS:
                    out.append(("MOVE", int(t[1]), int(t[2]), t[3], int(t[4]), t[5]))
                elif t[0] == "MOVE2" and len(t) == 7 and t[3] == "S" and int(t[4]) > 0 and t[5] in DIRS and t[6] in DIRS:
                    out.append(("MOVE2", int(t[1]), int(t[2]), "S", int(t[4]), t[5], t[6]))
                elif t[0] == "TELE" and len(t) == 7 and t[3] in KINDS and int(t[4]) > 0:
                    out.append(("TELE", int(t[1]), int(t[2]), t[3], int(t[4]), int(t[5]), int(t[6])))
                elif t[0] == "PRIORITY" and len(t) % 2 == 1:
                    v = list(map(int, t[1:]))
                    out.append(("PRIORITY", [(v[i], v[i + 1]) for i in range(0, len(v), 2)]))
            except ValueError:
                pass
        return out

    # --------------------------- 턴 처리
    def step(self, cmds):
        self.turn += 1
        cfg = CFG
        # 2. 생산
        for team in TEAMS:
            engs = len(self.owned(team, "ENG"))
            for c in cmds[team]:
                if c[0] != "SPAWN":
                    continue
                kind, n = c[1], c[2]
                if len(c) == 5:
                    b = self.bpos.get((c[3], c[4]))
                    if not b or b["type"] != "HOSPITAL" or b["owner"] != team:
                        continue
                    pos = (c[3], c[4])
                else:
                    pos = self.bases[team]
                cost = cfg["units"][kind]["cost"]
                if kind == "W":
                    cost = max(cfg["buildings"]["eng_cost_floor"], cost - engs * cfg["buildings"]["eng_discount_per"])
                n = min(n, self.res[team] // cost)
                if n <= 0:
                    continue
                self.res[team] -= n * cost
                key = (team, kind, pos[0], pos[1])
                self.units[key] = self.units.get(key, 0) + n
        # 3. 이동
        avail = dict(self.units)
        arrive = {}
        for team in TEAMS:
            stations = {(b["x"], b["y"]) for b in self.owned(team, "STATION")}
            tele_used = False
            for c in cmds[team]:
                if c[0] == "MOVE":
                    _, x, y, k, n, d = c
                    dx, dy = DIRS[d]
                    nx, ny = x + dx, y + dy
                    if not self.passable(nx, ny):
                        continue
                    dest = (nx, ny)
                elif c[0] == "MOVE2":
                    _, x, y, k, n, d1, d2 = c
                    mx, my = x + DIRS[d1][0], y + DIRS[d1][1]
                    nx, ny = mx + DIRS[d2][0], my + DIRS[d2][1]
                    if not self.passable(mx, my) or not self.passable(nx, ny):
                        continue
                    dest = (nx, ny)
                elif c[0] == "TELE":
                    _, x, y, k, n, tx, ty = c
                    if tele_used or len(stations) < 2 or (x, y) not in stations or (tx, ty) not in stations or (x, y) == (tx, ty):
                        continue
                    n = min(n, cfg["tele"]["max_units"])
                    dest = (tx, ty)
                else:
                    continue
                key = (team, k, x, y)
                m = min(n, avail.get(key, 0))
                if m <= 0:
                    continue
                if c[0] == "TELE":
                    tele_used = True
                avail[key] -= m
                dk = (team, k, dest[0], dest[1])
                arrive[dk] = arrive.get(dk, 0) + m
        units = {}
        for d in (avail, arrive):
            for k, v in d.items():
                if v > 0:
                    units[k] = units.get(k, 0) + v
        self.units = units
        # 4. 전투
        cells = {}
        for (t, k, x, y), c in self.units.items():
            cells.setdefault((x, y), set()).add(t)
        for (x, y), ts in cells.items():
            if len(ts) < 2:
                continue
            wy = self.units.get(("Y", "W", x, y), 0)
            wk = self.units.get(("K", "W", x, y), 0)
            m = min(wy, wk)
            wy -= m; wk -= m
            self.units[("Y", "W", x, y)] = wy
            self.units[("K", "W", x, y)] = wk
            loser = "K" if wy > 0 else ("Y" if wk > 0 else None)
            if loser:
                had_f = self.units.get((loser, "F", x, y), 0) > 0
                self.units[(loser, "F", x, y)] = 0
                self.units[(loser, "S", x, y)] = 0
                b = self.bpos.get((x, y))
                if had_f and b and b["owner"] == loser:
                    b["owner"] = "N"; b["stage"] = 1; b["_pulled"] = self.turn
        self.units = {k: v for k, v in self.units.items() if v > 0}
        # 6. 수입
        for team in TEAMS:
            inc = cfg["resource"]["base_income"] + cfg["resource"]["hall_bonus"] * len(self.owned(team, "HALL"))
            self.res[team] = min(cfg["resource"]["resource_cap"], self.res[team] + inc)
        # 7. 점령
        lib = {t: len(self.owned(t, "LIBRARY")) > 0 for t in TEAMS}
        touched = set()
        new_owned = {t: [] for t in TEAMS}
        for b in self.b:
            if b.get("_pulled") != self.turn and b["stage"] == 1:
                b["stage"] = 0  # 직전 턴 표시 해제 (N1 -> N0)
        for team in TEAMS:
            opp = "K" if team == "Y" else "Y"
            cand = []
            for b in self.b:
                p = (b["x"], b["y"])
                if self.units.get((team, "F", *p), 0) <= 0 or b["owner"] == team:
                    continue
                if self.units.get((opp, "F", *p), 0) > 0:
                    continue
                cand.append(b)
            pri = []
            for c in cmds[team]:
                if c[0] == "PRIORITY":
                    pri = c[1]
            order = []
            for p in pri:
                b = self.bpos.get(p)
                if b in cand and b not in order:
                    order.append(b)

            def keyf(b):
                s = b["score"] if b["id"] in self.revealed[team] else 0
                yy, xx = (b["y"], b["x"]) if team == "Y" else (14 - b["y"], 14 - b["x"])
                return (-s, yy, xx)
            order += sorted([b for b in cand if b not in order], key=keyf)
            for b in order:
                if b["id"] in touched:
                    continue
                cost = cfg["capture"]["capture_cost"] * (cfg["capture"]["plaza_multiplier"] if b["type"] == "PLAZA" else 1)
                if lib[team]:
                    cost = max(cfg["capture"]["min_capture_cost"], cost - cfg["buildings"]["library_discount"])
                if self.res[team] < cost:
                    continue
                self.res[team] -= cost
                touched.add(b["id"])
                if b["owner"] == opp:
                    b["owner"] = "N"; b["stage"] = 1; b["_pulled"] = self.turn
                else:
                    b["owner"] = team; b["stage"] = 2
                    new_owned[team].append(b)
        for team in TEAMS:
            for b in new_owned[team]:
                if b["type"] == "DEPOT" and b["id"] not in self.depot_got[team]:
                    self.depot_got[team].add(b["id"])
                    self.res[team] = min(cfg["resource"]["resource_cap"], self.res[team] + cfg["buildings"]["depot_bonus"])
        for team in TEAMS:
            self.occ[team] += self.score(team)
        # 8. 정보 공개
        for team in TEAMS:
            rv = self.revealed[team]
            for (t, k, x, y), c in self.units.items():
                if t != team:
                    continue
                for b in self.b:
                    if (b["x"], b["y"]) == (x, y):
                        rv.add(b["id"])
                    if k == "S" and max(abs(b["x"] - x), abs(b["y"] - y)) <= 2:
                        rv.add(b["id"])
            for wb in self.owned(team, "WATCH"):
                for b in self.b:
                    if max(abs(b["x"] - wb["x"]), abs(b["y"] - wb["y"])) <= 3:
                        rv.add(b["id"])
        # 9. 승리 판정
        sy, sk = self.score("Y"), self.score("K")
        yw = sk == 0 and sy * 2 > self.total
        kw = sy == 0 and sk * 2 > self.total
        if yw and not kw:
            self.winner, self.reason = "Y", "instant"
        elif kw and not yw:
            self.winner, self.reason = "K", "instant"
        elif self.turn >= CFG["total_turns"]:
            vy = (sy, self.occ["Y"], self.unit_value("Y"))
            vk = (sk, self.occ["K"], self.unit_value("K"))
            self.winner = "Y" if vy > vk else ("K" if vk > vy else "D")
            self.reason = "final"
        return self.winner

    def unit_value(self, team):
        v = CFG["tiebreak_values"]
        return sum(c * v[k] for (t, k, x, y), c in self.units.items() if t == team)


# ------------------------------------------------------------------ 봇 러너

def load_module(name, alias):
    spec = importlib.util.spec_from_file_location(alias, os.path.join(HERE, name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class InProcBot:
    def __init__(self, name, idx):
        self.mod = load_module(name, f"bot_{name}_{idx}_{random.random()}")
        self.init = None
        self.maxt = 0.0

    def start(self, init_lines):
        self.init = campus_bot.parse_init(init_lines)

    def act(self, turn_lines):
        view = campus_bot.parse_turn(turn_lines, self.init)
        t0 = time.perf_counter()
        out = self.mod.decide(view, self.init)
        self.maxt = max(self.maxt, time.perf_counter() - t0)
        return out

    def close(self):
        pass


class ProcBot:
    def __init__(self, name, idx):
        self.p = subprocess.Popen([sys.executable, os.path.join(HERE, name + ".py")], cwd=HERE,
                                  stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)
        self.maxt = 0.0

    def start(self, init_lines):
        self.p.stdin.write("\n".join(init_lines) + "\nEND\n"); self.p.stdin.flush()

    def act(self, turn_lines):
        t0 = time.perf_counter()
        self.p.stdin.write("\n".join(turn_lines) + "\nEND\n"); self.p.stdin.flush()
        out = []
        while True:
            ln = self.p.stdout.readline()
            if not ln:
                raise RuntimeError("bot died")
            ln = ln.rstrip("\n")
            if ln == "END":
                break
            out.append(ln)
        self.maxt = max(self.maxt, time.perf_counter() - t0)
        return out

    def close(self):
        try:
            self.p.stdin.close(); self.p.wait(timeout=2)
        except Exception:
            self.p.kill()


def play(bot_y, bot_k, seed, proc=False, verbose=False):
    g = Game(seed)
    cls = ProcBot if proc else InProcBot
    bots = {"Y": cls(bot_y, 0), "K": cls(bot_k, 1)}
    for t in TEAMS:
        bots[t].start(g.init_text(t))
    while g.winner is None:
        cmds = {}
        for t in TEAMS:
            cmds[t] = Game.parse_cmds(bots[t].act(g.turn_text(t)))
        g.step(cmds)
        if verbose and g.turn % 20 == 0:
            print(f"t{g.turn} score Y{g.score('Y')} K{g.score('K')} res {g.res}", file=sys.stderr)
    for b in bots.values():
        b.close()
    return g, {t: bots[t].maxt for t in TEAMS}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("a")
    ap.add_argument("b")
    ap.add_argument("--games", type=int, default=10)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--subprocess", action="store_true")
    ap.add_argument("-v", action="store_true")
    args = ap.parse_args()
    res = {"A": 0, "B": 0, "D": 0}
    maxt = 0.0
    for i in range(args.games):
        seed = args.seed + i
        # 진영을 번갈아 배정
        if i % 2 == 0:
            g, mt = play(args.a, args.b, seed, args.subprocess, args.v)
            a_team = "Y"
        else:
            g, mt = play(args.b, args.a, seed, args.subprocess, args.v)
            a_team = "K"
        b_team = "K" if a_team == "Y" else "Y"
        maxt = max(maxt, mt[a_team])
        r = "D" if g.winner == "D" else ("A" if g.winner == a_team else "B")
        res[r] += 1
        print(f"game {i} seed {seed}: {args.a}={g.score(a_team)} {args.b}={g.score(b_team)} "
              f"(총점 {g.total}) turn {g.turn} {g.reason} -> {r}")
    print(f"결과 {args.a} 승 {res['A']} / {args.b} 승 {res['B']} / 무 {res['D']}  "
          f"({args.a} 최대 응답 {maxt*1000:.1f}ms)")


if __name__ == "__main__":
    main()
