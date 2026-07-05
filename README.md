# 世界杯冠军预测 Agent（2026）

Agent 开发比赛参赛项目：实时采集 2026 世界杯数据（Wikipedia + eloratings，无需 API key），用统计模型（Elo + 泊松/Dixon-Coles + 10000 次蒙特卡洛）逐轮推演淘汰赛并预测冠军，模型参数由已赛场次回测自动校准，Qwen 生成可解释推理，Web 页面以对阵树可视化呈现。

**当前状态（2026-07-05）**：预测冠军**西班牙**（夺冠概率 34.0%）；已赛 90 场回测方向命中率 **73.3%**（无数据泄漏口径），7 月 4 日两场 16 强赛前预测全部命中。

## 文档导航

| 文档 | 内容 | 适合读者 |
|-----|------|---------|
| [docs/01-设计思路.md](docs/01-设计思路.md) | 目标、关键决策及理由、演进记录 | 想理解"为什么这么做" |
| [docs/02-系统架构.md](docs/02-系统架构.md) | 模块划分、数据流、API 契约、部署架构 | 想理解"系统长什么样" |
| [docs/03-复现指南.md](docs/03-复现指南.md) | 算法公式、数据源解析细节、Prompt 模板、实现步骤与验收清单 | 想动手复现本工程（人或 AI 工具均可） |
| [docs/04-特征工程路线.md](docs/04-特征工程路线.md) | 特征全景与 P0-P3 落地优先级 | 想理解准确率提升路线 |
| [deploy/README.md](deploy/README.md) | 阿里云 ECS 部署与运维 | 想部署上线 |

## 快速开始

```bash
# 后端（Python ≥3.11）
cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest tests/ -q          # 26 个测试
.venv/bin/python -m agent.pipeline            # 跑完整预测流水线（离线可用，内置快照）
.venv/bin/python -m agent.pipeline --refresh  # 在线采集最新赛果后重跑
.venv/bin/python -m agent.calibrate --apply   # 回测网格搜索校准模型参数
.venv/bin/python -m uvicorn api:app --port 8000   # 启动服务（含 auto-refresh 后台调度）

# 前端
cd frontend && npm install && npm run build   # 产物由后端静态托管，访问 http://localhost:8000

# Docker（单容器）
docker build -t worldcup-agent . && docker run -d -p 80:8000 worldcup-agent
```

环境变量（全部可选，缺省自动降级）：

| 变量 | 作用 | 缺省行为 |
|-----|------|---------|
| `DASHSCOPE_API_KEY` | Qwen 推理解释（qwen-plus/qwen-max） | 规则模板解释 |
| `FOOTBALL_DATA_TOKEN` | 备用数据源 | Wikipedia 主源 + 快照兜底 |
| `AUTO_REFRESH_MINUTES` | 自动刷新间隔（分钟） | 30；设 0 关闭 |
