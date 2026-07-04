import math

from agent.predictor import elo_expectation, expected_goals, predict_match, score_matrix


def test_probabilities_sum_to_one():
    pred = predict_match(2100, 1900)
    assert math.isclose(pred["p_win"] + pred["p_draw"] + pred["p_loss"], 1.0, abs_tol=1e-3)


def test_score_matrix_normalized():
    m = score_matrix(1.8, 1.2)
    assert math.isclose(sum(sum(row) for row in m), 1.0, abs_tol=1e-9)


def test_stronger_team_favored():
    pred = predict_match(2200, 1800, knockout=True)
    assert pred["p_win"] > pred["p_loss"]
    assert pred["p_advance"] > 0.5


def test_symmetry():
    a = predict_match(2000, 1900)
    b = predict_match(1900, 2000)
    assert math.isclose(a["p_win"], b["p_loss"], abs_tol=1e-9)
    assert math.isclose(a["p_draw"], b["p_draw"], abs_tol=1e-9)


def test_equal_strength_balanced():
    pred = predict_match(2000, 2000, knockout=True)
    assert math.isclose(pred["p_win"], pred["p_loss"], abs_tol=1e-9)
    assert math.isclose(pred["p_advance"], 0.5, abs_tol=1e-9)
    lam_a, lam_b = expected_goals(2000, 2000)
    assert math.isclose(lam_a + lam_b, 2.7, rel_tol=0.15)  # 校准到世界杯场均总进球附近


def test_elo_expectation_bounds():
    assert elo_expectation(2400, 1500) > 0.99
    assert math.isclose(elo_expectation(2000, 2000), 0.5)
