"""FastAPI 服务：REST API + 前端静态托管。

    uvicorn api:app --port 8000
"""
from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from agent import collector, pipeline

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


def _finished_count(data: dict) -> int:
    n = sum(1 for m in data["group_matches"] if m.get("score"))
    for matches in data["bracket"].values():
        n += sum(1 for m in matches if m.get("status") == "finished")
    return n


async def _auto_refresh_loop(minutes: int) -> None:
    """主动数据调度：定期在线探测；发现新完赛场次即重跑全流程并热替换缓存。"""
    global _cache
    while True:
        await asyncio.sleep(minutes * 60)
        try:
            fresh = await asyncio.to_thread(collector.collect_online)
            known = _finished_count(collector.load_snapshot())
            if _finished_count(fresh) > known:
                log.info("auto-refresh: 检测到新完赛场次，重跑预测流水线")
                collector.save_snapshot(fresh)
                _cache = await asyncio.to_thread(pipeline.run)
            else:
                log.info("auto-refresh: 无新赛果")
        except Exception:
            log.exception("auto-refresh 失败，等待下一轮")


@asynccontextmanager
async def _lifespan(app: FastAPI):
    minutes = int(os.environ.get("AUTO_REFRESH_MINUTES", "30"))
    task = asyncio.create_task(_auto_refresh_loop(minutes)) if minutes > 0 else None
    if task:
        log.info("auto-refresh 已启动，每 %s 分钟探测一次（AUTO_REFRESH_MINUTES=0 可关闭）", minutes)
    yield
    if task:
        task.cancel()


app = FastAPI(title="世界杯冠军预测 Agent", version="1.1", lifespan=_lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"

_cache: dict | None = None


def _prediction() -> dict:
    global _cache
    if _cache is None:
        _cache = pipeline.load()
    if _cache is None:
        log.info("no prediction.json, running pipeline (snapshot mode)")
        _cache = pipeline.run()
    return _cache


@app.get("/api/prediction")
def full_prediction():
    return _prediction()


@app.get("/api/bracket")
def bracket():
    p = _prediction()
    return {"bracket": p["bracket"], "teams": p["teams"],
            "data_source": p["data_source"], "data_fetched_at": p["data_fetched_at"]}


@app.get("/api/groups")
def groups():
    p = _prediction()
    return {"groups": p["groups"], "group_matches": p["group_matches"], "teams": p["teams"]}


@app.get("/api/champion")
def champion():
    p = _prediction()
    return {"champion": p["champion"], "monte_carlo": p["monte_carlo"],
            "model_backtest": p["model_backtest"], "teams": p["teams"],
            "reasoning_source": p["reasoning_source"]}


@app.get("/api/match/{match_id}")
def match_detail(match_id: str):
    p = _prediction()
    for round_name, matches in p["bracket"].items():
        for m in matches:
            if m["id"] == match_id:
                return {"round": round_name, "match": m, "teams": p["teams"],
                        "ratings": p["ratings"]}
    raise HTTPException(404, f"match {match_id} not found")


@app.get("/api/eval")
def eval_report():
    """预测复盘报告（Eval Agent，docs/07）。若无缓存则即时生成。"""
    from agent import evaluator
    report = evaluator.load_report()
    if report is None:
        report = evaluator.evaluate(_prediction())
    return report


@app.get("/api/evolution")
def evolution_log():
    """进化时间线（Evolution Agent，docs/07 E4）：可回放的模型自我改进史。"""
    from agent import evolution
    return {"log": evolution.read_log()}


@app.post("/api/refresh")
def refresh():
    """重新在线采集数据并重跑全流程（赛事推进后获取最新赛果）。"""
    global _cache
    _cache = pipeline.run(force_refresh=True)
    return {"ok": True, "generated_at": _cache["generated_at"],
            "data_source": _cache["data_source"]}


# 前端静态托管（构建产物存在时）
if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/")
    def index():
        return FileResponse(FRONTEND_DIST / "index.html")
