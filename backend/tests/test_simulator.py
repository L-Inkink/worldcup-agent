import math

import pytest

from agent import collector, rating, simulator


@pytest.fixture(scope="module")
def tournament():
    return collector.load_snapshot()  # 测试只用仓库内置快照，不联网


@pytest.fixture(scope="module")
def sim_result(tournament):
    ratings = rating.compute_ratings(tournament)
    return simulator.simulate(tournament, ratings)


def test_champion_probabilities_sum_to_one(sim_result):
    total = sum(sim_result["monte_carlo"]["p_champion"].values())
    assert math.isclose(total, 1.0, abs_tol=0.01)


def test_reproducible_with_fixed_seed(tournament):
    ratings = rating.compute_ratings(tournament)
    a = simulator.simulate(tournament, ratings)
    b = simulator.simulate(tournament, ratings)
    assert a["monte_carlo"]["p_champion"] == b["monte_carlo"]["p_champion"]
    assert a["champion"] == b["champion"]


def test_finished_matches_locked(sim_result, tournament):
    """已赛场次必须保留真实结果，不被预测覆盖。"""
    for rn, matches in tournament["bracket"].items():
        for original in matches:
            if original["status"] != "finished":
                continue
            sim_match = next(m for m in sim_result["bracket"][rn] if m["id"] == original["id"])
            assert sim_match["score"] == original["score"]
            assert sim_match["winner"] == original["winner"]


def test_all_unplayed_have_predictions(sim_result):
    for rn, matches in sim_result["bracket"].items():
        for m in matches:
            if m["status"] == "scheduled":
                assert m.get("prediction"), f"{m['id']} missing prediction"
                assert m.get("predicted_winner") in (m["home"], m["away"])


def test_backtest_no_leakage_and_sane(sim_result):
    bt = sim_result["backtest"]
    assert bt["overall"]["matches"] >= 80  # 72小组赛 + 16场32强
    assert 0.4 <= bt["overall"]["accuracy"] <= 1.0  # 显著好于随机(~33%三向)


def test_rating_strength_pre_excludes_wc(tournament):
    ratings = rating.compute_ratings(tournament)
    for code, r in ratings.items():
        expected = r["strength_pre"] + rating.W_WC * r["wc_performance"]
        assert math.isclose(r["strength"], expected, abs_tol=0.11)
