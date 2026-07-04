# 多阶段构建：前端 build → 后端运行镜像（单容器单端口）

FROM node:20-alpine AS frontend
WORKDIR /build
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./
COPY --from=frontend /build/dist ../frontend/dist

# 环境变量（均可缺省，自动降级）：
#   DASHSCOPE_API_KEY    Qwen 推理（缺省用规则模板）
#   FOOTBALL_DATA_TOKEN  备用数据源（缺省用 Wikipedia + 快照）
EXPOSE 8000
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
