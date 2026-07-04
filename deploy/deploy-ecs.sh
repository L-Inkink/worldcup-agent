#!/usr/bin/env bash
# 阿里云 ECS 一键部署脚本
# 用法：在 ECS 实例（Ubuntu/Alibaba Cloud Linux）上执行：
#   git clone <repo> && cd worldcup-agent && bash deploy/deploy-ecs.sh
# 可选：部署前 export DASHSCOPE_API_KEY=sk-xxx 以启用 Qwen 推理
set -euo pipefail

cd "$(dirname "$0")/.."

# 1. 安装 Docker（如未安装）
if ! command -v docker &>/dev/null; then
  echo "==> 安装 Docker ..."
  curl -fsSL https://get.docker.com | bash
  systemctl enable --now docker
fi

# 2. 构建镜像
echo "==> 构建镜像 ..."
docker build -t worldcup-agent:latest .

# 3. 运行容器（80 端口对外）
echo "==> 启动容器 ..."
docker rm -f worldcup-agent 2>/dev/null || true
docker run -d --name worldcup-agent \
  --restart unless-stopped \
  -p 80:8000 \
  -e DASHSCOPE_API_KEY="${DASHSCOPE_API_KEY:-}" \
  -e FOOTBALL_DATA_TOKEN="${FOOTBALL_DATA_TOKEN:-}" \
  worldcup-agent:latest

echo "==> 部署完成。安全组放行 80 端口后，访问 http://<ECS公网IP>/"
echo "==> 赛事推进后可调用 POST /api/refresh 拉取最新赛果并重跑预测"
