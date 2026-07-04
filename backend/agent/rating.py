"""实力评估模块：融合 Elo、FIFA 排名、近期状态、本届表现，输出综合实力分。

strength = elo
         + W_FIFA * fifa_bonus        # (50 - rank) * 2，截断到 [0, 100]
         + W_FORM * form_1y           # eloratings 近一年评分变化（动量信号）
         + W_WC   * wc_performance    # 本届场均净胜球 * 30，截断到 [-100, 100]

回测专用的 pre-tournament 实力分（strength_pre）不含本届表现项，
避免用比赛结果预测比赛自身的数据泄漏。
"""
from __future__ import annotations

W_FIFA = 0.3
W_FORM = 0.5
W_WC = 1.0


def compute_ratings(tournament: dict) -> dict[str, dict]:
    """返回 {code: {elo, fifa_bonus, form_1y, wc_performance, strength, strength_pre}}"""
    per_team_stats = _tournament_stats(tournament)
    ratings: dict[str, dict] = {}
    for code, team in tournament["teams"].items():
        elo = team["elo"]
        fifa_bonus = max(0.0, min(100.0, (50 - team["fifa_rank"]) * 2))
        form = team.get("form_1y", 0)
        played, gd = per_team_stats.get(code, (0, 0))
        wc_perf = max(-100.0, min(100.0, (gd / played) * 30)) if played else 0.0

        strength_pre = elo + W_FIFA * fifa_bonus + W_FORM * form
        ratings[code] = {
            "elo": elo,
            "fifa_rank": team["fifa_rank"],
            "fifa_bonus": round(fifa_bonus, 1),
            "form_1y": form,
            "wc_played": played,
            "wc_gd": gd,
            "wc_performance": round(wc_perf, 1),
            "strength_pre": round(strength_pre, 1),
            "strength": round(strength_pre + W_WC * wc_perf, 1),
        }
    return ratings


def _tournament_stats(tournament: dict) -> dict[str, tuple[int, int]]:
    """统计每队本届已赛场次与总净胜球（小组赛 + 已完成的淘汰赛，90分钟口径）。"""
    stats: dict[str, list[int]] = {}

    def add(code: str, gf: int, ga: int) -> None:
        s = stats.setdefault(code, [0, 0])
        s[0] += 1
        s[1] += gf - ga

    for m in tournament["group_matches"]:
        if m.get("score"):
            add(m["home"], m["score"][0], m["score"][1])
            add(m["away"], m["score"][1], m["score"][0])
    for round_matches in tournament["bracket"].values():
        for m in round_matches:
            if m.get("status") == "finished" and m.get("score"):
                add(m["home"], m["score"][0], m["score"][1])
                add(m["away"], m["score"][1], m["score"][0])
    return {code: (s[0], s[1]) for code, s in stats.items()}
