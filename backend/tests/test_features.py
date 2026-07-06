from datetime import date

from agent import features


def _mini_bracket():
    """合成对阵树：不随真实赛事推进而变化的确定性用例。"""
    return {
        "round_of_32": [
            {"id": "a", "slot": 1, "home": "AAA", "away": "BBB", "date": "June 29",
             "status": "finished", "score": [1, 1], "pens": [4, 3], "winner": "AAA"},
            {"id": "b", "slot": 2, "home": "CCC", "away": "DDD", "date": "June 30",
             "status": "finished", "score": [2, 0], "winner": "CCC"},
        ],
        "round_of_16": [
            {"id": "c", "slot": 1, "home": "AAA", "away": "CCC", "date": "July 4",
             "status": "scheduled", "feeders": ["a", "b"]},
        ],
        "quarter_finals": [], "semi_finals": [], "final": [],
    }


def test_rest_days_and_pens():
    b = _mini_bracket()
    features.annotate_context(b)
    ctx = b["round_of_16"][0]["context"]
    assert ctx["rest_days"] == {"home": 5, "away": 4}
    assert ctx["pens_this_wc"]["home"] == {"won": 1, "lost": 0}
    assert "away" not in ctx["pens_this_wc"]


def test_finished_matches_untouched():
    b = _mini_bracket()
    features.annotate_context(b)
    for m in b["round_of_32"]:
        assert "context" not in m


def test_real_snapshot_scheduled_matches_get_context():
    """真实数据上：所有已确定对阵的未赛场次都应有休息天数。"""
    from agent import collector, rating, simulator
    t = collector.load_snapshot()
    sim = simulator.simulate(t, rating.compute_ratings(t))
    features.annotate_context(sim["bracket"])
    checked = 0
    for rn in features.ROUND_CHAIN:
        for m in sim["bracket"][rn]:
            if m["status"] == "scheduled" and m.get("home") and m.get("away") and m.get("date"):
                assert "context" in m and "rest_days" in m["context"], m["id"]
                checked += 1
    assert checked > 0


def test_parse_match_date():
    assert features.parse_match_date("July 4") == date(2026, 7, 4)
    assert features.parse_match_date("June 29") == date(2026, 6, 29)
    assert features.parse_match_date(None) is None
    assert features.parse_match_date("bogus") is None


def test_key_players_loader():
    players = features.load_key_players()
    assert "ESP" in players
    line = features.key_players_line("ESP", players)
    assert "亚马尔" in line and "可出战" in line
    assert features.key_players_line("XXX", players) is None


def test_lineup_parser_from_wikitext():
    from agent import collector
    seg = """
{| style="font-size:90%"
|-
|GK ||'''1''' ||[[Keeper One]]
|-
|CB ||'''3''' ||[[Back One]] || {{yel|23}}
|-
|CB ||'''5''' ||[[Back Two]] || {{sent off|1|88}}
|-
|CM ||'''8''' ||[[Mid One]] || || {{suboff|66}}
|-
|colspan=3|'''Substitutions:'''
|-
|FW ||'''14'''||[[Sub One]] || || {{subon|66}}
|-
|colspan=3|'''Manager:'''
|-
|colspan=3|[[Coach A]]
|}
|valign="top"|
{| style="font-size:90%"
|-
|GK ||'''1''' ||[[Away Keeper]]
|-
|colspan=3|'''Manager:'''
|-
|colspan=3|[[Coach B]]
|}
"""
    # 放宽 11 人校验做单元测试：直接测行解析
    rows = [l for l in seg.split("\n") if collector._LINEUP_ROW.match(l.strip())]
    assert len(rows) == 6
    parsed = collector._parse_lineup_segment(seg)
    assert parsed is None  # 不足11人 → 整段拒绝（防脏数据）


def test_team_discipline_rules():
    hist = [
        [{"name": "A", "pos": "CB", "starter": True, "yellows": 1, "red": False},
         {"name": "B", "pos": "CM", "starter": True, "yellows": 0, "red": False}],
        [{"name": "A", "pos": "CB", "starter": True, "yellows": 1, "red": False},
         {"name": "B", "pos": "CM", "starter": True, "yellows": 1, "red": False},
         {"name": "C", "pos": "FW", "starter": False, "yellows": 0, "red": True}],
    ]
    d = features.team_discipline(hist)
    assert "A" in d["suspended_next"]      # 第二场攒到第2黄
    assert "C" in d["suspended_next"]      # 红牌
    assert d["at_risk"] == ["B"]           # 1黄且上场首发


def test_lineup_stability_counts():
    def team(names, defense=()):
        return [{"name": n, "pos": "CB" if n in defense else "CM",
                 "starter": True, "yellows": 0, "red": False} for n in names]
    hist = [team("ABCDEFGHIJK", "ABC"), team("ABCDEFGHIJK", "ABC"),
            team("ABCDEFGHIJX", "ABC")]
    s = features.lineup_stability(hist)
    assert s["xi_changes_last"] == 1
    assert s["back_line_stable_matches"] == 3
