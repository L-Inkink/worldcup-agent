"""逐轮推演 + 蒙特卡洛模拟 + 回测。

- 确定性推演：已赛场次锁定真实结果，未赛场次取"最可能结果"逐轮推进到冠军。
- 蒙特卡洛：从当前真实赛况出发做 N 次全赛事采样，输出每队夺冠/进决赛/进四强概率。
- 回测：用赛前实力分（strength_pre，不含本届表现，避免数据泄漏）重新预测
  全部已赛场次，统计方向命中率作为模型可信度证据。
"""
from __future__ import annotations

import copy

import numpy as np

from .predictor import predict_match

ROUND_CHAIN = ["round_of_32", "round_of_16", "quarter_finals", "semi_finals", "final"]
N_SIMS = 10_000
SEED = 2026


def simulate(tournament: dict, ratings: dict[str, dict]) -> dict:
    bracket = copy.deepcopy(tournament["bracket"])
    strength = {code: r["strength"] for code, r in ratings.items()}

    _deterministic_run(bracket, strength)
    monte_carlo = _monte_carlo(tournament["bracket"], strength)
    backtest = _backtest(tournament, ratings)

    champion = bracket["final"][0].get("winner") or bracket["final"][0].get("predicted_winner")
    return {
        "bracket": bracket,
        "champion": champion,
        "monte_carlo": monte_carlo,
        "backtest": backtest,
    }


# ---------------------------------------------------------------- 确定性推演

def _winner_of(match: dict) -> str | None:
    return match.get("winner") or match.get("predicted_winner")


def _loser_of(match: dict) -> str | None:
    w = _winner_of(match)
    if not w:
        return None
    return match["away"] if w == match["home"] else match["home"]


def _resolve_teams(bracket: dict, match: dict, by_id: dict) -> None:
    """未确定对阵的场次，从上一轮 feeders 的（预测）胜者填充。"""
    if match.get("home") and match.get("away"):
        return
    feeders = match.get("feeders")
    if not feeders:
        return
    take = _loser_of if match.get("losers_of_feeders") else _winner_of
    match["home"] = match.get("home") or take(by_id[feeders[0]])
    match["away"] = match.get("away") or take(by_id[feeders[1]])


def _deterministic_run(bracket: dict, strength: dict[str, float]) -> None:
    by_id = {m["id"]: m for ms in bracket.values() for m in ms}
    rounds = ROUND_CHAIN[:-1] + ["third_place", "final"]
    for round_name in rounds:
        for match in bracket[round_name]:
            _resolve_teams(bracket, match, by_id)
            if match["status"] == "finished" or not (match["home"] and match["away"]):
                continue
            pred = predict_match(strength[match["home"]], strength[match["away"]], knockout=True)
            advance_home = pred["p_advance"] >= 0.5
            match["prediction"] = pred
            match["predicted_winner"] = match["home"] if advance_home else match["away"]
            match["predicted_score"] = pred["most_likely_score"]


# ---------------------------------------------------------------- 蒙特卡洛

def _monte_carlo(bracket: dict, strength: dict[str, float]) -> dict:
    rng = np.random.default_rng(SEED)
    advance_cache: dict[tuple[str, str], float] = {}

    def p_advance(a: str, b: str) -> float:
        key = (a, b)
        if key not in advance_cache:
            advance_cache[key] = predict_match(strength[a], strength[b], knockout=True)["p_advance"]
        return advance_cache[key]

    reach_semi: dict[str, int] = {}
    reach_final: dict[str, int] = {}
    champions: dict[str, int] = {}

    # 预展平结构，加速循环
    rounds = [
        [
            {
                "feeder_slots": ((m["slot"] - 1) * 2, (m["slot"] - 1) * 2 + 1),
                "home": m.get("home"), "away": m.get("away"),
                "actual_winner": m.get("winner"),
            }
            for m in bracket[rn]
        ]
        for rn in ROUND_CHAIN
    ]

    for _ in range(N_SIMS):
        prev_winners: list[str] = []
        for depth, matches in enumerate(rounds):
            winners: list[str] = []
            for m in matches:
                home, away = m["home"], m["away"]
                if home is None or away is None:
                    i, j = m["feeder_slots"]
                    home = home or prev_winners[i]
                    away = away or prev_winners[j]
                if m["actual_winner"]:
                    winners.append(m["actual_winner"])
                else:
                    p = p_advance(home, away)
                    winners.append(home if rng.random() < p else away)
                # 统计进四强/决赛（按进入该轮即计）
                if depth == len(ROUND_CHAIN) - 2:  # semi_finals 参赛者
                    reach_semi[home] = reach_semi.get(home, 0) + 1
                    reach_semi[away] = reach_semi.get(away, 0) + 1
                if depth == len(ROUND_CHAIN) - 1:  # final 参赛者
                    reach_final[home] = reach_final.get(home, 0) + 1
                    reach_final[away] = reach_final.get(away, 0) + 1
            prev_winners = winners
        champ = prev_winners[0]
        champions[champ] = champions.get(champ, 0) + 1

    def to_prob(counter: dict[str, int]) -> dict[str, float]:
        return {k: round(v / N_SIMS, 4) for k, v in sorted(counter.items(), key=lambda kv: -kv[1])}

    return {
        "n_sims": N_SIMS,
        "seed": SEED,
        "p_champion": to_prob(champions),
        "p_final": to_prob(reach_final),
        "p_semi": to_prob(reach_semi),
    }


# ---------------------------------------------------------------- 回测

def _backtest(tournament: dict, ratings: dict[str, dict]) -> dict:
    """用赛前实力分预测已赛场次，统计命中率。"""
    strength_pre = {code: r["strength_pre"] for code, r in ratings.items()}

    group_total = group_hits = 0
    for m in tournament["group_matches"]:
        if not m.get("score"):
            continue
        pred = predict_match(strength_pre[m["home"]], strength_pre[m["away"]])
        probs = {"H": pred["p_win"], "D": pred["p_draw"], "A": pred["p_loss"]}
        predicted = max(probs, key=probs.get)
        actual = "H" if m["score"][0] > m["score"][1] else ("A" if m["score"][0] < m["score"][1] else "D")
        group_total += 1
        group_hits += predicted == actual

    ko_total = ko_hits = 0
    for round_matches in tournament["bracket"].values():
        for m in round_matches:
            if m.get("status") != "finished" or not m.get("winner"):
                continue
            pred = predict_match(strength_pre[m["home"]], strength_pre[m["away"]], knockout=True)
            predicted = m["home"] if pred["p_advance"] >= 0.5 else m["away"]
            ko_total += 1
            ko_hits += predicted == m["winner"]

    total = group_total + ko_total
    hits = group_hits + ko_hits
    return {
        "note": "回测使用赛前实力分（不含本届表现），无数据泄漏",
        "group": {"matches": group_total, "hits": group_hits,
                  "accuracy": round(group_hits / group_total, 4) if group_total else None},
        "knockout": {"matches": ko_total, "hits": ko_hits,
                     "accuracy": round(ko_hits / ko_total, 4) if ko_total else None},
        "overall": {"matches": total, "hits": hits,
                    "accuracy": round(hits / total, 4) if total else None},
    }
