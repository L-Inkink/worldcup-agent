import json

from agent import evolution


def test_diagnose_thresholds():
    assert evolution.diagnose(None)["has_bias"] is False
    assert evolution.diagnose({"n_cases": 1})["has_bias"] is False
    low = {"n_cases": 5, "summary": {"goal_bias": {"avg_actual_minus_predicted": 0.2}}}
    assert evolution.diagnose(low)["has_bias"] is False
    high = {"n_cases": 5, "summary": {"goal_bias":
            {"avg_actual_minus_predicted": 0.8, "verdict": "模型系统性低估进球"}}}
    d = evolution.diagnose(high)
    assert d["has_bias"] is True and d["goal_bias"] == 0.8


def test_evolve_does_not_auto_change_base_goals(tmp_path, monkeypatch):
    """核心安全性：偏差只产出提案，绝不自动改 base_goals。"""
    from agent import collector, evaluator
    monkeypatch.setattr(evolution, "EVOLUTION_LOG", tmp_path / "evo.jsonl")
    monkeypatch.setattr(evolution, "DATA_DIR", tmp_path)

    t = collector.load_snapshot()
    eval_report = {"n_cases": 5, "summary": {"goal_bias":
                   {"avg_actual_minus_predicted": 0.8, "verdict": "模型系统性低估进球"}}}
    action = evolution.evolve(t, None, eval_report)

    assert action["trigger"] == "goal_bias_proposal"
    assert action["proposal"] is not None
    assert action["proposal"]["auto_applied"] is False
    # base_goals 不在自动变更集中
    assert "predictor.base_goals" not in action["params_changed"]


def test_proposal_flags_direction_conflict(tmp_path, monkeypatch):
    from agent import collector
    monkeypatch.setattr(evolution, "EVOLUTION_LOG", tmp_path / "evo.jsonl")
    monkeypatch.setattr(evolution, "DATA_DIR", tmp_path)
    t = collector.load_snapshot()
    eval_report = {"n_cases": 5, "summary": {"goal_bias":
                   {"avg_actual_minus_predicted": 0.8, "verdict": "低估"}}}
    action = evolution.evolve(t, None, eval_report)
    p = action["proposal"]
    # 低估→偏差想调高；本届样本 log loss 想调低 → 应识别为冲突
    assert p["conflict"] is True
    assert p["log_loss_prefers"] <= 2.7


def test_evolution_log_append_and_finalize(tmp_path, monkeypatch):
    from agent import collector
    monkeypatch.setattr(evolution, "EVOLUTION_LOG", tmp_path / "evo.jsonl")
    monkeypatch.setattr(evolution, "DATA_DIR", tmp_path)
    t = collector.load_snapshot()
    action = evolution.evolve(t, None, None)  # 无 eval → 标准重校准
    assert action["trigger"] == "scheduled_recalibration"

    new_pred = {"champion": {"team": "ESP"},
                "monte_carlo": {"p_champion": {"ESP": 0.4, "FRA": 0.3, "ARG": 0.2}}}
    evolution.finalize(action, new_pred)
    logged = evolution.read_log()
    assert len(logged) == 1
    assert logged[-1]["champion_after"]["team"] == "ESP"
