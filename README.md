# 世界杯冠军预测 Agent（2026）

Agent 开发比赛参赛项目：采集 2026 世界杯真实数据，用统计模型（Elo + 泊松 + 蒙特卡洛）逐轮推演淘汰赛并预测冠军，Qwen 生成可解释推理，Web 页面以对阵树可视化呈现。

## 文档导航

| 文档 | 内容 | 适合读者 |
|-----|------|---------|
| [docs/01-设计思路.md](docs/01-设计思路.md) | 目标、关键决策及理由、成功标准 | 想理解"为什么这么做" |
| [docs/02-系统架构.md](docs/02-系统架构.md) | 模块划分、数据流、API 契约、部署架构 | 想理解"系统长什么样" |
| [docs/03-复现指南.md](docs/03-复现指南.md) | 算法公式、数据源、Prompt 模板、实现步骤与验收清单 | 想动手复现本工程（人或 AI 工具均可） |

## 快速开始（实现完成后）

```bash
# 后端
cd backend && pip install -r requirements.txt
python -m agent.pipeline        # 跑完整预测流水线
uvicorn api:app --port 8000     # 启动服务

# 前端
cd frontend && npm install && npm run build

# Docker（单容器）
docker build -t worldcup-agent . && docker run -d -p 80:8000 worldcup-agent
```

环境变量（可选，缺省自动降级）：`FOOTBALL_DATA_TOKEN`（数据源）、`DASHSCOPE_API_KEY`（Qwen 推理）。
