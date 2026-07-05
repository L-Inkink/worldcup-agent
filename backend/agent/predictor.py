"""单场预测模块：独立泊松模型 + Dixon-Coles 低比分修正。

实力差 → Elo 期望 → 双方期望进球 λ → 泊松比分概率矩阵（DC修正）
→ 胜/平/负概率、最可能比分；淘汰赛叠加加时/点球晋级概率。

模型参数支持两级来源：
1. DEFAULT_PARAMS 经验默认值
2. data/model_params.json —— 由 calibrate.py 回测校准后写入（优先生效）

全部为纯函数（参数可显式注入），无任何外部调用。
"""
from __future__ import annotations

import json
import math
from pathlib import Path

MAX_GOALS = 8  # 比分矩阵上限（P(9+球)≈0，尾部并入最后一格）

DEFAULT_PARAMS = {
    "base_goals": 2.7,       # 世界杯场均总进球（等实力时校准锚点）
    "goal_exp": 0.85,        # 期望进球平滑指数
    "elo_div": 400.0,        # Elo 期望公式分母（越小对实力差越敏感）
    "rho": 0.0,              # Dixon-Coles 低比分相关性修正（负值提升平局概率）
    "pso_edge_decay": 0.4,   # 点球阶段强队优势衰减系数
}

PARAMS_FILE = Path(__file__).resolve().parent.parent / "data" / "model_params.json"


def load_params() -> dict:
    """默认参数 + 校准文件覆盖。"""
    p = dict(DEFAULT_PARAMS)
    if PARAMS_FILE.exists():
        try:
            p.update(json.loads(PARAMS_FILE.read_text()).get("predictor", {}))
        except (json.JSONDecodeError, OSError):
            pass
    return p


PARAMS = load_params()


def elo_expectation(strength_a: float, strength_b: float, elo_div: float = 400.0) -> float:
    """Elo 期望胜率（中立场地）。"""
    return 1.0 / (1.0 + 10 ** (-(strength_a - strength_b) / elo_div))


def expected_goals(strength_a: float, strength_b: float, params: dict | None = None) -> tuple[float, float]:
    p = params or PARAMS
    e_a = elo_expectation(strength_a, strength_b, p["elo_div"])
    # scale 由 goal_exp 推导，保证等实力时 λ_A + λ_B = base_goals
    scale = 1.0 / (2.0 * 0.5 ** p["goal_exp"])
    lam_a = p["base_goals"] * (e_a ** p["goal_exp"]) * scale
    lam_b = p["base_goals"] * ((1.0 - e_a) ** p["goal_exp"]) * scale
    return lam_a, lam_b


def _poisson_pmf(lam: float, k: int) -> float:
    return math.exp(-lam) * lam ** k / math.factorial(k)


def score_matrix(lam_a: float, lam_b: float, rho: float = 0.0) -> list[list[float]]:
    """P(i:j) 矩阵。rho != 0 时应用 Dixon-Coles 修正（0:0/1:0/0:1/1:1），后重新归一。"""
    pa = [_poisson_pmf(lam_a, i) for i in range(MAX_GOALS + 1)]
    pb = [_poisson_pmf(lam_b, j) for j in range(MAX_GOALS + 1)]
    pa[-1] += 1.0 - sum(pa)
    pb[-1] += 1.0 - sum(pb)
    m = [[pa[i] * pb[j] for j in range(MAX_GOALS + 1)] for i in range(MAX_GOALS + 1)]
    if rho:
        m[0][0] *= 1.0 - lam_a * lam_b * rho
        m[0][1] *= 1.0 + lam_a * rho
        m[1][0] *= 1.0 + lam_b * rho
        m[1][1] *= 1.0 - rho
        total = sum(sum(row) for row in m)
        m = [[v / total for v in row] for row in m]
    return m


def predict_match(strength_a: float, strength_b: float, knockout: bool = False,
                  params: dict | None = None) -> dict:
    """核心预测函数。

    返回 p_win/p_draw/p_loss（90分钟口径）、most_likely_score、期望进球；
    knockout=True 时额外返回 p_advance（A 队晋级概率，含加时点球）。
    """
    p = params or PARAMS
    lam_a, lam_b = expected_goals(strength_a, strength_b, p)
    matrix = score_matrix(lam_a, lam_b, p["rho"])

    p_win = p_draw = p_loss = 0.0
    best_score, best_p = (1, 1), -1.0
    for i in range(MAX_GOALS + 1):
        for j in range(MAX_GOALS + 1):
            v = matrix[i][j]
            if v > best_p:
                best_score, best_p = (i, j), v
            if i > j:
                p_win += v
            elif i == j:
                p_draw += v
            else:
                p_loss += v

    result = {
        "expected_goals": [round(lam_a, 2), round(lam_b, 2)],
        "p_win": round(p_win, 4),
        "p_draw": round(p_draw, 4),
        "p_loss": round(p_loss, 4),
        "most_likely_score": list(best_score),
        "most_likely_score_p": round(best_p, 4),
        "score_matrix": [[round(v, 5) for v in row] for row in matrix],
    }

    if knockout:
        e_a = elo_expectation(strength_a, strength_b, p["elo_div"])
        # 平局进入加时/点球：强队仍占优但优势衰减（点球高度随机）
        p_draw_win = 0.5 + (e_a - 0.5) * p["pso_edge_decay"]
        result["p_advance"] = round(p_win + p_draw * p_draw_win, 4)
        if best_score[0] == best_score[1]:
            result["decided_in_extra"] = True
    return result
