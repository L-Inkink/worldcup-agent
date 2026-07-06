"""数据采集模块。

三级数据源，按优先级：
1. Wikipedia（无需 API key）：小组积分、全部比赛结果、淘汰赛对阵树
2. football-data.org（需 FOOTBALL_DATA_TOKEN）：备用赛程/赛果源
3. 本地快照 backend/data/tournament.json：任何网络失败时兜底

每次成功在线采集都会刷新本地快照，保证演示零风险。
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from .teams import TEAMS, GROUP_ORDER

log = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SNAPSHOT_FILE = DATA_DIR / "tournament.json"

WIKI_API = "https://en.wikipedia.org/w/api.php?action=parse&prop=wikitext&format=json&formatversion=2&page="
ELO_TSV = "http://eloratings.net/World.tsv"
ELO_NAMES_TSV = "http://eloratings.net/en.teams.tsv"
USER_AGENT = "worldcup-agent/1.0 (competition demo; contact via repo)"

FLAG_RE = r"\{\{#invoke:flag\|fb(?:-rt)?\|(\w+)\}\}"

# 淘汰赛官方场次编号（按对阵树展示顺序）。相邻两场的胜者进入下一轮同一槽位。
R32_MATCH_NUMBERS = [73, 74, 75, 76, 77, 78, 79, 80, 81, 82, 83, 84, 85, 86, 87, 88]
R16_MATCH_NUMBERS = [89, 90, 93, 94, 91, 92, 95, 96]
QF_MATCH_NUMBERS = [97, 98, 99, 100]
SF_MATCH_NUMBERS = [101, 102]


def _http_get(url: str, timeout: int = 30, retries: int = 6) -> str:
    """带指数退避重试，应对 Wikipedia 429 限流。"""
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code in (429, 500, 502, 503):
                wait = 3 * (2 ** attempt)
                log.warning("HTTP %s on %s, retry in %ss", e.code, url[:80], wait)
                time.sleep(wait)
                continue
            raise
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            last_err = e
            wait = 3 * (2 ** attempt)
            log.warning("network error %s on %s, retry in %ss", e, url[:80], wait)
            time.sleep(wait)
    raise last_err  # type: ignore[misc]


def _wiki_wikitext(page: str) -> str:
    time.sleep(1.0)  # 全局礼貌间隔，降低 429 概率
    raw = _http_get(WIKI_API + urllib.parse.quote(page))
    return json.loads(raw)["parse"]["wikitext"]


# ---------------------------------------------------------------- Elo 评分

# eloratings.net 与 FIFA 命名差异的显式映射
ELO_NAME_OVERRIDES = {"CZE": "Czechia", "CUW": "Curaçao"}


def _norm_name(s: str) -> str:
    import unicodedata
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if not unicodedata.combining(c)).lower().strip()


def fetch_elo() -> dict[str, dict]:
    """返回 {FIFA三字码: {elo, form_1y}}。基于 eloratings.net TSV。"""
    names_raw = _http_get(ELO_NAMES_TSV)
    code_by_name: dict[str, str] = {}
    for line in names_raw.strip().split("\n"):
        parts = line.split("\t")
        if len(parts) >= 2 and not parts[0].endswith("_loc"):
            for alias in parts[1:]:
                code_by_name[_norm_name(alias)] = parts[0]

    ratings_raw = _http_get(ELO_TSV)
    elo_by_code: dict[str, dict] = {}
    for line in ratings_raw.strip().split("\n"):
        f = line.replace("−", "-").split("\t")
        if len(f) < 4:
            continue
        code = f[2]
        try:
            elo = int(f[3])
        except ValueError:
            continue
        form = 0
        if len(f) > 17:
            try:
                form = int(f[17].replace("+", ""))
            except ValueError:
                form = 0
        elo_by_code[code] = {"elo": elo, "form_1y": max(-150, min(150, form))}

    result: dict[str, dict] = {}
    for fifa_code, meta in TEAMS.items():
        lookup = ELO_NAME_OVERRIDES.get(fifa_code, meta["name_en"])
        elo_code = code_by_name.get(_norm_name(lookup))
        if elo_code and elo_code in elo_by_code:
            result[fifa_code] = elo_by_code[elo_code]
        else:
            log.warning("no elo match for %s (%s)", fifa_code, meta["name_en"])
    return result


# ---------------------------------------------------------------- 小组赛

def fetch_group_standings() -> dict[str, list[dict]]:
    """解析 Wikipedia 小组积分模板。team_order 已含官方同分判定结果。"""
    wt = _wiki_wikitext("Template:2026 FIFA World Cup group tables")
    groups: dict[str, list[dict]] = {}
    parts = re.split(r"\|Group ([A-L])=", wt)
    for i in range(1, len(parts) - 1, 2):
        g, body = parts[i], parts[i + 1]
        order_m = re.search(r"team_order=\s*([A-Z, ]+)", body)
        if not order_m:
            continue
        codes = [c.strip() for c in order_m.group(1).split(",") if c.strip()]
        rows = []
        for pos, code in enumerate(codes, 1):
            def stat(field: str, _code=code, _body=body) -> int:
                m = re.search(r"\|%s_%s=(-?\d+)" % (field, _code), _body)
                return int(m.group(1)) if m else 0
            won, drawn, lost = stat("win"), stat("draw"), stat("loss")
            gf, ga = stat("gf"), stat("ga")
            rows.append({
                "code": code, "pos": pos,
                "played": won + drawn + lost, "won": won, "drawn": drawn,
                "lost": lost, "gf": gf, "ga": ga, "gd": gf - ga,
                "points": won * 3 + drawn,
            })
        groups[g] = rows
    if len(groups) != 12:
        raise ValueError(f"expected 12 groups, got {len(groups)}")
    return groups


def fetch_group_matches() -> tuple[list[dict], dict[str, dict]]:
    """抓取 12 个小组页面：72 场比赛结果 + 每场阵容详情（M0）。"""
    matches: list[dict] = []
    details: dict[str, dict] = {}
    for g in GROUP_ORDER:
        wt = _wiki_wikitext(f"2026 FIFA World Cup Group {g}")
        found = _parse_football_boxes(wt)
        for idx, m in enumerate(found, 1):
            m["id"] = f"g{g}{idx}"
            m["round"] = "group"
            m["group"] = g
        matches.extend(found)
        details.update(parse_page_match_details(wt))
        time.sleep(1.2)  # 礼貌限速，避免 Wikipedia 429
    if len(matches) < 60:
        raise ValueError(f"expected ~72 group matches, got {len(matches)}")
    return matches, details


def fetch_knockout_details() -> dict[str, dict]:
    """淘汰赛阵容详情：32强专页 + 淘汰赛主页（16强起的详情在此页）。"""
    details: dict[str, dict] = {}
    for page in ("2026 FIFA World Cup round of 32", "2026 FIFA World Cup knockout stage"):
        try:
            details.update(parse_page_match_details(_wiki_wikitext(page)))
        except Exception:
            log.exception("knockout details fetch failed for %s", page)
    return details


# ---------------------------------------------------------------- 阵容与牌（M0）

_LINEUP_ROW = re.compile(
    r"^\|(?P<pos>[A-Z]{2,3})\s*\|\|\s*'''(?P<num>\d+)'''\s*\|\|\s*"
    r"\[\[(?:[^]|]*\|)?(?P<name>[^]|]+)\]\](?P<rest>.*)$")

DEFENSE_POS = {"RB", "CB", "LB", "SW", "RWB", "LWB", "DF"}


def _parse_lineup_segment(segment: str) -> dict | None:
    """解析一场比赛 footballbox 后面的两张首发表。

    返回 {"home": [player...], "away": [player...]}；
    player = {name, pos, starter, yellows, red}。
    黄牌 {{yel|min}}，红牌/两黄变一红 {{sent off|n|min}}（n>=1 表示黄牌累积转红）。
    """
    teams: list[list[dict]] = [[], []]
    team_idx, starter = 0, True
    for raw in segment.split("\n"):
        line = raw.strip()
        if "'''Substitutions:'''" in line:
            starter = False
            continue
        if "'''Manager:'''" in line:
            team_idx += 1
            starter = True
            continue
        if team_idx > 1:
            break
        m = _LINEUP_ROW.match(line)
        if not m:
            continue
        rest = m.group("rest")
        sent_off = re.search(r"\{\{sent off\|(\d+)", rest)
        teams[team_idx].append({
            "name": m.group("name").strip(),
            "pos": m.group("pos"),
            "starter": starter,
            "yellows": len(re.findall(r"\{\{yel\|", rest)) + (
                int(sent_off.group(1)) if sent_off else 0),
            "red": bool(sent_off),
        })
    if len(teams[0]) < 11 or len(teams[1]) < 11:
        return None
    return {"home": teams[0], "away": teams[1]}


def parse_page_match_details(wt: str) -> dict[str, dict]:
    """从整页 wikitext 提取每场比赛的阵容详情，键为 'HOME-AWAY'。

    footballbox 给出对阵双方；其后到下一个 footballbox 之间的文本含首发表。
    """
    details: dict[str, dict] = {}
    boxes = list(re.finditer(r"\{\{#invoke:football box\|main(.*?)\n\}\}", wt, re.S))
    for i, box in enumerate(boxes):
        b = box.group(1)
        t1 = re.search(r"\|team1\s*=\s*" + FLAG_RE, b)
        t2 = re.search(r"\|team2\s*=\s*" + FLAG_RE, b)
        if not (t1 and t2):
            continue
        seg_end = boxes[i + 1].start() if i + 1 < len(boxes) else len(wt)
        lineups = _parse_lineup_segment(wt[box.end():seg_end])
        if lineups:
            details[f"{t1.group(1)}-{t2.group(1)}"] = lineups
    return details


def _parse_football_boxes(wt: str) -> list[dict]:
    out = []
    for box in re.finditer(r"\{\{#invoke:football box\|main(.*?)\n\}\}", wt, re.S):
        b = box.group(1)
        t1 = re.search(r"\|team1\s*=\s*" + FLAG_RE, b)
        t2 = re.search(r"\|team2\s*=\s*" + FLAG_RE, b)
        sc = re.search(r"\{\{score link\|[^|]*\|(\d+)\s*[–\-]\s*(\d+)", b)
        if t1 and t2 and sc:
            out.append({
                "home": t1.group(1), "away": t2.group(1),
                "score": [int(sc.group(1)), int(sc.group(2))],
                "status": "finished",
            })
    return out


# ---------------------------------------------------------------- 淘汰赛

def fetch_bracket() -> dict:
    """解析淘汰赛页面的 RoundN 对阵树模板。

    已赛场次带真实比分（含加时/点球标记），未赛场次比分为空。
    随赛事推进，同一解析逻辑会自动带出新完成的比赛结果。
    """
    wt = _wiki_wikitext("2026 FIFA World Cup knockout stage")
    m = re.search(r"\{\{#invoke:RoundN\|N32(.*?)\}\}<section end=\"Bracket\"", wt, re.S)
    if not m:
        raise ValueError("bracket template not found")
    body = m.group(1)

    entries = []
    for raw_line in body.split("\n"):
        entry = _parse_bracket_line(raw_line)
        if entry:
            entries.append(entry)
    if len(entries) < 32:
        raise ValueError(f"expected 32 bracket entries, got {len(entries)}")

    rounds = {
        "round_of_32": (entries[0:16], R32_MATCH_NUMBERS),
        "round_of_16": (entries[16:24], R16_MATCH_NUMBERS),
        "quarter_finals": (entries[24:28], QF_MATCH_NUMBERS),
        "semi_finals": (entries[28:30], SF_MATCH_NUMBERS),
        "final": ([entries[30]], [104]),
        "third_place": ([entries[31]], [103]),
    }
    bracket: dict = {}
    for round_name, (ents, numbers) in rounds.items():
        matches = []
        for slot, (e, num) in enumerate(zip(ents, numbers), 1):
            matches.append(_bracket_match(e, num, slot))
        bracket[round_name] = matches

    _link_feeders(bracket)
    return bracket


def _parse_bracket_line(raw: str) -> dict | None:
    """解析 RoundN 模板中的一行对阵。

    嵌套模板/wiki链接内含 '|'，直接切分会错位。处理顺序：
    剥 HTML 注释 → 折叠 [[a|b]] 为 b → 旗帜模板替换为 @CODE@ → 按 '|' 切分。
    """
    line = re.sub(r"<!--.*?-->", "", raw.strip())
    line = re.sub(r"\[\[(?:[^]|]*\|)?([^]|]+)\]\]", r"\1", line)
    line = re.sub(FLAG_RE, r"@\1@", line)
    if not line.startswith("|") or "–" not in line:
        return None
    fields = line.split("|")
    if len(fields) < 6 or "–" not in fields[1]:
        return None
    date, _, venue = fields[1].partition("–")
    t1, s1, t2, s2 = fields[2], fields[3], fields[4], fields[5]
    c1 = re.search(r"@(\w+)@", t1)
    c2 = re.search(r"@(\w+)@", t2)
    return {
        "date": date.strip(),
        "venue": venue.strip(),
        "home": c1.group(1) if c1 else None,
        "away": c2.group(1) if c2 else None,
        "score1": _parse_bracket_score(s1),
        "score2": _parse_bracket_score(s2),
        "aet": "{{aet}}" in t1 + t2,
        "pso": "{{pso}}" in t1 + t2,
    }


def _parse_bracket_score(s: str):
    """'1 (3)' -> (1, 3)加时点球; '3' -> (3, None); '' -> (None, None)"""
    s = s.strip()
    m = re.match(r"^(\d+)(?:\s*\((\d+)\))?$", s)
    if not m:
        return (None, None)
    return (int(m.group(1)), int(m.group(2)) if m.group(2) else None)


def _bracket_match(e: dict, num: int, slot: int) -> dict:
    goals1, pens1 = e["score1"]
    goals2, pens2 = e["score2"]
    finished = goals1 is not None and goals2 is not None
    match = {
        "id": f"m{num}",
        "slot": slot,
        "home": e["home"],
        "away": e["away"],
        "date": e["date"],
        "venue": e["venue"],
        "status": "finished" if finished else "scheduled",
        "score": [goals1, goals2] if finished else None,
        "aet": e["aet"],
        "pens": [pens1, pens2] if pens1 is not None else None,
    }
    if finished:
        if pens1 is not None:
            match["winner"] = e["home"] if pens1 > pens2 else e["away"]
        else:
            match["winner"] = e["home"] if goals1 > goals2 else e["away"]
    return match


def _link_feeders(bracket: dict) -> None:
    """相邻两场胜者进入下一轮同一槽位；决赛/季军赛由两场半决赛供给。"""
    chain = ["round_of_32", "round_of_16", "quarter_finals", "semi_finals"]
    for prev_name, next_name in zip(chain, chain[1:]):
        prev, nxt = bracket[prev_name], bracket[next_name]
        for match in nxt:
            i = (match["slot"] - 1) * 2
            match["feeders"] = [prev[i]["id"], prev[i + 1]["id"]]
    sf = bracket["semi_finals"]
    bracket["final"][0]["feeders"] = [sf[0]["id"], sf[1]["id"]]
    bracket["third_place"][0]["feeders"] = [sf[0]["id"], sf[1]["id"]]
    bracket["third_place"][0]["losers_of_feeders"] = True


# ---------------------------------------------------------------- football-data.org（备用源）

def fetch_football_data() -> list[dict]:
    """备用赛果源。仅在配置 FOOTBALL_DATA_TOKEN 时可用。"""
    token = os.environ.get("FOOTBALL_DATA_TOKEN")
    if not token:
        raise RuntimeError("FOOTBALL_DATA_TOKEN not set")
    req = urllib.request.Request(
        "https://api.football-data.org/v4/competitions/WC/matches",
        headers={"X-Auth-Token": token, "User-Agent": USER_AGENT},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)["matches"]


# ---------------------------------------------------------------- 编排

def collect(force_refresh: bool = False) -> dict:
    """采集入口：在线采集成功则刷新快照，失败则回退快照。"""
    if not force_refresh and SNAPSHOT_FILE.exists():
        snapshot = load_snapshot()
        return snapshot

    try:
        data = collect_online()
        save_snapshot(data)
        return data
    except Exception:
        log.exception("online collection failed, falling back to snapshot")
        return load_snapshot()


def collect_online() -> dict:
    elo = fetch_elo()
    standings = fetch_group_standings()
    group_matches, match_details = fetch_group_matches()
    bracket = fetch_bracket()
    match_details.update(fetch_knockout_details())

    teams = {}
    for code, meta in TEAMS.items():
        teams[code] = {
            **meta,
            "elo": elo.get(code, {}).get("elo", 1500),
            "form_1y": elo.get(code, {}).get("form_1y", 0),
        }
    return {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "source": "wikipedia+eloratings",
        "teams": teams,
        "groups": standings,
        "group_matches": group_matches,
        "bracket": bracket,
        "match_details": match_details,
    }


def save_snapshot(data: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SNAPSHOT_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=1))


def load_snapshot() -> dict:
    data = json.loads(SNAPSHOT_FILE.read_text())
    data["source"] = "snapshot"
    return data


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = collect(force_refresh=True)
    print(f"source={result['source']} teams={len(result['teams'])} "
          f"group_matches={len(result['group_matches'])}")
