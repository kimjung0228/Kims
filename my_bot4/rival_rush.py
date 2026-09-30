"""테스트용 상대 봇: 전투병 대군 러시 + 뒤따르는 깃발병 (제출용 아님)."""
from protocol import BALANCE, spawn, move, run
from search import bfs


def decide(view, init):
    cmds = []
    me, op = view.team, view.opp
    engs = sum(b["type"] == "ENG" and b["owner"] == me for b in view.buildings)
    wc = max(2, 3 - engs)
    nf = sum(u["count"] for u in view.my_units("F"))
    res = view.my_resource
    if nf < 2 and res >= 5:
        k = min(2 - nf, res // 5)
        cmds.append(spawn("F", k)); res -= 5 * k
    if res // wc:
        cmds.append(spawn("W", res // wc))
    efl = {(u["x"], u["y"]) for u in view.units if u["team"] == op and u["kind"] == "F"}
    ebld = {(b["x"], b["y"]) for b in view.buildings if b["owner"] == op}
    notmine = {(b["x"], b["y"]) for b in view.buildings if b["owner"] != me}
    goal = efl or ebld or notmine or {init.bases[op]}
    ws = view.my_units("W")
    # 스폰된 전투병은 본진에서 같이 이동
    bx, by = init.bases[me]
    extra = res // wc
    pos = {}
    for u in ws:
        pos[(u["x"], u["y"])] = pos.get((u["x"], u["y"]), 0) + u["count"]
    if extra:
        pos[(bx, by)] = pos.get((bx, by), 0) + extra
    for (x, y), c in pos.items():
        s = bfs((x, y), goal, init)
        if s:
            cmds.append(move(x, y, "W", c, s))
    for u in view.my_units("F"):
        s = bfs((u["x"], u["y"]), notmine, init)
        if s:
            cmds.append(move(u["x"], u["y"], "F", u["count"], s))
    return cmds


if __name__ == "__main__":
    run(decide)
