# Hermes Agent Universal - Docker 部署
# 多阶段构建

# ===== Stage 1: Build =====
FROM python:3.12-slim AS builder

WORKDIR /build
COPY pyproject.toml .
COPY hermes_universal/ hermes_universal/
COPY config.yaml .
COPY store/ store/

RUN pip install --no-cache-dir hatchling && \
    pip install --no-cache-dir --prefix=/install hermes_universal/

# ===== Stage 2: Runtime =====
FROM python:3.12-slim

# 安装运行时依赖
RUN pip install --no-cache-dir \
    httpx \
    pyyaml \
    fastapi \
    uvicorn \
    jinja2 \
    python-multipart \
    pillow

# 从builder复制
COPY --from=builder /install /usr/local

# 创建hermes用户
RUN useradd -m -s /bin/bash hermes
USER hermes
WORKDIR /home/hermes

# 默认配置
ENV HERMES_MONKEY_PROVIDER=openai
ENV HERMES_HORSE_PROVIDER=deepseek
ENV HERMES_ENCODING=utf-8

# 暴露桌面版端口
EXPOSE 8080

# 默认启动桌面版
ENTRYPOINT ["hermes"]
CMD ["desktop", "--host", "0.0.0.0", "--port", "8080"]
