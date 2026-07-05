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


def _played_matches(tournament: dict) -> list[dict]:
    out = []
    for m in tournament["group_matches"]:
        if m.get("score"):
            out.append({"home": m["home"], "away": m["away"], "score": m["score"], "ko": False})
    for matches in tournament["bracket"].values():
        for m in matches:
            if m.get("status") == "finished" and m.get("winner"):
                out.append({"home": m["home"], "away": m["away"], "score": m["score"],
                            "winner": m["winner"], "ko": True})
    return out


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


def search(tournament: dict) -> dict:
    """网格搜索。返回 {baseline, best, results_top5}。"""
    baseline_params = dict(DEFAULT_PARAMS)
    baseline = log_loss(tournament, baseline_params, w_form=rating.W_FORM)

    results = []
    keys = list(GRID)
    for combo in itertools.product(*(GRID[k] for k in keys)):
        cfg = dict(zip(keys, combo))
        params = dict(DEFAULT_PARAMS)
        params.update({k: cfg[k] for k in ("goal_exp", "rho", "elo_div")})
        ll = log_loss(tournament, params, w_form=cfg["w_form"])
        results.append((ll, cfg))
    results.sort(key=lambda r: r[0])

    best_ll, best_cfg = results[0]
    return {
        "baseline_log_loss": round(baseline, 4),
        "best_log_loss": round(best_ll, 4),
        "gain": round(baseline - best_ll, 4),
        "best": best_cfg,
        "top5": [{"log_loss": round(ll, 4), **cfg} for ll, cfg in results[:5]],
    }


def apply(tournament: dict, result: dict) -> bool:
    """改善超过阈值时写入 model_params.json，返回是否落盘。"""
    if result["gain"] < MIN_GAIN:
        return False
    cfg = result["best"]
    payload = {
        "calibrated_at": datetime.now(timezone.utc).isoformat(),
        "matches_used": len(_played_matches(tournament)),
        "baseline_log_loss": result["baseline_log_loss"],
        "log_loss": result["best_log_loss"],
        "predictor": {k: cfg[k] for k in ("goal_exp", "rho", "elo_div")},
        "rating": {"w_form": cfg["w_form"]},
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
    if "--apply" in sys.argv:
        if apply(t, res):
            print(f"✅ 已写入 {PARAMS_FILE}（改善 {res['gain']}）")
        else:
            print(f"改善 {res['gain']} < 阈值 {MIN_GAIN}，维持默认参数")
    else:
        print("（加 --apply 参数以在改善显著时落盘）")
