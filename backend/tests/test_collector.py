from agent import collector
from agent.teams import TEAMS


def test_snapshot_loads_offline():
    data = collector.load_snapshot()
    assert data["source"] == "snapshot"
    assert len(data["teams"]) == 48
    assert len(data["groups"]) == 12
    assert len(data["group_matches"]) == 72


def test_snapshot_bracket_structure():
    b = collector.load_snapshot()["bracket"]
    assert len(b["round_of_32"]) == 16
    assert len(b["round_of_16"]) == 8
    assert len(b["quarter_finals"]) == 4
    assert len(b["semi_finals"]) == 2
    assert len(b["final"]) == 1
    for m in b["round_of_16"]:
        assert len(m["feeders"]) == 2


def test_finished_matches_have_winner():
    b = collector.load_snapshot()["bracket"]
    for matches in b.values():
        for m in matches:
            if m["status"] == "finished":
                assert m["winner"] in (m["home"], m["away"])


def test_all_teams_have_elo():
    data = collector.load_snapshot()
    for code in TEAMS:
        assert data["teams"][code]["elo"] > 1000, f"{code} missing real elo"


def test_bracket_line_parser():
    line = ("|June 29 – [[Foxborough, Massachusetts|Foxborough]]"
            "|{{#invoke:flag|fb|GER}}|1 (3)|{{#invoke:flag|fb|PAR}} {{pso}}|1 (4)")
    e = collector._parse_bracket_line(line)
    assert e["home"] == "GER" and e["away"] == "PAR"
    assert e["score1"] == (1, 3) and e["score2"] == (1, 4)
    assert e["pso"] is True


def test_bracket_line_parser_unplayed():
    line = "|July 4 – [[Philadelphia]]|{{#invoke:flag|fb-rt|PAR}}||{{#invoke:flag|fb|FRA}}|"
    e = collector._parse_bracket_line(line)
    assert e["home"] == "PAR" and e["away"] == "FRA"
    assert e["score1"] == (None, None)
