# 阿里云部署指南

## 方式一：ECS 一键部署（推荐）

1. 购买 ECS 实例（最低配即可：2核2G，Ubuntu 22.04 / Alibaba Cloud Linux 3），安全组放行 **80** 端口
2. SSH 登录后执行：

```bash
git clone <你的仓库地址> && cd worldcup-agent
export DASHSCOPE_API_KEY=sk-xxx     # 可选：启用 Qwen 推理（阿里云百炼控制台获取）
bash deploy/deploy-ecs.sh
```

3. 浏览器访问 `http://<ECS公网IP>/`

## 方式二：本地构建镜像后上传

```bash
docker build -t worldcup-agent .
docker save worldcup-agent | ssh <ecs> "docker load"
ssh <ecs> "docker run -d --restart unless-stopped -p 80:8000 worldcup-agent"
```

## 运维

| 操作 | 命令 |
|-----|------|
| 看日志 | `docker logs -f worldcup-agent` |
| 赛事推进后刷新预测 | `curl -X POST http://localhost/api/refresh` |
| 重启 | `docker restart worldcup-agent` |
| 更新代码 | `git pull && bash deploy/deploy-ecs.sh` |

## 说明

- 镜像内置数据快照，**无任何 API key 也能完整运行**（推理用规则模板、数据用快照）
- **自动跟赛程（v1.1）**：服务自带 auto-refresh 后台调度，每 30 分钟探测新完赛场次并自动重跑预测，无需人工干预；`AUTO_REFRESH_MINUTES` 可调（0=关闭），`POST /api/refresh` 可手动立即刷新
- 若配置 `DASHSCOPE_API_KEY`，解说文本由 qwen-plus / qwen-max 生成
