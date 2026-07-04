"""LLM 推理解释模块（Qwen 全链路）。

- 单场解说：qwen-plus（快、成本低）
- 冠军推理长文：qwen-max（质量优先）
- 无 DASHSCOPE_API_KEY 或调用失败：降级为规则模板，功能不残缺

约束：LLM 只解释统计模型的数字结论，不产生/修改任何数字。
"""
from __future__ import annotations

import logging
import os

log = logging.getLogger(__name__)

DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
MATCH_MODEL = "qwen-plus"
REPORT_MODEL = "qwen-max"

_SYSTEM_MATCH = (
    "你是一名专业足球分析师。基于给定的量化数据，用中文写一段120字以内的比赛预测分析。"
    "只解释数据，不得更改任何数字结论，不得编造数据中没有的信息。不要使用markdown格式。"
)
_SYSTEM_REPORT = (
    "你是一名资深足球战术与数据分析专家。基于统计模型的完整推演结果撰写冠军预测报告"
    "（600-800字，中文），结构：①夺冠热门格局 ②预测冠军的晋级路径逐轮分析 ③主要威胁 ④结论。"
    "只解释数据，不得更改数字结论。可以使用简单的段落结构，不要使用markdown标题。"
)


def _client():
    api_key = os.environ.get("DASHSCOPE_API_KEY")
    if not api_key:
        return None
    try:
        from openai import OpenAI
        return OpenAI(api_key=api_key, base_url=DASHSCOPE_BASE_URL)
    except Exception:
        log.exception("failed to init DashScope client")
        return None


def _chat(client, model: str, system: str, user: str) -> str | None:
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": user}],
            temperature=0.7,
        )
        return resp.choices[0].message.content.strip()
    except Exception:
        log.exception("qwen call failed (model=%s)", model)
        return None


# ---------------------------------------------------------------- 单场解说

def explain_match(match: dict, ratings: dict, teams: dict, client=None) -> dict:
    """返回 {text, source}。match 需含 home/away/prediction。"""
    home, away = match["home"], match["away"]
    pred = match.get("prediction")
    if not (home and away and pred):
        return {"text": "", "source": "none"}

    rh, ra = ratings[home], ratings[away]
    nh, na = teams[home]["name_zh"], teams[away]["name_zh"]
    facts = (
        f"比赛：{nh} vs {na}\n"
        f"- 综合实力分：{nh} {rh['strength']}（Elo {rh['elo']}，FIFA第{rh['fifa_rank']}，"
        f"近一年Elo变化{rh['form_1y']:+d}，本届{rh['wc_played']}场净胜球{rh['wc_gd']:+d}）\n"
        f"  {na} {ra['strength']}（Elo {ra['elo']}，FIFA第{ra['fifa_rank']}，"
        f"近一年Elo变化{ra['form_1y']:+d}，本届{ra['wc_played']}场净胜球{ra['wc_gd']:+d}）\n"
        f"- 模型输出：{nh}胜率{pred['p_win']*100:.0f}%，平局{pred['p_draw']*100:.0f}%，"
        f"{na}胜率{pred['p_loss']*100:.0f}%\n"
        f"- 最可能比分：{pred['most_likely_score'][0]}比{pred['most_likely_score'][1]}"
        f"；{nh}晋级概率{pred.get('p_advance', pred['p_win'])*100:.0f}%\n"
        f"请解释为什么模型给出这一预测。"
    )
    if client:
        text = _chat(client, MATCH_MODEL, _SYSTEM_MATCH, facts)
        if text:
            return {"text": text, "source": "qwen"}
    return {"text": _template_match(match, rh, ra, nh, na), "source": "template"}


def _template_match(match: dict, rh: dict, ra: dict, nh: str, na: str) -> str:
    pred = match["prediction"]
    gap = rh["strength"] - ra["strength"]
    stronger, weaker = (nh, na) if gap >= 0 else (na, nh)
    s = abs(gap)
    level = "明显占优" if s > 150 else ("略占上风" if s > 50 else "势均力敌")
    win_side_p = max(pred.get("p_advance", pred["p_win"]), 1 - pred.get("p_advance", pred["p_win"]))
    parts = [
        f"综合实力分{stronger}高出{weaker} {s:.0f}分（{level}）。",
        f"实力差主要来自Elo基础分（{rh['elo']} vs {ra['elo']}）与本届状态"
        f"（净胜球{rh['wc_gd']:+d} vs {ra['wc_gd']:+d}）。",
        f"泊松模型给出最可能比分{pred['most_likely_score'][0]}比{pred['most_likely_score'][1]}，"
        f"{stronger}晋级概率约{win_side_p*100:.0f}%。",
    ]
    if pred.get("decided_in_extra"):
        parts.append("常规时间大概率难分胜负，预计需要加时或点球分出晋级方。")
    return "".join(parts)


# ---------------------------------------------------------------- 冠军报告

def champion_report(sim_result: dict, ratings: dict, teams: dict, client=None) -> dict:
    champion = sim_result["champion"]
    mc = sim_result["monte_carlo"]
    bt = sim_result["backtest"]
    name = teams[champion]["name_zh"]

    odds_lines = [
        f"{teams[c]['name_zh']} {p*100:.1f}%"
        for c, p in list(mc["p_champion"].items())[:8]
    ]
    path = _champion_path(sim_result["bracket"], champion, teams)
    facts = (
        f"蒙特卡洛{mc['n_sims']}次模拟夺冠概率Top8：{'，'.join(odds_lines)}\n"
        f"确定性推演（每场取最可能结果）冠军：{name}"
        f"（蒙特卡洛夺冠概率{mc['p_champion'].get(champion, 0)*100:.1f}%）\n"
        f"其晋级路径与各场预测：\n" + "\n".join(path) + "\n"
        f"模型对已赛{bt['overall']['matches']}场回测方向命中率"
        f"{bt['overall']['accuracy']*100:.0f}%（淘汰赛{bt['knockout']['accuracy']*100:.0f}%）"
    )
    if client:
        text = _chat(client, REPORT_MODEL, _SYSTEM_REPORT, facts)
        if text:
            return {"text": text, "source": "qwen", "facts": facts}
    return {"text": _template_report(name, mc, bt, path, teams), "source": "template", "facts": facts}


def _champion_path(bracket: dict, champion: str, teams: dict) -> list[str]:
    round_names = {"round_of_32": "32强", "round_of_16": "16强", "quarter_finals": "8强",
                   "semi_finals": "半决赛", "final": "决赛"}
    lines = []
    for rn, label in round_names.items():
        for m in bracket[rn]:
            if champion not in (m.get("home"), m.get("away")):
                continue
            opp = m["away"] if m["home"] == champion else m["home"]
            if not opp:
                continue
            opp_name = teams[opp]["name_zh"]
            if m["status"] == "finished":
                s = m["score"]
                extra = "（点球）" if m.get("pens") else ("（加时）" if m.get("aet") else "")
                lines.append(f"{label}：已胜{opp_name} {s[0]}比{s[1]}{extra}"
                             if m["winner"] == champion else
                             f"{label}：负于{opp_name}")
            else:
                pred = m.get("prediction", {})
                ml = pred.get("most_likely_score", ["?", "?"])
                p = pred.get("p_advance", 0.5)
                p_champ_side = p if m["home"] == champion else 1 - p
                lines.append(f"{label}：预测胜{opp_name}（最可能比分{ml[0]}比{ml[1]}，"
                             f"晋级概率{p_champ_side*100:.0f}%）")
    return lines


def _template_report(name: str, mc: dict, bt: dict, path: list[str], teams: dict) -> str:
    top3 = list(mc["p_champion"].items())[:3]
    top3_txt = "、".join(f"{teams[c]['name_zh']}（{p*100:.1f}%）" for c, p in top3)
    return (
        f"基于{mc['n_sims']}次蒙特卡洛模拟，当前夺冠格局前三为：{top3_txt}。"
        f"确定性推演（每轮取最可能结果）显示{name}将最终夺冠。\n\n"
        f"{name}的预测晋级路径：\n" + "\n".join(path) + "\n\n"
        f"模型可信度：对本届已赛{bt['overall']['matches']}场比赛的回测方向命中率为"
        f"{bt['overall']['accuracy']*100:.0f}%，其中淘汰赛命中率{bt['knockout']['accuracy']*100:.0f}%。"
        f"（提示：配置 DASHSCOPE_API_KEY 可获得 Qwen 生成的深度推理报告）"
    )


# ---------------------------------------------------------------- 批量入口

def annotate(sim_result: dict, ratings: dict, teams: dict, use_llm: bool = True) -> dict:
    """为所有未赛场次生成解说，并生成冠军报告。返回 reasoning 元信息。"""
    client = _client() if use_llm else None
    source = "qwen" if client else "template"

    for round_matches in sim_result["bracket"].values():
        for m in round_matches:
            if m.get("prediction"):
                m["reasoning"] = explain_match(m, ratings, teams, client)

    report = champion_report(sim_result, ratings, teams, client)
    sim_result["champion_report"] = report
    return {"reasoning_source": source}
