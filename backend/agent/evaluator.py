"""Eval Agent：预测留档 + 复盘评估（docs/07 E1/E2）。

元层模块，不侵入五模块流水线。两个入口：

- record_predictions(prediction)：每次 pipeline 跑完，把未赛场次的预测追加到
  prediction_ledger.jsonl（一行一条）。复盘时取每场开赛前最后一条。
- evaluate()：对账本中"有赛前预测且已完赛"的比赛做结果层/概率层/汇总层复盘，
  产出 eval_report.json。推理层（Qwen 判因素应验）见 E5，此处预留接口。
"""
from __future__ import annotations

import json
import logging
import math
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"
LEDGER_FILE = DATA_DIR / "prediction_ledger.jsonl"
EVAL_FILE = OUTPUT_DIR / "eval_report.json"

EPS = 1e-9


# ---------------------------------------------------------------- E1：预测留档

def record_predictions(prediction: dict) -> int:
    """把当前所有未赛场次的预测快照追加进账本。返回新增条数。

    幂等保护：同一 (match_id, param_version) 已存在则跳过，避免同参数重复留档。
    """
    param_version = _param_version(prediction)
    existing = {(r["match_id"], r["param_version"]) for r in _read_ledger()}
    rows = []
    for round_name, matches in prediction["bracket"].items():
        for m in matches:
            if m.get("status") != "scheduled" or not m.get("prediction"):
                continue
            if not (m.get("home") and m.get("away")):
                continue
            key = (m["id"], param_version)
            if key in existing:
                continue
            pred = m["prediction"]
            rows.append({
                "match_id": m["id"],
                "round": round_name,
                "recorded_at": prediction["generated_at"],
                "param_version": param_version,
                "home": m["home"],
                "away": m["away"],
                "date": m.get("date"),
                "predicted_score": m.get("predicted_score"),
                "predicted_winner": m.get("predicted_winner"),
                "p_advance": pred.get("p_advance"),
                "p_win": pred.get("p_win"),
                "p_draw": pred.get("p_draw"),
                "p_loss": pred.get("p_loss"),
                "reasoning": (m.get("reasoning") or {}).get("text", "")[:280],
            })
    if rows:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with LEDGER_FILE.open("a", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        log.info("留档 %d 条预测到 %s", len(rows), LEDGER_FILE.name)
    return len(rows)


def _param_version(prediction: dict) -> str:
    mp = prediction.get("model_params", {})
    return mp.get("calibrated_at") or mp.get("source", "default")


def _read_ledger() -> list[dict]:
    if not LEDGER_FILE.exists():
        return []
    rows = []
    for line in LEDGER_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


# ---------------------------------------------------------------- E2：复盘评估

def evaluate(prediction: dict) -> dict:
    """对账本中已完赛的比赛做复盘。prediction 提供实际赛果。"""
    actuals = _finished_matches(prediction)
    teams = prediction["teams"]
    ledger = _read_ledger()

    # 每场取开赛前最后一条预测（recorded_at 最新的一条）
    pre_by_match: dict[str, dict] = {}
    for r in sorted(ledger, key=lambda x: x["recorded_at"]):
        if r["match_id"] in actuals:
            a = actuals[r["match_id"]]
            if r["home"] == a["home"] and r["away"] == a["away"]:
                pre_by_match[r["match_id"]] = r

    cases = []
    for mid, pre in pre_by_match.items():
        cases.append(_eval_case(pre, actuals[mid], teams))
    cases.sort(key=lambda c: c["date"] or "")

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "n_cases": len(cases),
        "summary": _summarize(cases),
        "calibration": _calibration(cases),
        "cases": cases,
    }
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    EVAL_FILE.write_text(json.dumps(report, ensure_ascii=False, indent=1))
    return report


def _finished_matches(prediction: dict) -> dict[str, dict]:
    out = {}
    for matches in prediction["bracket"].values():
        for m in matches:
            if m.get("status") == "finished" and m.get("winner"):
                out[m["id"]] = m
    return out


def _eval_case(pre: dict, actual: dict, teams: dict) -> dict:
    ps, ac = pre.get("predicted_score"), actual["score"]
    pw, aw = pre.get("predicted_winner"), actual["winner"]
    # 概率层用"实际晋级方"的赛前概率；展示层用"预测晋级方"的赛前置信度
    p_adv = pre.get("p_advance")
    p_for_actual = p_for_predicted = None
    if p_adv is not None:
        p_for_actual = p_adv if aw == pre["home"] else 1 - p_adv
        p_for_predicted = p_adv if pw == pre["home"] else 1 - p_adv

    case = {
        "match_id": pre["match_id"],
        "round": pre["round"],
        "date": pre.get("date"),
        "home": pre["home"], "away": pre["away"],
        "home_zh": teams[pre["home"]]["name_zh"], "away_zh": teams[pre["away"]]["name_zh"],
        "predicted_score": ps, "actual_score": ac,
        "predicted_winner": pw, "actual_winner": aw,
        "winner_hit": pw == aw,
        "exact_score": ps == ac if ps else None,
        "gd_error": abs((ps[0] - ps[1]) - (ac[0] - ac[1])) if ps else None,
        "total_goals_error": abs((ps[0] + ps[1]) - (ac[0] + ac[1])) if ps else None,
        "p_advance_for_winner": round(p_for_actual, 4) if p_for_actual is not None else None,
        "pred_confidence": round(p_for_predicted, 4) if p_for_predicted is not None else None,
        "log_loss": round(-math.log(max(p_for_actual, EPS)), 4) if p_for_actual is not None else None,
        "brier": round((1 - p_for_actual) ** 2, 4) if p_for_actual is not None else None,
        "reasoning": pre.get("reasoning", ""),
        "recorded_at": pre["recorded_at"],
    }
    return case


def _summarize(cases: list[dict]) -> dict:
    if not cases:
        return {"note": "账本中暂无可复盘场次（需赛前预测过且已完赛）"}
    n = len(cases)
    winner_hits = sum(c["winner_hit"] for c in cases)
    gd_errs = [c["gd_error"] for c in cases if c["gd_error"] is not None]
    tg_errs = [c["total_goals_error"] for c in cases if c["total_goals_error"] is not None]
    lls = [c["log_loss"] for c in cases if c["log_loss"] is not None]
    briers = [c["brier"] for c in cases if c["brier"] is not None]
    exact = sum(1 for c in cases if c["exact_score"])

    # 系统性偏差：预测总进球 vs 实际总进球
    goal_bias = None
    diffs = [(sum(c["actual_score"]) - sum(c["predicted_score"]))
             for c in cases if c["predicted_score"]]
    if diffs:
        avg = sum(diffs) / len(diffs)
        goal_bias = {
            "avg_actual_minus_predicted": round(avg, 2),
            "verdict": ("模型系统性低估进球" if avg > 0.5
                        else "模型系统性高估进球" if avg < -0.5 else "无明显偏差"),
        }
    return {
        "cases": n,
        "winner_accuracy": round(winner_hits / n, 4),
        "winner_hits": winner_hits,
        "exact_score_hits": exact,
        "avg_gd_error": round(sum(gd_errs) / len(gd_errs), 2) if gd_errs else None,
        "avg_total_goals_error": round(sum(tg_errs) / len(tg_errs), 2) if tg_errs else None,
        "avg_log_loss": round(sum(lls) / len(lls), 4) if lls else None,
        "avg_brier": round(sum(briers) / len(briers), 4) if briers else None,
        "goal_bias": goal_bias,
    }


def _calibration(cases: list[dict]) -> list[dict]:
    """按晋级方赛前置信度分桶，比较预测概率均值 vs 实际命中率（校准表）。"""
    buckets = [(0.5, 0.6), (0.6, 0.7), (0.7, 0.8), (0.8, 0.9), (0.9, 1.01)]
    out = []
    for lo, hi in buckets:
        # 用"预测晋级方"视角的置信度（max(p_adv, 1-p_adv)）
        members = []
        for c in cases:
            p = c["p_advance_for_winner"]
            if p is None:
                continue
            conf = p if c["winner_hit"] else 1 - p  # 预测方的赛前置信度
            if lo <= conf < hi:
                members.append(c)
        if not members:
            continue
        confs = []
        for c in members:
            p = c["p_advance_for_winner"]
            confs.append(p if c["winner_hit"] else 1 - p)
        hits = sum(c["winner_hit"] for c in members)
        out.append({
            "bucket": f"{int(lo*100)}-{int(hi*100)}%",
            "n": len(members),
            "avg_predicted_conf": round(sum(confs) / len(confs), 3),
            "actual_hit_rate": round(hits / len(members), 3),
        })
    return out


def load_report() -> dict | None:
    if EVAL_FILE.exists():
        return json.loads(EVAL_FILE.read_text())
    return None


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    from . import pipeline
    pred = pipeline.load() or pipeline.run()
    report = evaluate(pred)
    s = report["summary"]
    print(f"可复盘场次: {report['n_cases']}")
    if report["n_cases"]:
        print(f"晋级方命中率: {s['winner_accuracy']*100:.0f}% ({s['winner_hits']}/{s['cases']})")
        print(f"平均净胜球误差: {s['avg_gd_error']} | 平均对数损失: {s['avg_log_loss']}")
        if s.get("goal_bias"):
            print(f"进球偏差: {s['goal_bias']['verdict']}（实际-预测均值 {s['goal_bias']['avg_actual_minus_predicted']}）")
        print("校准表:")
        for b in report["calibration"]:
            print(f"  {b['bucket']}: 预测均值 {b['avg_predicted_conf']} vs 实际命中 {b['actual_hit_rate']}（n={b['n']}）")
