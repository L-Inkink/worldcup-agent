"""比赛上下文特征（P0：从已有数据零成本推导）。

- rest_days：两队各自距上一场的休息天数（淘汰赛密集期的真实优势项）
- pens_this_wc：本届点球大战胜负记录（拖入点球时的经验参考）

特征只进入解释层（Qwen 推理上下文 + 前端量化依据），
不直接进入评分公式——评分层特征须先经回测校准验证增益（见 docs/04）。
"""
from __future__ import annotations

from datetime import date

ROUND_CHAIN = ["round_of_32", "round_of_16", "quarter_finals", "semi_finals", "final"]
_MONTHS = {"June": 6, "July": 7}


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


def annotate_context(bracket: dict) -> None:
    """为已确定双方的未赛场次写入 match['context']。

    须在确定性推演之后调用（届时后续轮次的参赛方已由预测填充）。
    """
    pens_record = _pens_record(bracket)
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
