# 世界杯冠军预测 Agent（2026）

Agent 开发比赛参赛项目：实时采集 2026 世界杯数据（Wikipedia + eloratings，无需 API key），用统计模型（Elo + 泊松/Dixon-Coles + 10000 次蒙特卡洛）逐轮推演淘汰赛并预测冠军，模型参数由已赛场次回测自动校准（两阶段 + walk-forward 门禁），Qwen 生成可解释推理，Web 页面以对阵树可视化呈现。流水线之外设**元层双 Agent**：Eval（预测复盘）与 Evolution（进化编排 + 可审计进化史）。

**当前状态（2026-07-08）**：预测冠军**西班牙**（夺冠概率 39.9%）；已赛 93 场回测方向命中率 **73%**（无数据泄漏口径），16 强 5 场赛前预测命中 4 场（唯一失手为 52% 置信的挪威爆冷）。11 个后端模块、9 条 API、5 个前端视图、39 个单元测试。

## 文档导航

| 文档 | 内容 | 适合读者 |
|-----|------|---------|
| [docs/01-设计思路.md](docs/01-设计思路.md) | 目标、关键决策及理由、演进记录 | 想理解"为什么这么做" |
| [docs/02-系统架构.md](docs/02-系统架构.md) | 模块划分、数据流、API 契约、部署架构 | 想理解"系统长什么样" |
| [docs/03-复现指南.md](docs/03-复现指南.md) | 算法公式、数据源解析细节、Prompt 模板、实现步骤与验收清单 | 想动手复现本工程（人或 AI 工具均可） |
| [docs/04-特征工程路线.md](docs/04-特征工程路线.md) | 特征全景与 P0-P3 落地优先级 | 想理解准确率提升路线 |
| [docs/05-球探Agent需求.md](docs/05-球探Agent需求.md) | 球探 Agent 需求规格（M0 已实现，搜索主体待定） | 想理解球员级数据规划 |
| [docs/06-新特征提案.md](docs/06-新特征提案.md) | F1-F6 零成本特征提案与落地结论（含 F3 负结果） | 想看特征验证方法论 |
| [docs/07-Eval与Evolution-Agent方案.md](docs/07-Eval与Evolution-Agent方案.md) | 元层双 Agent 设计（含一次推翻初版的自我质疑） | 想理解复盘与进化机制 |
| [deploy/README.md](deploy/README.md) | 阿里云 ECS 部署与运维 | 想部署上线 |

## 快速开始

```bash
# 后端（Python ≥3.11）
cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest tests/ -q          # 39 个测试
.venv/bin/python -m agent.pipeline            # 跑完整预测流水线（离线可用，内置快照）
.venv/bin/python -m agent.pipeline --refresh  # 在线采集最新赛果 + 进化校准后重跑
.venv/bin/python -m agent.calibrate --apply   # 两阶段回测校准模型参数
.venv/bin/python -m agent.evaluator           # 预测复盘（对照留档账本与实际赛果）
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
