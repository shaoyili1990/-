# Hermes Agent Universal - Docker 多阶段构建
# 包含所有资产文件：fingerprints/subchains/validations/store

# ===== Stage 1: Build =====
FROM python:3.12-slim AS builder

WORKDIR /build
COPY . .

RUN pip install --no-cache-dir hatchling && \
    pip install --no-cache-dir --prefix=/install .

# ===== Stage 2: Runtime =====
FROM python:3.12-slim

# 安装运行时依赖
RUN pip install --no-cache-dir \
    httpx pyyaml fastapi uvicorn jinja2 python-multipart pillow

# 从 builder 复制安装的包
COPY --from=builder /install /usr/local

# 复制资产文件（指纹、子链、验证链、数据库、配置）
COPY --from=builder /build/fingerprints /fingerprints
COPY --from=builder /build/subchains /subchains
COPY --from=builder /build/validations /validations
COPY --from=builder /build/store /store
COPY --from=builder /build/config.yaml /config.yaml
COPY --from=builder /build/SKILL.md /SKILL.md

# 创建 hermes 用户
RUN useradd -m -s /bin/bash hermes && \
    chown -R hermes:hermes /store /fingerprints /subchains /validations
USER hermes
WORKDIR /home/hermes

# 环境变量（默认混搭: Monkey=OpenAI, Horse=DeepSeek）
ENV HERMES_MONKEY_PROVIDER=openai
ENV HERMES_HORSE_PROVIDER=deepseek
ENV HERMES_ENCODING=utf-8
ENV HERMES_STORE_DIR=/store
ENV HERMES_MONKEY_BASE_URL=
ENV HERMES_HORSE_BASE_URL=

EXPOSE 8080

ENTRYPOINT ["hermes"]
CMD ["desktop", "--host", "0.0.0.0", "--port", "8080"]
