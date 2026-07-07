"""实力评估模块：融合 Elo、FIFA 排名、近期状态、本届表现，输出综合实力分。

strength = elo
         + w_fifa * fifa_bonus        # (50 - rank) * 2，截断到 [0, 100]
         + w_form * form_1y           # eloratings 近一年评分变化（动量信号）
         + w_wc   * wc_performance    # 本届场均净胜球 * 30，截断到 [-100, 100]

F3（对手强度调整，adj_gd=True 时生效）：每场净胜球乘 opp_elo / ELO_NORM——
赢强敌的净胜球比刷弱旅更值钱。是否启用由 calibrate.py 的 walk-forward 回测决定。

回测专用的 pre-tournament 实力分（strength_pre）不含本届表现项。
walk-forward 评估可传 upto（date）：只统计该日期之前的比赛，模拟"赛前视角"。
"""
from __future__ import annotations

import json
from datetime import date

from .predictor import PARAMS_FILE

W_FIFA = 0.3
W_FORM = 0.5
W_WC = 1.0
ADJ_GD = False
ELO_NORM = 1900.0  # 本届参赛队 Elo 均值量级


def load_weights() -> dict:
    """默认权重 + 校准文件覆盖（calibrate.py 写入 model_params.json 的 rating 段）。"""
    w = {"w_fifa": W_FIFA, "w_form": W_FORM, "w_wc": W_WC, "adj_gd": ADJ_GD}
    if PARAMS_FILE.exists():
        try:
            w.update(json.loads(PARAMS_FILE.read_text()).get("rating", {}))
        except (json.JSONDecodeError, OSError):
            pass
    return w


def compute_ratings(tournament: dict, w_fifa: float | None = None,
                    w_form: float | None = None, w_wc: float | None = None,
                    adj_gd: bool | None = None, upto: date | None = None) -> dict[str, dict]:
    """返回 {code: {elo, fifa_bonus, form_1y, wc_performance, strength, strength_pre}}"""
    cal = load_weights()
    w_fifa = cal["w_fifa"] if w_fifa is None else w_fifa
    w_form = cal["w_form"] if w_form is None else w_form
    w_wc = cal["w_wc"] if w_wc is None else w_wc
    adj_gd = cal["adj_gd"] if adj_gd is None else adj_gd

    elo_by_code = {c: t["elo"] for c, t in tournament["teams"].items()}
    records = _match_records(tournament, upto)
    ratings: dict[str, dict] = {}
    for code, team in tournament["teams"].items():
        elo = team["elo"]
        fifa_bonus = max(0.0, min(100.0, (50 - team["fifa_rank"]) * 2))
        form = team.get("form_1y", 0)
        recs = records.get(code, [])
        played = len(recs)
        gd = sum(g for _, g in recs)
        if played:
            if adj_gd:
                eff_gd = sum(g * elo_by_code.get(opp, ELO_NORM) / ELO_NORM for opp, g in recs)
            else:
                eff_gd = gd
            wc_perf = max(-100.0, min(100.0, (eff_gd / played) * 30))
        else:
            wc_perf = 0.0

        strength_pre = elo + w_fifa * fifa_bonus + w_form * form
        ratings[code] = {
            "elo": elo,
            "fifa_rank": team["fifa_rank"],
            "fifa_bonus": round(fifa_bonus, 1),
            "form_1y": form,
            "wc_played": played,
            "wc_gd": gd,
            "wc_performance": round(wc_perf, 1),
            "strength_pre": round(strength_pre, 1),
            "strength": round(strength_pre + w_wc * wc_perf, 1),
        }
    return ratings


def _match_records(tournament: dict, upto: date | None = None) -> dict[str, list]:
    """每队的 (对手, 净胜球) 记录列表（90分钟口径）。

    upto 非空时只统计早于该日期的比赛（walk-forward 赛前视角）。
    """
    from .features import parse_match_date

    records: dict[str, list] = {}

    def add(m: dict) -> None:
        if upto is not None:
            d = parse_match_date(m.get("date"))
            if d is None or d >= upto:
                return
        h, a = m["home"], m["away"]
        gd = m["score"][0] - m["score"][1]
        records.setdefault(h, []).append((a, gd))
        records.setdefault(a, []).append((h, -gd))

    for m in tournament["group_matches"]:
        if m.get("score"):
            add(m)
    for round_matches in tournament["bracket"].values():
        for m in round_matches:
            if m.get("status") == "finished" and m.get("score"):
                add(m)
    return records
