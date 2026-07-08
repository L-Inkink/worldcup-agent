"""流水线编排：采集 → 实力评估 → 推演预测 → LLM 解释 → 落盘。

用法：
    python -m agent.pipeline              # 使用快照（如有），全流程离线可跑
    python -m agent.pipeline --refresh    # 强制在线重新采集
"""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import (collector, evaluator, evolution, features, predictor,
               rating, reasoner, simulator)

log = logging.getLogger(__name__)

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"
OUTPUT_FILE = OUTPUT_DIR / "prediction.json"


def run(force_refresh: bool = False, use_llm: bool = True) -> dict:
    log.info("step 1/4 数据采集 ...")
    tournament = collector.collect(force_refresh=force_refresh)

    evo_action = None
    if force_refresh:
        # Evolution Agent 编排闭环（docs/07 E4）：读上轮 Eval 诊断 → 依诊断决定进化动作
        # → 校准（改善超阈值才落盘）→ 记进化日志。预测重跑后 finalize 回填冠军变化。
        log.info("step 1b Evolution 进化闭环 ...")
        try:
            prev_prediction = load()
            prev_eval = evaluator.load_report()
            evo_action = evolution.evolve(tournament, prev_prediction, prev_eval)
        except Exception:
            log.exception("进化失败，维持现有参数")

    log.info("step 2/4 实力评估 ...")
    ratings = rating.compute_ratings(tournament)

    log.info("step 3/4 逐轮推演 + 蒙特卡洛 ...")
    sim = simulator.simulate(tournament, ratings)
    features.annotate_context(sim["bracket"], tournament)

    log.info("step 4/4 推理解释（%s）...", "Qwen" if use_llm else "模板")
    meta = reasoner.annotate(sim, ratings, tournament["teams"], use_llm=use_llm)

    prediction = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "data_source": tournament["source"],
        "data_fetched_at": tournament["fetched_at"],
        "reasoning_source": meta["reasoning_source"],
        "teams": tournament["teams"],
        "ratings": ratings,
        "groups": tournament["groups"],
        "group_matches": tournament["group_matches"],
        "bracket": sim["bracket"],
        "champion": {
            "team": sim["champion"],
            "probability": sim["monte_carlo"]["p_champion"].get(sim["champion"], 0),
            "report": sim["champion_report"],
        },
        "monte_carlo": sim["monte_carlo"],
        "model_backtest": sim["backtest"],
        "model_params": _model_params_info(),
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(prediction, ensure_ascii=False, indent=1))
    log.info("prediction written to %s", OUTPUT_FILE)

    # Eval Agent（元层）：留档未赛预测 + 复盘已赛场次（docs/07 E1/E2）
    try:
        evaluator.record_predictions(prediction)
        evaluator.evaluate(prediction)
    except Exception:
        log.exception("eval 步骤失败，不影响主预测产物")

    # Evolution 收尾：回填本轮进化对冠军概率的影响，补全进化日志
    if evo_action:
        try:
            evolution.finalize(evo_action, prediction)
        except Exception:
            log.exception("evolution.finalize 失败，不影响主预测产物")

    return prediction


def _model_params_info() -> dict:
    """当前生效的模型参数 + 校准溯源信息（供前端展示）。"""
    info = {"source": "default", "params": dict(predictor.PARAMS)}
    if predictor.PARAMS_FILE.exists():
        try:
            meta = json.loads(predictor.PARAMS_FILE.read_text())
            info.update({
                "source": "calibrated",
                "calibrated_at": meta.get("calibrated_at"),
                "matches_used": meta.get("matches_used"),
                "baseline_log_loss": meta.get("baseline_log_loss"),
                "log_loss": meta.get("log_loss"),
            })
        except (json.JSONDecodeError, OSError):
            pass
    return info


def load() -> dict | None:
    if OUTPUT_FILE.exists():
        return json.loads(OUTPUT_FILE.read_text())
    return None


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    result = run(force_refresh="--refresh" in sys.argv)
    champ = result["champion"]
    print(f"预测冠军: {result['teams'][champ['team']]['name_zh']} "
          f"(夺冠概率 {champ['probability']*100:.1f}%)")
