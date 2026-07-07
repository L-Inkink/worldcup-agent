import json
import math

from agent import evaluator


def _prediction_with_finished():
    """合成一个含已赛结果的 prediction，供评估。"""
    return {
        "generated_at": "2026-07-08T00:00:00+00:00",
        "model_params": {"source": "calibrated", "calibrated_at": "2026-07-07T00:00:00+00:00"},
        "teams": {"AAA": {"name_zh": "甲"}, "BBB": {"name_zh": "乙"}},
        "bracket": {
            "round_of_16": [
                {"id": "mx", "status": "finished", "home": "AAA", "away": "BBB",
                 "score": [2, 1], "winner": "AAA"},
            ],
            "quarter_finals": [],
        },
    }


def _ledger_rows():
    return [{
        "match_id": "mx", "round": "round_of_16", "recorded_at": "2026-07-07T10:00:00+00:00",
        "param_version": "2026-07-07T00:00:00+00:00", "home": "AAA", "away": "BBB",
        "date": "July 8", "predicted_score": [1, 1], "predicted_winner": "AAA",
        "p_advance": 0.7, "p_win": 0.4, "p_draw": 0.3, "p_loss": 0.3,
        "reasoning": "甲实力占优",
    }]


def test_evaluate_case(tmp_path, monkeypatch):
    monkeypatch.setattr(evaluator, "LEDGER_FILE", tmp_path / "ledger.jsonl")
    monkeypatch.setattr(evaluator, "EVAL_FILE", tmp_path / "eval.json")
    evaluator.LEDGER_FILE.write_text(
        "\n".join(json.dumps(r) for r in _ledger_rows()), encoding="utf-8")

    report = evaluator.evaluate(_prediction_with_finished())
    assert report["n_cases"] == 1
    c = report["cases"][0]
    assert c["winner_hit"] is True          # 预测甲晋级，实际甲胜
    assert c["exact_score"] is False        # 预测1:1，实际2:1
    assert c["gd_error"] == 1               # |0 - 1|
    assert c["total_goals_error"] == 1      # |2 - 3|
    assert math.isclose(c["p_advance_for_winner"], 0.7)
    assert report["summary"]["winner_accuracy"] == 1.0


def test_record_predictions_idempotent(tmp_path, monkeypatch):
    monkeypatch.setattr(evaluator, "LEDGER_FILE", tmp_path / "ledger.jsonl")
    monkeypatch.setattr(evaluator, "DATA_DIR", tmp_path)
    pred = {
        "generated_at": "2026-07-08T00:00:00+00:00",
        "model_params": {"calibrated_at": "v1"},
        "bracket": {"round_of_16": [
            {"id": "m1", "status": "scheduled", "home": "AAA", "away": "BBB",
             "predicted_score": [1, 0], "predicted_winner": "AAA",
             "prediction": {"p_advance": 0.6, "p_win": 0.5, "p_draw": 0.3, "p_loss": 0.2},
             "reasoning": {"text": "x"}},
        ]},
    }
    assert evaluator.record_predictions(pred) == 1
    assert evaluator.record_predictions(pred) == 0  # 同参数版本不重复留档


def test_goal_bias_detection(tmp_path, monkeypatch):
    monkeypatch.setattr(evaluator, "LEDGER_FILE", tmp_path / "ledger.jsonl")
    monkeypatch.setattr(evaluator, "EVAL_FILE", tmp_path / "eval.json")
    # 预测都偏低：预测总进球1，实际总进球3
    rows = []
    pred_bracket = {"round_of_16": [], "quarter_finals": []}
    for i in range(3):
        mid = f"m{i}"
        rows.append({
            "match_id": mid, "round": "round_of_16", "recorded_at": "2026-07-07T10:00:00+00:00",
            "param_version": "v1", "home": "AAA", "away": "BBB", "date": f"July {i+1}",
            "predicted_score": [1, 0], "predicted_winner": "AAA",
            "p_advance": 0.7, "p_win": 0.5, "p_draw": 0.3, "p_loss": 0.2, "reasoning": "",
        })
        pred_bracket["round_of_16"].append(
            {"id": mid, "status": "finished", "home": "AAA", "away": "BBB",
             "score": [2, 1], "winner": "AAA"})
    evaluator.LEDGER_FILE.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    pred = {"generated_at": "t", "teams": {"AAA": {"name_zh": "甲"}, "BBB": {"name_zh": "乙"}},
            "bracket": pred_bracket}
    report = evaluator.evaluate(pred)
    assert report["summary"]["goal_bias"]["verdict"] == "模型系统性低估进球"
