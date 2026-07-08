"""Evolution Agent：进化闭环编排 + 可审计进化史 + 克制的提案机制（docs/07 E4）。

设计原则（见 docs/07 §2.3-2.4，并经一次自我质疑修正）：
- Evolution 不是"自由进化"，而是把现有散件串成显式回路 + 留可回放的进化日志。
- **参数自动变更只走既有安全校准通道**（calibrate 的两阶段 + walk-forward 门禁）。
- Eval 诊断出的系统性偏差 → 产出**带推理的提案**（logged, 不自动执行），由人工决策。

为什么偏差不自动改参数（一次自我质疑的结论）：
  Eval 的"进球偏差"衡量的是"预测比分 vs 实际总进球"，而校准优化的是"胜负/晋级
  log loss"，两者是不同目标。实测：把 base_goals 纳入校准，log loss 会选更**低**的
  2.4（锐化热门胜率、拟合本届冷门少），方向与"低估进球"相反。且比分低估本质是
  泊松众数 < 均值的显示层伪影，调 base_goals 治不了。故此类偏差记为提案，不自动执行。

安全边界：只改 model_params.json 白名单参数、必过校准门禁、evolution_log 只追加。
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from . import calibrate, predictor
from .predictor import DEFAULT_PARAMS

log = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
EVOLUTION_LOG = DATA_DIR / "evolution_log.jsonl"

GOAL_BIAS_THRESHOLD = 0.5          # 实际−预测总进球均值绝对值超此，才生成提案
BASE_GOALS_PROBE = [2.4, 2.7, 3.0, 3.3, 3.6]  # 提案分析用的探针（不自动落盘）


def diagnose(eval_report: dict | None) -> dict:
    """从 Eval 复盘读出诊断。返回是否有可提案的系统性偏差。"""
    if not eval_report or eval_report.get("n_cases", 0) < 3:
        return {"has_bias": False,
                "note": f"可复盘场次不足（{(eval_report or {}).get('n_cases', 0)}），仅做标准重校准"}
    bias = (eval_report.get("summary") or {}).get("goal_bias") or {}
    avg = bias.get("avg_actual_minus_predicted", 0.0)
    if abs(avg) >= GOAL_BIAS_THRESHOLD:
        return {"has_bias": True, "goal_bias": avg, "verdict": bias.get("verdict"),
                "note": f"Eval 诊断进球偏差 {avg:+.2f}（{bias.get('verdict')}）"}
    return {"has_bias": False, "note": "Eval 未发现系统性偏差"}


def evolve(tournament: dict, prev_prediction: dict | None = None,
           eval_report: dict | None = None) -> dict:
    """一次进化：标准安全校准（自动）+ 偏差提案（不自动执行）+ 记日志。

    不重跑预测，由调用方 pipeline 负责；finalize() 回填冠军变化。
    """
    before = _current_params()
    diag = diagnose(eval_report)

    # (1) 标准安全校准——沿用既有网格与 walk-forward 门禁，不引入偏差驱动的维度
    result = calibrate.search(tournament)
    applied = calibrate.apply(tournament, result)
    if applied:
        predictor.PARAMS.update(predictor.load_params())
    after = _current_params()

    # (2) 偏差提案——仅当 Eval 发现偏差时，分析并记录，交人工决策
    proposal = _goal_bias_proposal(tournament, result, diag) if diag["has_bias"] else None

    action = {
        "at": datetime.now(timezone.utc).isoformat(),
        "trigger": "goal_bias_proposal" if diag["has_bias"] else "scheduled_recalibration",
        "note": diag["note"],
        "matches_used": len(calibrate._played_matches(tournament)),
        "recalibration": {
            "applied": applied,
            "log_loss": {"baseline": result["baseline_log_loss"], "best": result["best_log_loss"]},
            "walk_forward": result.get("walk_forward", {}).get("best") if result.get("walk_forward") else None,
        },
        "proposal": proposal,
        "params_before": before,
        "params_after": after,
        "params_changed": _diff(before, after),
        "champion_before": _champion_of(prev_prediction),
    }
    _append_log(action)
    _log_summary(action, diag)
    return action


def _goal_bias_proposal(tournament: dict, result: dict, diag: dict) -> dict:
    """分析 base_goals 探针：诚实呈现"log loss 想怎么走"vs"偏差想怎么走"的冲突。"""
    base = dict(DEFAULT_PARAMS)
    for k in ("goal_exp", "rho", "elo_div"):
        if k in result["best"]:
            base[k] = result["best"][k]
    w_form = result["best"].get("w_form", 0.5)
    sweep = []
    for bg in BASE_GOALS_PROBE:
        p = dict(base); p["base_goals"] = bg
        sweep.append({"base_goals": bg,
                      "log_loss": round(calibrate.log_loss(tournament, p, w_form=w_form), 4)})
    ll_best = min(sweep, key=lambda s: s["log_loss"])["base_goals"]
    bias_dir = "调高 base_goals" if diag["goal_bias"] > 0 else "调低 base_goals"
    ll_dir = "调高 base_goals" if ll_best > DEFAULT_PARAMS["base_goals"] else \
             ("调低 base_goals" if ll_best < DEFAULT_PARAMS["base_goals"] else "维持 base_goals")
    return {
        "kind": "goal_bias",
        "observation": f"Eval 显示预测比分平均低估总进球 {diag['goal_bias']:+.2f} 球/场",
        "base_goals_sweep": sweep,
        "log_loss_prefers": ll_best,
        "conflict": ll_dir != bias_dir,
        "recommendation": (
            "冲突：偏差方向（{bd}）与 log loss 最优方向（{ld}）不一致。"
            "比分低估是泊松众数<均值的显示层伪影，建议在展示层并列'期望比分'，"
            "而非改 base_goals 扭曲概率模型。base_goals 变更需人工确认。"
        ).format(bd=bias_dir, ld=ll_dir) if ll_dir != bias_dir else
        f"log loss 与偏差方向一致（{ll_dir}），但仍建议人工确认后再改，避免小样本过拟合。",
        "auto_applied": False,
    }


def finalize(action: dict, new_prediction: dict) -> None:
    """预测重跑后回填冠军概率变化，补全日志最后一条。"""
    champ_after = _champion_of(new_prediction)
    delta = _champion_delta(action.get("champion_before"), champ_after)
    _patch_last_log({"champion_after": champ_after, "champion_delta": delta})


# ---------------------------------------------------------------- helpers

def _log_summary(action: dict, diag: dict) -> None:
    rc = action["recalibration"]
    if rc["applied"]:
        log.info("进化：重校准生效，log loss %s→%s，参数变更 %s",
                 rc["log_loss"]["baseline"], rc["log_loss"]["best"], action["params_changed"])
    else:
        log.info("进化：重校准改善不足，维持现有参数")
    if action["proposal"]:
        log.info("进化提案（交人工）：%s", action["proposal"]["recommendation"])


def _current_params() -> dict:
    p = dict(DEFAULT_PARAMS)
    w = {"w_form": 0.5, "w_wc": 1.0, "adj_gd": False}
    if predictor.PARAMS_FILE.exists():
        try:
            saved = json.loads(predictor.PARAMS_FILE.read_text())
            p.update(saved.get("predictor", {}))
            w.update(saved.get("rating", {}))
        except (json.JSONDecodeError, OSError):
            pass
    return {"predictor": {k: p[k] for k in ("base_goals", "goal_exp", "rho", "elo_div")},
            "rating": w}


def _diff(before: dict, after: dict) -> dict:
    changed = {}
    for section in ("predictor", "rating"):
        for k, v in after[section].items():
            if before[section].get(k) != v:
                changed[f"{section}.{k}"] = {"from": before[section].get(k), "to": v}
    return changed


def _champion_of(prediction: dict | None) -> dict | None:
    if not prediction:
        return None
    mc = prediction.get("monte_carlo", {}).get("p_champion", {})
    top3 = list(mc.items())[:3]
    return {"team": prediction.get("champion", {}).get("team"),
            "top3": [{"team": c, "p": p} for c, p in top3]}


def _champion_delta(before: dict | None, after: dict | None) -> dict | None:
    if not (before and after):
        return None
    pb = {x["team"]: x["p"] for x in before["top3"]}
    pa = {x["team"]: x["p"] for x in after["top3"]}
    return {"champion_change": None if before["team"] == after["team"]
            else {"from": before["team"], "to": after["team"]},
            "prob_shifts": {t: round(pa[t] - pb.get(t, 0), 4)
                            for t in pa if abs(pa[t] - pb.get(t, 0)) >= 0.01}}


def _append_log(action: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with EVOLUTION_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(action, ensure_ascii=False) + "\n")


def _patch_last_log(extra: dict) -> None:
    if not EVOLUTION_LOG.exists():
        return
    lines = EVOLUTION_LOG.read_text(encoding="utf-8").splitlines()
    if not lines:
        return
    try:
        last = json.loads(lines[-1])
    except json.JSONDecodeError:
        return
    last.update(extra)
    lines[-1] = json.dumps(last, ensure_ascii=False)
    EVOLUTION_LOG.write_text("\n".join(lines) + "\n", encoding="utf-8")


def read_log() -> list[dict]:
    if not EVOLUTION_LOG.exists():
        return []
    out = []
    for line in EVOLUTION_LOG.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out
