"""FastAPI 服务：REST API + 前端静态托管。

    uvicorn api:app --port 8000
"""
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from agent import pipeline

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

app = FastAPI(title="世界杯冠军预测 Agent", version="1.0")
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
