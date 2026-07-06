"""比赛上下文特征（P0：从已有数据零成本推导）。

- rest_days：两队各自距上一场的休息天数（淘汰赛密集期的真实优势项）
- pens_this_wc：本届点球大战胜负记录（拖入点球时的经验参考）

特征只进入解释层（Qwen 推理上下文 + 前端量化依据），
不直接进入评分公式——评分层特征须先经回测校准验证增益（见 docs/04）。
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

ROUND_CHAIN = ["round_of_32", "round_of_16", "quarter_finals", "semi_finals", "final"]
_MONTHS = {"June": 6, "July": 7}

KEY_PLAYERS_FILE = Path(__file__).resolve().parent.parent / "data" / "key_players.json"

_STATUS_ZH = {"fit": "可出战", "doubt": "出战成疑", "out": "伤停缺阵"}


def load_key_players() -> dict[str, list[dict]]:
    """人工维护的核心球员可用性表（P1，仅供推理解释层）。"""
    if not KEY_PLAYERS_FILE.exists():
        return {}
    try:
        return json.loads(KEY_PLAYERS_FILE.read_text()).get("teams", {})
    except (json.JSONDecodeError, OSError):
        return {}


def key_players_line(code: str, players: dict[str, list[dict]]) -> str | None:
    """'姆巴佩（前锋，可出战）、格列兹曼（前场自由人，可出战）'"""
    rows = players.get(code)
    if not rows:
        return None
    return "、".join(f"{p['name']}（{p['role']}，{_STATUS_ZH.get(p['status'], p['status'])}）"
                     for p in rows)


def parse_match_date(s: str | None) -> date | None:
    """'July 4' -> date(2026, 7, 4)"""
    if not s:
        return None
    parts = s.split()
    if len(parts) != 2 or parts[0] not in _MONTHS:
        return None
    try:
        return date(2026, _MONTHS[parts[0]], int(parts[1]))
    except ValueError:
        return None


# ---------------------------------------------------------------- M0：停赛风险与首发稳定性

DEFENSE_POS = {"RB", "CB", "LB", "SW", "RWB", "LWB", "DF"}


def team_lineup_history(tournament: dict) -> dict[str, list[list[dict]]]:
    """每队按时间序的阵容列表（小组赛在前，已完成的淘汰赛在后）。"""
    details = tournament.get("match_details") or {}
    hist: dict[str, list[list[dict]]] = {}
    seq = list(tournament["group_matches"])
    for rn in ROUND_CHAIN:
        seq += [m for m in tournament["bracket"][rn] if m.get("status") == "finished"]
    for m in seq:
        d = details.get(f"{m['home']}-{m['away']}")
        if not d:
            continue
        for side, code in (("home", m["home"]), ("away", m["away"])):
            hist.setdefault(code, []).append(d[side])
    return hist


def team_discipline(history: list[list[dict]]) -> dict:
    """停赛/黄牌预警（近似规则：累计2黄即停赛一场，黄牌四强前不清零）。

    - suspended_next：最近一场领到红牌，或在最近一场达到第2张累计黄牌
    - at_risk：当前累计1张黄牌的最近一场首发球员（再染黄将停赛）
    """
    yellows: dict[str, int] = {}
    reached_two_last, red_last = set(), set()
    for i, match_players in enumerate(history):
        is_last = i == len(history) - 1
        for p in match_players:
            before = yellows.get(p["name"], 0)
            after = before + p["yellows"]
            yellows[p["name"]] = after
            if is_last and p["red"]:
                red_last.add(p["name"])
            if is_last and before < 2 <= after:
                reached_two_last.add(p["name"])
    last_starters = {p["name"] for p in history[-1] if p["starter"]} if history else set()
    at_risk = sorted(n for n, c in yellows.items() if c == 1 and n in last_starters)[:5]
    return {
        "suspended_next": sorted(reached_two_last | red_last),
        "at_risk": at_risk,
    }


def lineup_stability(history: list[list[dict]]) -> dict | None:
    """首发稳定性：上场轮换人数 + 后防组合连续未变场次。"""
    if len(history) < 2:
        return None
    xis = [{p["name"] for p in match if p["starter"]} for match in history]
    defenses = [{p["name"] for p in match if p["starter"] and p["pos"] in DEFENSE_POS}
                for match in history]
    stable = 1
    for i in range(len(defenses) - 2, -1, -1):
        if defenses[i] == defenses[-1]:
            stable += 1
        else:
            break
    return {
        "xi_changes_last": len(xis[-1] - xis[-2]),
        "back_line_stable_matches": stable,
    }


def annotate_context(bracket: dict, tournament: dict | None = None) -> None:
    """为已确定双方的未赛场次写入 match['context']。

    须在确定性推演之后调用（届时后续轮次的参赛方已由预测填充）。
    传入 tournament（含 match_details）时额外计算停赛风险与首发稳定性。
    """
    pens_record = _pens_record(bracket)
    lineup_hist = team_lineup_history(tournament) if tournament else {}
    discipline_done: set[str] = set()  # 停赛只影响下一场，仅注入每队最近的未赛场次
    last_played: dict[str, date] = {}

    for round_name in ROUND_CHAIN:
        for m in bracket[round_name]:
            d = parse_match_date(m.get("date"))
            home, away = m.get("home"), m.get("away")
            if m["status"] != "finished" and home and away and d:
                ctx: dict = {}
                rest = {}
                for side, code in (("home", home), ("away", away)):
                    if code in last_played:
                        rest[side] = (d - last_played[code]).days
                if len(rest) == 2:
                    ctx["rest_days"] = rest
                pens = {s: pens_record.get(c) for s, c in (("home", home), ("away", away))
                        if pens_record.get(c)}
                if pens:
                    ctx["pens_this_wc"] = pens
                discipline, lineup = {}, {}
                for side, code in (("home", home), ("away", away)):
                    h = lineup_hist.get(code)
                    if not h:
                        continue
                    if code not in discipline_done:
                        discipline_done.add(code)
                        disc = team_discipline(h)
                        if disc["suspended_next"] or disc["at_risk"]:
                            discipline[side] = disc
                    stab = lineup_stability(h)
                    if stab:
                        lineup[side] = stab
                if discipline:
                    ctx["discipline"] = discipline
                if lineup:
                    ctx["lineup"] = lineup
                if ctx:
                    m["context"] = ctx
            if d and home and away:
                last_played[home] = d
                last_played[away] = d


def _pens_record(bracket: dict) -> dict[str, dict]:
    """{team: {'won': n, 'lost': n}}，来自本届已完成的点球大战。"""
    record: dict[str, dict] = {}
    for matches in bracket.values():
        for m in matches:
            if m.get("status") == "finished" and m.get("pens"):
                loser = m["away"] if m["winner"] == m["home"] else m["home"]
                record.setdefault(m["winner"], {"won": 0, "lost": 0})["won"] += 1
                record.setdefault(loser, {"won": 0, "lost": 0})["lost"] += 1
    return record
