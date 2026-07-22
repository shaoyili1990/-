# Monkey Harness Agent (弼马温 Agent) — Docker 多阶段构建
# 包含：web桌面版 + MCP Streamable HTTP 双模式

# ===== Stage 1: Build =====
FROM python:3.12-slim AS builder

WORKDIR /build
COPY . .

RUN pip install --no-cache-dir hatchling && \
    pip install --no-cache-dir --prefix=/install .[all]

# ===== Stage 2: Runtime =====
FROM python:3.12-slim

# 运行时依赖
RUN pip install --no-cache-dir \
    httpx pyyaml fastapi uvicorn jinja2 python-multipart pillow mcp agent-reach

# 从 builder 复制
COPY --from=builder /install /usr/local

# 资产文件
COPY --from=builder /build/fingerprints /fingerprints
COPY --from=builder /build/subchains /subchains
COPY --from=builder /build/validations /validations
COPY --from=builder /build/store /store
COPY --from=builder /build/config.yaml /config.yaml
COPY --from=builder /build/SKILL.md /SKILL.md

RUN useradd -m -s /bin/bash monkey && \
    chown -R monkey:monkey /store /fingerprints /subchains /validations
USER monkey
WORKDIR /home/monkey

# 环境变量
ENV MONKEY_MONKEY_PROVIDER=openai
ENV MONKEY_HORSE_PROVIDER=deepseek
ENV MONKEY_ENCODING=utf-8
ENV MONKEY_STORE_DIR=/store

EXPOSE 8080 8000

# 默认：Web 桌面版
CMD ["monkey-harness", "desktop", "--host", "0.0.0.0", "--port", "8080"]

# 替代入口：MCP HTTP 模式
# docker run -e MCP_TRANSPORT=http -p 8000:8000 monkey-harness-agent bimawen-mcp --transport http --host 0.0.0.0 --port 8000
