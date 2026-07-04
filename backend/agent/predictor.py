"""单场预测模块：独立泊松模型（Maher 1982 经典方法）。

实力差 → Elo 期望 → 双方期望进球 λ → 泊松比分概率矩阵
→ 胜/平/负概率、最可能比分；淘汰赛叠加加时/点球晋级概率。

全部为纯函数，输入实力分输出概率，无任何外部调用。
"""
from __future__ import annotations

import math

BASE_GOALS = 2.7      # 近几届世界杯场均总进球
GOAL_EXP = 0.85       # 期望进球平滑指数
GOAL_SCALE = 0.9      # 校准系数：使等实力时 λ_A + λ_B = 2.7（=BASE_GOALS）
MAX_GOALS = 8         # 比分矩阵上限（P(9+球)≈0，并入尾部）
PSO_EDGE_DECAY = 0.4  # 点球阶段强队优势衰减系数


def elo_expectation(strength_a: float, strength_b: float) -> float:
    """Elo 期望胜率（中立场地）。"""
    return 1.0 / (1.0 + 10 ** (-(strength_a - strength_b) / 400.0))


def expected_goals(strength_a: float, strength_b: float) -> tuple[float, float]:
    e_a = elo_expectation(strength_a, strength_b)
    lam_a = BASE_GOALS * (e_a ** GOAL_EXP) * GOAL_SCALE
    lam_b = BASE_GOALS * ((1.0 - e_a) ** GOAL_EXP) * GOAL_SCALE
    return lam_a, lam_b


def _poisson_pmf(lam: float, k: int) -> float:
    return math.exp(-lam) * lam ** k / math.factorial(k)


def score_matrix(lam_a: float, lam_b: float) -> list[list[float]]:
    """P(i:j) 矩阵，i/j ∈ [0, MAX_GOALS]，归一化到和为 1。"""
    pa = [_poisson_pmf(lam_a, i) for i in range(MAX_GOALS + 1)]
    pb = [_poisson_pmf(lam_b, j) for j in range(MAX_GOALS + 1)]
    # 尾部概率并入最后一格，保证矩阵严格归一
    pa[-1] += 1.0 - sum(pa)
    pb[-1] += 1.0 - sum(pb)
    return [[pa[i] * pb[j] for j in range(MAX_GOALS + 1)] for i in range(MAX_GOALS + 1)]


def predict_match(strength_a: float, strength_b: float, knockout: bool = False) -> dict:
    """核心预测函数。

    返回 p_win/p_draw/p_loss（90分钟口径）、most_likely_score、期望进球；
    knockout=True 时额外返回 p_advance（A 队晋级概率，含加时点球）。
    """
    lam_a, lam_b = expected_goals(strength_a, strength_b)
    matrix = score_matrix(lam_a, lam_b)

    p_win = p_draw = p_loss = 0.0
    best_score, best_p = (1, 1), -1.0
    for i in range(MAX_GOALS + 1):
        for j in range(MAX_GOALS + 1):
            p = matrix[i][j]
            if p > best_p:
                best_score, best_p = (i, j), p
            if i > j:
                p_win += p
            elif i == j:
                p_draw += p
            else:
                p_loss += p

    result = {
        "expected_goals": [round(lam_a, 2), round(lam_b, 2)],
        "p_win": round(p_win, 4),
        "p_draw": round(p_draw, 4),
        "p_loss": round(p_loss, 4),
        "most_likely_score": list(best_score),
        "most_likely_score_p": round(best_p, 4),
        "score_matrix": [[round(p, 5) for p in row] for row in matrix],
    }

    if knockout:
        e_a = elo_expectation(strength_a, strength_b)
        # 平局进入加时/点球：强队仍占优但优势衰减（点球高度随机）
        p_draw_win = 0.5 + (e_a - 0.5) * PSO_EDGE_DECAY
        result["p_advance"] = round(p_win + p_draw * p_draw_win, 4)
        if best_score[0] == best_score[1]:
            # 最可能比分为平局时，展示层需要标注加时/点球胜者
            result["decided_in_extra"] = True
    return result
