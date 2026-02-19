# Docker 镜像构建指南

## 跨平台兼容性（重要）

GridNode 在 Linux 容器中运行任务。在 macOS/Windows 上开发时，**绝对不能直接复制本地编译的二进制到镜像中**。

### 错误做法

会导致 `Exec format error`：

```dockerfile
# 在 macOS 上编译，复制到 Linux 容器 -> 失败
COPY ./target/release/myapp /usr/local/bin/myapp
```

### 正确做法：多阶段构建

在 Linux 容器中编译：

```dockerfile
# 阶段 1：编译
FROM rustlang/rust:nightly-bookworm AS builder

WORKDIR /app
COPY Cargo.toml Cargo.lock ./
COPY src ./src
RUN cargo build --release

# 阶段 2：运行时
FROM debian:bookworm-slim
COPY --from=builder /app/target/release/myapp /usr/local/bin/myapp
CMD ["myapp"]
```

## 语言特定模板

### Python

```dockerfile
# 阶段 1：构建环境
FROM python:3.11-slim AS builder

WORKDIR /app
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 阶段 2：运行时
FROM python:3.11-slim

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app
COPY consumer.py .

ENTRYPOINT ["python", "consumer.py"]
```

### Node.js

```dockerfile
FROM node:18-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci --only=production

FROM node:18-alpine
WORKDIR /app
COPY --from=builder /app/node_modules ./node_modules
COPY . .
ENTRYPOINT ["node", "consumer.js"]
```

### Go

```dockerfile
FROM golang:1.21-alpine AS builder
WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -o consumer

FROM alpine:latest
RUN apk --no-cache add ca-certificates
WORKDIR /root/
COPY --from=builder /app/consumer .
ENTRYPOINT ["./consumer"]
```

## 快速验证镜像

```bash
# 启动容器检查是否能正常运行
docker run --rm your-image your-command

# 检查容器日志
docker logs <container-id>

# 交互式调试
docker run --rm -it your-image sh

# 检查环境变量
docker run --rm your-image env
```

## 多架构镜像

支持不同架构的节点：

```dockerfile
# 使用 docker buildx
# 构建并推送多架构镜像
docker buildx build \
  --platform linux/amd64,linux/arm64,linux/arm/v7 \
  -t your-registry/task:v1.0 \
  --push .
```

注册任务时使用 `images` 字段：

```json
{
  "name": "my-task",
  "images": {
    "linux/amd64": "your-registry/task:v1.0-amd64",
    "linux/arm64": "your-registry/task:v1.0-arm64"
  },
  "input_redis": "redis://host:6379",
  "input_queue": "task:input",
  "output_queue": "task:output"
}
```

## 镜像优化

### 减小镜像大小

```dockerfile
FROM python:3.11-slim AS builder
RUN pip install --user -r requirements.txt

FROM python:3.11-alpine  # 使用 alpine 更小
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH
```

### 清理缓存

```dockerfile
RUN apt-get update && apt-get install -y \
    some-package \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir -r requirements.txt
```

## 安全最佳实践

```dockerfile
# 使用非 root 用户
RUN adduser --disabled-password --gecos '' appuser
USER appuser

# 只复制必要的文件
COPY consumer.py requirements.txt ./
# 不要 COPY . .

# 指定工作目录
WORKDIR /app
```
