import math

from agent import calibrate, collector
from agent.predictor import DEFAULT_PARAMS


def test_log_loss_sane():
    t = collector.load_snapshot()
    ll = calibrate.log_loss(t, dict(DEFAULT_PARAMS), w_form=0.5)
    # 三向随机基线 ln(3)≈1.10，模型应显著优于随机
    assert 0.3 < ll < 1.0


def test_dc_correction_shifts_draw_probability():
    from agent.predictor import predict_match
    base = dict(DEFAULT_PARAMS, rho=0.0)
    dc = dict(DEFAULT_PARAMS, rho=-0.12)
    p0 = predict_match(2000, 2000, params=base)
    p1 = predict_match(2000, 2000, params=dc)
    assert p1["p_draw"] > p0["p_draw"]  # 负rho提升平局概率
    total = p1["p_win"] + p1["p_draw"] + p1["p_loss"]
    assert math.isclose(total, 1.0, abs_tol=1e-3)


def test_params_file_roundtrip():
    from agent import predictor, rating
    params = predictor.load_params()
    for key in DEFAULT_PARAMS:
        assert key in params
    w_fifa, w_form, w_wc = rating.load_weights()
    assert 0 <= w_fifa <= 2 and 0 <= w_form <= 2 and 0 <= w_wc <= 2
