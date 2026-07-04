import copy

from agent import collector, features, rating, simulator


def _annotated_bracket():
    t = collector.load_snapshot()
    sim = simulator.simulate(t, rating.compute_ratings(t))
    bracket = sim["bracket"]
    features.annotate_context(bracket)
    return bracket


def test_rest_days_r16():
    """m89 巴拉圭vs法国 7月4日：巴拉圭 6/29 赛，法国 6/30 赛。"""
    b = _annotated_bracket()
    m89 = next(m for m in b["round_of_16"] if m["id"] == "m89")
    assert m89["context"]["rest_days"] == {"home": 5, "away": 4}


def test_pens_record_from_bracket():
    """本届32强点球：巴拉圭胜德国、摩洛哥胜荷兰、埃及胜澳大利亚。"""
    b = _annotated_bracket()
    m89 = next(m for m in b["round_of_16"] if m["id"] == "m89")
    assert m89["context"]["pens_this_wc"]["home"] == {"won": 1, "lost": 0}
    assert "away" not in m89["context"].get("pens_this_wc", {})  # 法国无点球记录


def test_finished_matches_untouched():
    b = _annotated_bracket()
    for matches in b.values():
        for m in matches:
            if m["status"] == "finished":
                assert "context" not in m


def test_parse_match_date():
    from datetime import date
    assert features.parse_match_date("July 4") == date(2026, 7, 4)
    assert features.parse_match_date("June 29") == date(2026, 6, 29)
    assert features.parse_match_date(None) is None
    assert features.parse_match_date("bogus") is None
