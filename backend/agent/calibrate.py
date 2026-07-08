"""回测驱动的参数校准：在已赛场次上网格搜索最优模型参数。

目标函数：平均对数损失（log loss，越低越好）
- 小组赛（72场）：三向（胜/平/负）
- 淘汰赛已赛场次：二向（晋级方）
预测一律使用赛前实力分（strength_pre），无数据泄漏。

搜索空间刻意保持小（4个参数、共几百组合）以避免 88 个样本上的过拟合；
仅当最优组合比默认参数改善超过 MIN_GAIN 时才写入 model_params.json。

用法：python -m agent.calibrate [--apply]
"""
from __future__ import annotations

import itertools
import json
import math
import sys
from datetime import datetime, timezone

from . import collector, rating
from .predictor import DEFAULT_PARAMS, PARAMS_FILE, predict_match

MIN_GAIN = 0.005   # 平均log loss至少改善此值才落盘（防噪声）
EPS = 1e-9

GRID = {
    "goal_exp": [0.7, 0.85, 1.0, 1.15],
    "rho": [-0.12, -0.06, 0.0],
    "elo_div": [320.0, 400.0, 480.0],
    "w_form": [0.0, 0.5, 1.0],
}

# 阶段2（F3）：本届表现项的 walk-forward 搜索空间
WC_GRID = {
    "w_wc": [0.0, 0.5, 1.0, 1.5],
    "adj_gd": [False, True],
}
WC_BASELINE = {"w_wc": 1.0, "adj_gd": False}


def _played_matches(tournament: dict) -> list[dict]:
    out = []
    for m in tournament["group_matches"]:
        if m.get("score"):
            out.append({"home": m["home"], "away": m["away"], "score": m["score"],
                        "date": m.get("date"), "ko": False})
    for matches in tournament["bracket"].values():
        for m in matches:
            if m.get("status") == "finished" and m.get("winner"):
                out.append({"home": m["home"], "away": m["away"], "score": m["score"],
                            "date": m.get("date"), "winner": m["winner"], "ko": True})
    return out


def _match_log_loss(pred: dict, m: dict) -> float:
    if m["ko"]:
        p = pred["p_advance"] if m["winner"] == m["home"] else 1 - pred["p_advance"]
    else:
        h, a = m["score"]
        p = pred["p_win"] if h > a else (pred["p_loss"] if h < a else pred["p_draw"])
    return -math.log(max(p, EPS))


def walk_forward_log_loss(tournament: dict, params: dict, w_fifa: float, w_form: float,
                          w_wc: float, adj_gd: bool) -> float | None:
    """F3 前瞻评估：逐场只用该场开赛前已完赛的比赛计算实力（含本届表现项）。

    与 log_loss()（纯赛前实力）不同，这里诚实评估 wc_performance 的前瞻价值。
    需要比赛带日期（F2 之后的快照）；日期覆盖不足时返回 None。
    """
    from .features import parse_match_date

    dated = [(parse_match_date(m.get("date")), m) for m in _played_matches(tournament)]
    dated = [(d, m) for d, m in dated if d]
    if len(dated) < 30:
        return None
    dated.sort(key=lambda x: x[0])

    ratings_cache: dict = {}
    total, n = 0.0, 0
    for d, m in dated:
        if d not in ratings_cache:
            ratings_cache[d] = rating.compute_ratings(
                tournament, w_fifa=w_fifa, w_form=w_form, w_wc=w_wc,
                adj_gd=adj_gd, upto=d)
        r = ratings_cache[d]
        pred = predict_match(r[m["home"]]["strength"], r[m["away"]]["strength"],
                             knockout=m["ko"], params=params)
        total += _match_log_loss(pred, m)
        n += 1
    return total / n


def log_loss(tournament: dict, params: dict, w_form: float, w_fifa: float = rating.W_FIFA) -> float:
    """给定参数组合在全部已赛场次上的平均对数损失。"""
    ratings = rating.compute_ratings(tournament, w_fifa=w_fifa, w_form=w_form)
    pre = {c: r["strength_pre"] for c, r in ratings.items()}
    total, n = 0.0, 0
    for m in _played_matches(tournament):
        pred = predict_match(pre[m["home"]], pre[m["away"]], knockout=m["ko"], params=params)
        if m["ko"]:
            p = pred["p_advance"] if m["winner"] == m["home"] else 1 - pred["p_advance"]
        else:
            h, a = m["score"]
            p = pred["p_win"] if h > a else (pred["p_loss"] if h < a else pred["p_draw"])
        total += -math.log(max(p, EPS))
        n += 1
    return total / n


# 阶段1可进入 predictor 参数的维度（Evolution 可扩展 base_goals）
PREDICTOR_KEYS = ("goal_exp", "rho", "elo_div", "base_goals")


def search(tournament: dict, grid: dict | None = None) -> dict:
    """网格搜索。grid 缺省用 GRID；Evolution 可注入扩展网格（如加 base_goals）。"""
    grid = grid or GRID
    baseline_params = dict(DEFAULT_PARAMS)
    baseline = log_loss(tournament, baseline_params, w_form=rating.W_FORM)

    results = []
    keys = list(grid)
    for combo in itertools.product(*(grid[k] for k in keys)):
        cfg = dict(zip(keys, combo))
        params = dict(DEFAULT_PARAMS)
        params.update({k: cfg[k] for k in PREDICTOR_KEYS if k in cfg})
        ll = log_loss(tournament, params, w_form=cfg.get("w_form", rating.W_FORM))
        results.append((ll, cfg))
    results.sort(key=lambda r: r[0])

    best_ll, best_cfg = results[0]
    out = {
        "baseline_log_loss": round(baseline, 4),
        "best_log_loss": round(best_ll, 4),
        "gain": round(baseline - best_ll, 4),
        "best": best_cfg,
        "top5": [{"log_loss": round(ll, 4), **cfg} for ll, cfg in results[:5]],
    }

    # 阶段2（F3）：固定阶段1最优参数，walk-forward 搜索本届表现项
    params = dict(DEFAULT_PARAMS)
    params.update({k: best_cfg[k] for k in PREDICTOR_KEYS if k in best_cfg})
    wf_results = []
    for w_wc in WC_GRID["w_wc"]:
        for adj in WC_GRID["adj_gd"]:
            ll = walk_forward_log_loss(tournament, params, rating.W_FIFA,
                                       best_cfg["w_form"], w_wc, adj)
            if ll is not None:
                wf_results.append((ll, {"w_wc": w_wc, "adj_gd": adj}))
    if wf_results:
        wf_results.sort(key=lambda r: r[0])
        wf_baseline = next((ll for ll, c in wf_results if c == WC_BASELINE), None)
        wf_best_ll, wf_best = wf_results[0]
        out["walk_forward"] = {
            "baseline": round(wf_baseline, 4) if wf_baseline is not None else None,
            "best_log_loss": round(wf_best_ll, 4),
            "gain": round(wf_baseline - wf_best_ll, 4) if wf_baseline is not None else 0.0,
            "best": wf_best,
            "all": [{"log_loss": round(ll, 4), **c} for ll, c in wf_results],
        }
    return out


def apply(tournament: dict, result: dict) -> bool:
    """改善超过阈值时写入 model_params.json，返回是否落盘。"""
    if result["gain"] < MIN_GAIN:
        return False
    cfg = result["best"]
    rating_cfg = {"w_form": cfg["w_form"]}
    wf = result.get("walk_forward")
    if wf and wf["gain"] >= MIN_GAIN:
        rating_cfg.update(wf["best"])  # F3：walk-forward 证明有增益才启用
    payload = {
        "calibrated_at": datetime.now(timezone.utc).isoformat(),
        "matches_used": len(_played_matches(tournament)),
        "baseline_log_loss": result["baseline_log_loss"],
        "log_loss": result["best_log_loss"],
        "walk_forward": {k: wf[k] for k in ("baseline", "best_log_loss", "gain", "best")} if wf else None,
        "predictor": {k: cfg[k] for k in PREDICTOR_KEYS if k in cfg},
        "rating": rating_cfg,
    }
    PARAMS_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=1))
    return True


if __name__ == "__main__":
    t = collector.collect()
    res = search(t)
    print(f"样本数: {len(_played_matches(t))} 场")
    print(f"默认参数 log loss: {res['baseline_log_loss']}")
    print("Top5 组合:")
    for row in res["top5"]:
        print("  ", row)
    wf = res.get("walk_forward")
    if wf:
        print(f"walk-forward（F3，赛前视角含本届表现）: 基线 {wf['baseline']} → 最优 {wf['best_log_loss']}"
              f"（{wf['best']}，增益 {wf['gain']}）")
        for row in wf["all"]:
            print("  ", row)
    else:
        print("walk-forward: 日期覆盖不足，跳过（需先在线刷新快照获取小组赛日期）")
    if "--apply" in sys.argv:
        if apply(t, res):
            print(f"✅ 已写入 {PARAMS_FILE}（改善 {res['gain']}）")
        else:
            print(f"改善 {res['gain']} < 阈值 {MIN_GAIN}，维持默认参数")
    else:
        print("（加 --apply 参数以在改善显著时落盘）")
