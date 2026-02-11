---
name: idm-gridcore
description: Agent 的算力调用工具。透明利用 IDM-GridCore 分布式集群加速"小计算、大批量"任务，支持从零快速部署或连接已有集群。
---

# IDM-GridCore Skill 使用指南

让 AI Agent 能够调用分布式计算集群，加速处理大批量小任务。

> **源码与接口文档**: https://github.com/Wolido/idm-gridcore
> 
> 本项目详细接口定义、API 规范、数据模型等，请参考上述仓库源码。

---

## 什么时候使用

### 适合使用

- 需要处理 1万+ 次的重复计算
- 单次计算快（<1秒），但总量大
- 数据可以分片独立处理，无强依赖
- 具体场景：
  - 批量图片处理（缩略图、水印、格式转换）
  - 批量 API 调用（数据抓取、接口测试）
  - 批量数据处理（CSV/JSON 转换、清洗）
  - 数值计算（蒙特卡洛模拟、参数扫描）

### 不适合使用

- 单次计算需要几小时的大型科学计算
- 任务间有强依赖，必须串行执行
- 需要严格事务一致性的任务
- 数据量极小（<1000条），本地处理更快

---

## 前置条件检查

### 1. 确认使用模式

**首先询问用户**：计算集群准备好了吗？

```yaml
modes:
  - scenario: 没有集群，需要临时启动
    action: 使用"从零启动"模式
  - scenario: 已有公司/团队共享集群
    action: 使用"连接已有集群"模式
  - scenario: 不确定
    action: 默认推荐"从零启动"（最简单）
```

### 2. 从零启动检查

如果选择从零启动，检查以下内容：

```bash
# 检查 Docker 是否可用
docker ps
# 如果失败，提示用户安装/启动 Docker

# 检查端口占用（默认 8080/6379）
lsof -i :8080
lsof -i :6379
# 如果被占用，询问是否更换端口
```

### 3. 连接已有集群检查

如果选择连接已有集群，询问：

```
请提供以下信息：
1. ComputeHub 地址（如 http://192.168.1.100:8080）
2. 认证 Token
3. Redis 地址（如 redis://:password@host:6379）
```

---

## 部署指南

### 方式一：从零启动（本地快速部署）

适用于临时需要并行计算的场景。

#### 步骤 1：下载二进制

**重要**：不要假设 release 文件的命名格式，务必先查阅 release 页面了解实际发布内容。不同版本可能有不同的打包方式（单独二进制、tar.gz、zip 等）。

**推荐步骤**：

```bash
# 1. 先查看 release 页面有哪些文件
curl -s https://api.github.com/repos/Wolido/idm-gridcore/releases/latest | grep "browser_download_url"

# 2. 根据实际文件结构决定下载方式
# 示例：如果是压缩包，下载后解压；如果是单独二进制，直接下载
```

**示例脚本**（根据实际 release 结构调整）：

```bash
# 创建目录
mkdir -p ~/.local/share/idm-gridcore/bin
cd ~/.local/share/idm-gridcore/bin

# 检测当前架构和平台
ARCH=$(uname -m)
OS=$(uname -s | tr '[:upper:]' '[:lower:]')

if [ "$OS" = "darwin" ]; then
    PLATFORM="macos"
elif [ "$OS" = "linux" ]; then
    PLATFORM="linux"
else
    echo "不支持的操作系统: $OS"
    exit 1
fi

if [ "$ARCH" = "x86_64" ]; then
    ARCH_SUFFIX="x64"
elif [ "$ARCH" = "aarch64" ] || [ "$ARCH" = "arm64" ]; then
    ARCH_SUFFIX="arm64"
else
    echo "不支持的架构: $ARCH，需要本地编译"
    exit 1
fi

# 获取下载 URL（根据实际文件名模式调整）
echo "查询最新 release..."
DOWNLOAD_URL=$(curl -s https://api.github.com/repos/Wolido/idm-gridcore/releases/latest | \
    grep "browser_download_url" | \
    grep "${PLATFORM}-${ARCH_SUFFIX}" | \
    head -1 | cut -d'"' -f4)

if [ -z "$DOWNLOAD_URL" ]; then
    echo "错误：无法获取下载 URL，可能需要本地编译"
    exit 1
fi

echo "下载: $DOWNLOAD_URL"

# 根据文件类型处理
if echo "$DOWNLOAD_URL" | grep -q "\.tar\.gz"; then
    # tar.gz 压缩包
    curl -L -o package.tar.gz "$DOWNLOAD_URL"
    tar -xzf package.tar.gz
    # 移动二进制文件（根据实际目录结构调整）
    find . -name "computehub" -o -name "gridnode" | while read f; do mv "$f" .; done
    rm -rf package.tar.gz */
elif echo "$DOWNLOAD_URL" | grep -q "\.zip"; then
    # zip 压缩包
    curl -L -o package.zip "$DOWNLOAD_URL"
    unzip -q package.zip
    find . -name "computehub" -o -name "gridnode" | while read f; do mv "$f" .; done
    rm -rf package.zip */
else
    # 单独二进制文件
    curl -L -o computehub "$DOWNLOAD_URL"
fi

chmod +x computehub gridnode 2>/dev/null || true

# 验证
if [ -f computehub ] && [ -f gridnode ]; then
    echo "下载成功"
    ls -la computehub gridnode
else
    echo "警告：未找到预期的二进制文件，请检查 release 页面"
    ls -la
fi
```

**如果下载失败**：尝试本地编译

```bash
# 克隆仓库
git clone https://github.com/Wolido/idm-gridcore.git /tmp/idm-gridcore
cd /tmp/idm-gridcore

# 编译
cargo build --release

# 复制二进制
cp target/release/computehub ~/.local/share/idm-gridcore/bin/
cp target/release/gridnode ~/.local/share/idm-gridcore/bin/
```

#### 步骤 2：生成配置

**配置文件路径优先级**（GridNode 按此顺序查找）：
1. 环境变量 `IDM_GRIDCORE_CONFIG` 指定的路径
2. `/etc/idm-gridcore/gridnode.toml`（系统级配置，需要 root）
3. 用户默认配置目录（推荐）

**用户默认配置目录**：
- **macOS**: `~/Library/Application Support/idm-gridcore/gridnode.toml`
- **Linux**: `~/.config/idm-gridcore/gridnode.toml`

```bash
# 检测操作系统并设置配置路径
if [[ "$OSTYPE" == "darwin"* ]]; then
    CONFIG_DIR="$HOME/Library/Application Support/idm-gridcore"
else
    CONFIG_DIR="$HOME/.config/idm-gridcore"
fi

mkdir -p "$CONFIG_DIR"

# 生成随机 token
TOKEN="skill-$(openssl rand -hex 16)"

# 生成 ComputeHub 配置
cat > "$CONFIG_DIR/computehub.toml" << EOF
bind = "0.0.0.0:8080"
token = "$TOKEN"
EOF

# 生成 GridNode 配置（必需配置）
cat > "$CONFIG_DIR/gridnode.toml" << EOF
# ComputeHub 服务端地址
server_url = "http://localhost:8080"

# 节点认证 Token（必须与 ComputeHub 配置的 token 相同）
token = "$TOKEN"
EOF

echo "配置已生成: $CONFIG_DIR"
```

**GridNode 完整配置参考**：

```toml
# ========== 必需配置（必须手动设置）==========
# ComputeHub 服务端地址
server_url = "http://192.168.1.100:8080"

# 节点认证 Token（必须与 ComputeHub 配置的 token 相同）
token = "your-secret-token"

# ========== 可选配置（都有默认值）==========
# 节点唯一 ID（首次启动由 ComputeHub 分配，自动保存到配置文件）
# node_id = "xxx-xxx-xxx"

# 并行容器数（默认使用 CPU 核心数）
# parallelism = 4

# 心跳间隔（秒，默认 30）
# heartbeat_interval = 30

# 停止容器的优雅超时（秒，默认 30）
# 任务切换或停止时，给容器多少时间来完成当前工作
# stop_timeout = 30

# 每个容器的内存限制（MB，默认 1024）
# container_memory = 1024

# ========== 自动检测字段（无需配置）==========
# hostname - 自动获取系统主机名
# architecture - 自动检测 CPU 架构 (x86_64/aarch64/arm)
```

#### 步骤 3：启动 Redis

```bash
# 使用项目自带的 docker-compose
cd /tmp/idm-gridcore/redis-setup

# 生成 .env 文件
cat > .env << 'EOF'
REDIS_PASSWORD=changeme-strong-password
REDIS_PORT=6379
EOF

# 启动 Redis
docker compose up -d

# 验证
redis-cli -a changeme-strong-password ping
# 应返回 PONG
```

#### 步骤 4：启动 ComputeHub

```bash
# 获取配置路径
if [[ "$OSTYPE" == "darwin"* ]]; then
    CONFIG_DIR="$HOME/Library/Application Support/idm-gridcore"
else
    CONFIG_DIR="$HOME/.config/idm-gridcore"
fi

# 前台启动（调试用）
~/.local/share/idm-gridcore/bin/computehub -c "$CONFIG_DIR/computehub.toml"

# 或后台启动
nohup ~/.local/share/idm-gridcore/bin/computehub -c "$CONFIG_DIR/computehub.toml" > /tmp/computehub.log 2>&1 &
echo $! > /tmp/computehub.pid

sleep 2

# 验证
curl http://localhost:8080/health
# 应返回 OK
```

#### 步骤 5：启动 GridNode

```bash
# 获取配置路径
if [[ "$OSTYPE" == "darwin"* ]]; then
    CONFIG_DIR="$HOME/Library/Application Support/idm-gridcore"
else
    CONFIG_DIR="$HOME/.config/idm-gridcore"
fi

# 启动 GridNode（首次启动会自动保存 node_id）
~/.local/share/idm-gridcore/bin/gridnode -c "$CONFIG_DIR/gridnode.toml" &

# 获取 token
TOKEN=$(grep token "$CONFIG_DIR/computehub.toml" | cut -d'"' -f2)

# 验证节点注册
curl -H "Authorization: Bearer $TOKEN" http://localhost:8080/api/nodes
```

#### 步骤 6：记录部署信息

```bash
# 获取配置路径
if [[ "$OSTYPE" == "darwin"* ]]; then
    CONFIG_DIR="$HOME/Library/Application Support/idm-gridcore"
else
    CONFIG_DIR="$HOME/.config/idm-gridcore"
fi

# 保存到 skill state 目录，方便后续管理
mkdir -p ~/.config/agents/skills/idm-gridcore/state

cat > ~/.config/agents/skills/idm-gridcore/state/local_cluster.json << EOF
{
  "mode": "local",
  "token": "$TOKEN",
  "computehub": {
    "pid": $(cat /tmp/computehub.pid),
    "binary_path": "$HOME/.local/share/idm-gridcore/bin/computehub",
    "config_path": "$CONFIG_DIR/computehub.toml",
    "url": "http://localhost:8080"
  },
  "gridnode": {
    "config_path": "$CONFIG_DIR/gridnode.toml"
  },
  "redis": {
    "url": "redis://:changeme-strong-password@localhost:6379"
  },
  "managed_by_skill": true,
  "created_at": "$(date -Iseconds)"
}
EOF
```

---

### 方式二：连接已有集群

如果用户已有部署好的 ComputeHub。

#### 步骤 1：获取配置信息

```
询问用户：
1. ComputeHub 地址（如 http://192.168.1.10:8080）
2. 认证 Token
3. Redis 地址（用于推送任务数据）
```

#### 步骤 2：保存配置

```bash
mkdir -p ~/.config/agents/skills/idm-gridcore

# 保存配置（注意：token 存到 credentials.toml）
cat > ~/.config/agents/skills/idm-gridcore/skill.toml << EOF
[cluster.production]
name = "预设集群"
computehub_url = "http://192.168.1.10:8080"
redis_url = "redis://:password@192.168.1.10:6379"
EOF

cat > ~/.config/agents/skills/idm-gridcore/credentials.toml << EOF
[cluster.production]
token = "用户提供的安全令牌"
EOF

chmod 600 ~/.config/agents/skills/idm-gridcore/credentials.toml
```

#### 步骤 3：验证连接

```bash
# 加载配置
source ~/.config/agents/skills/idm-gridcore/skill.toml
TOKEN=$(grep token ~/.config/agents/skills/idm-gridcore/credentials.toml | cut -d'"' -f2)

# 检查 ComputeHub
curl -H "Authorization: Bearer $TOKEN" \
  $CLUSTER_PRODUCTION_COMPUTEHUB_URL/health

# 查看在线节点
curl -H "Authorization: Bearer $TOKEN" \
  $CLUSTER_PRODUCTION_COMPUTEHUB_URL/api/nodes

# 检查 Redis 连接
redis-cli -u $CLUSTER_PRODUCTION_REDIS_URL ping
```

---

## 任务提交流程

> **接口详情参考**: https://github.com/Wolido/idm-gridcore
> 
> 以下示例展示了主要的 API 调用方式，完整接口定义请查阅项目源码。

### 完整示例：批量计算平方根

```bash
#!/bin/bash

# ========== 配置 ==========
# 加载 skill 保存的配置
CONFIG_DIR="$HOME/.config/agents/skills/idm-gridcore"
if [ -f "$CONFIG_DIR/state/local_cluster.json" ]; then
    # 使用本地集群
    MODE="local"
    COMPUTEHUB_URL=$(jq -r '.computehub.url' "$CONFIG_DIR/state/local_cluster.json")
    TOKEN=$(jq -r '.token' "$CONFIG_DIR/state/local_cluster.json")
    REDIS_URL=$(jq -r '.redis.url' "$CONFIG_DIR/state/local_cluster.json")
elif [ -f "$CONFIG_DIR/skill.toml" ]; then
    # 使用预设集群
    MODE="remote"
    source "$CONFIG_DIR/skill.toml"
    COMPUTEHUB_URL=$CLUSTER_PRODUCTION_COMPUTEHUB_URL
    TOKEN=$(grep token "$CONFIG_DIR/credentials.toml" | cut -d'"' -f2)
    REDIS_URL=$CLUSTER_PRODUCTION_REDIS_URL
else
    echo "错误：未找到集群配置，请先部署或连接集群"
    exit 1
fi

# ========== 步骤 1：创建计算容器 ==========
# 创建临时目录
WORKDIR=$(mktemp -d)
cd "$WORKDIR"

# 生成消费者代码（计算平方根）
cat > consumer.py << 'EOF'
import redis
import os
import math

INPUT_REDIS_URL = os.getenv("INPUT_REDIS_URL")
OUTPUT_REDIS_URL = os.getenv("OUTPUT_REDIS_URL", INPUT_REDIS_URL)
INPUT_QUEUE = os.getenv("INPUT_QUEUE", "task:input")
OUTPUT_QUEUE = os.getenv("OUTPUT_QUEUE", "task:output")
INSTANCE_ID = os.getenv("INSTANCE_ID", "0")

r_in = redis.from_url(INPUT_REDIS_URL)
r_out = redis.from_url(OUTPUT_REDIS_URL)

while True:
    result = r_in.brpop(INPUT_QUEUE, timeout=5)
    if result is None:
        if r_in.llen(INPUT_QUEUE) == 0:
            break
        continue
    
    _, task_data = result
    n = float(task_data.decode() if isinstance(task_data, bytes) else task_data)
    
    # 计算平方根
    result = math.sqrt(n)
    
    # 写回结果
    output = f"{n}:{result}"
    r_out.lpush(OUTPUT_QUEUE, output)
EOF

# 生成 Dockerfile
cat > Dockerfile << 'EOF'
FROM python:3.11-slim
RUN pip install redis
COPY consumer.py /app/consumer.py
CMD ["python", "/app/consumer.py"]
EOF

# 构建镜像
docker build -t idm-task:sqrt .

# ========== 步骤 2：注册任务 ==========

# 单镜像（所有架构通用，推荐）
curl -X POST "${COMPUTEHUB_URL}/api/tasks" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "sqrt-calc",
    "image": "idm-task:sqrt",
    "input_redis": "'"${REDIS_URL}"'",
    "output_redis": "'"${REDIS_URL}"'",
    "input_queue": "sqrt:input",
    "output_queue": "sqrt:output"
  }'

# 多架构镜像（不同架构使用不同镜像标签）
# 支持的架构：linux/amd64 (x86_64), linux/arm64 (ARM64), linux/arm/v7 (ARM32)
# curl -X POST "${COMPUTEHUB_URL}/api/tasks" \
#   -H "Authorization: Bearer ${TOKEN}" \
#   -H "Content-Type: application/json" \
#   -d '{
#     "name": "sqrt-calc",
#     "images": {
#       "linux/amd64": "your-registry/hea-calc:v1.0-amd64",
#       "linux/arm64": "your-registry/hea-calc:v1.0-arm64"
#     },
#     "input_redis": "'"${REDIS_URL}"'",
#     "input_queue": "sqrt:input",
#     "output_queue": "sqrt:output"
#   }'

echo "任务已注册"

# ========== 步骤 3：推送数据 ==========
# 生成测试数据：1 到 10000
python3 << EOF
import redis
r = redis.from_url("$REDIS_URL")
r.delete("sqrt:input", "sqrt:output")

# 批量推送
batch = []
for i in range(1, 10001):
    batch.append(str(i))
    if len(batch) >= 1000:
        r.lpush("sqrt:input", *batch)
        batch = []
if batch:
    r.lpush("sqrt:input", *batch)

print(f"已推送 {r.llen('sqrt:input')} 个任务")
EOF

# ========== 步骤 4：监控进度 ==========
echo "开始监控进度..."
python3 << EOF
import redis
import time
import sys

r = redis.from_url("$REDIS_URL")
total = r.llen("sqrt:input") + r.llen("sqrt:output")

while True:
    pending = r.llen("sqrt:input")
    done = r.llen("sqrt:output")
    
    if total > 0:
        progress = done / total * 100
        print(f"\r进度: {done}/{total} ({progress:.1f}%)", end='', flush=True)
    
    if pending == 0:
        print("\n完成!")
        break
    
    time.sleep(1)
EOF

# ========== 步骤 5：获取结果 ==========
echo "前 10 个结果："
redis-cli -u "$REDIS_URL" lrange sqrt:output 0 9

# 清理
rm -rf "$WORKDIR"
```

---

## 常用操作命令

### API 列表

所有 API 都需要认证头 `Authorization: Bearer <token>`，除了 `/health`。

```yaml
user_apis:
  - endpoint: /api/tasks
    method: POST
    description: 注册新任务
  - endpoint: /api/tasks
    method: GET
    description: 查看任务队列
  - endpoint: /api/tasks/next
    method: POST
    description: 切换到下一个任务（旧接口，建议使用 finish）
  - endpoint: /api/tasks/finish
    method: POST
    description: 完成当前任务，自动开始下一个（推荐）
  - endpoint: /api/nodes
    method: GET
    description: 查看在线节点列表
  - endpoint: /api/nodes/:node_id/stop
    method: POST
    description: 请求指定节点优雅停止

gridnode_internal_apis:
  - endpoint: /gridnode/register
    method: POST
    description: 节点注册（首次启动时）
  - endpoint: /gridnode/heartbeat
    method: POST
    description: 心跳上报，返回包含 stop_requested 字段
  - endpoint: /gridnode/task
    method: GET
    description: 获取当前任务配置

public_apis:
  - endpoint: /health
    method: GET
    description: 健康检查，无需认证，返回 OK
```

### 查看集群状态

```bash
# 加载配置
TOKEN="你的token"
COMPUTEHUB_URL="http://localhost:8080"

# 查看在线节点
curl -H "Authorization: Bearer ${TOKEN}" \
  "${COMPUTEHUB_URL}/api/nodes" | jq .

# 查看任务列表
curl -H "Authorization: Bearer ${TOKEN}" \
  "${COMPUTEHUB_URL}/api/tasks" | jq .
```

### 手动推送任务数据

```bash
REDIS_URL="redis://:password@localhost:6379"

# 推送单个数据
redis-cli -u "$REDIS_URL" lpush mytask:input "task_data"

# 批量推送（使用管道）
for i in {1..1000}; do
    echo "LPUSH mytask:input \"$i\""
done | redis-cli -u "$REDIS_URL" --pipe
```

### 查看队列长度

```bash
redis-cli -u "$REDIS_URL" llen mytask:input   # 待处理
redis-cli -u "$REDIS_URL" llen mytask:output  # 已完成
```

### 停止节点

```bash
# 远程停止指定节点
NODE_ID="节点id"
curl -X POST "${COMPUTEHUB_URL}/api/nodes/${NODE_ID}/stop" \
  -H "Authorization: Bearer ${TOKEN}"
```

### 完成任务并切换到下一个

当当前任务的 Redis 队列空了（人工确认）：

```bash
curl -X POST "${COMPUTEHUB_URL}/api/tasks/finish" \
  -H "Authorization: Bearer ${TOKEN}"
```

响应示例（有下一个任务）：
```json
{
  "completed": "task-1",
  "started": "task-2",
  "message": "Task 'task-1' completed, 'task-2' started"
}
```

响应示例（最后一个任务）：
```json
{
  "completed": "task-1",
  "started": null,
  "message": "Task 'task-1' completed, no more tasks"
}
```

所有计算节点会自动切换到下一个任务。

---

## Docker 镜像构建注意事项

### 跨平台兼容性（重要）

GridNode 在 Linux 容器中运行任务。如果你在 macOS 或 Windows 上开发，**绝对不能直接复制本地编译的二进制到镜像中**。

**错误做法**（会导致 Exec format error）：
```dockerfile
# 在 macOS 上编译，复制到 Linux 容器 -> 失败
COPY ./target/release/myapp /usr/local/bin/myapp
```

**正确做法**：使用多阶段构建，在 Linux 容器中编译

```dockerfile
# 阶段 1：在 Linux 容器中编译
FROM rustlang/rust:nightly-bookworm AS builder

WORKDIR /app
COPY Cargo.toml Cargo.lock ./
COPY src ./src
RUN cargo build --release

# 阶段 2：运行时镜像
FROM debian:bookworm-slim
COPY --from=builder /app/target/release/myapp /usr/local/bin/myapp
CMD ["myapp"]
```

Python 项目同理：
```dockerfile
FROM python:3.11-slim AS builder
# ... 安装依赖

FROM python:3.11-slim
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
```

### 快速验证镜像

```bash
# 启动容器检查是否能正常运行
docker run --rm your-image your-command

# 检查容器日志
docker logs <container-id>
```

---

## 容器环境变量

计算容器启动时会注入以下环境变量：

```yaml
env_vars:
  TASK_NAME: 任务名称
  NODE_ID: 节点 ID
  INSTANCE_ID: 容器实例 ID
  INPUT_REDIS_URL: 输入队列 Redis 地址
  OUTPUT_REDIS_URL: 输出队列 Redis 地址
  INPUT_QUEUE: 输入队列名
  OUTPUT_QUEUE: 输出队列名
```

容器内部使用这些变量连接 Redis 获取任务。示例：

```python
import redis
import os

r_in = redis.from_url(os.getenv("INPUT_REDIS_URL"))
r_out = redis.from_url(os.getenv("OUTPUT_REDIS_URL"))
input_queue = os.getenv("INPUT_QUEUE")
output_queue = os.getenv("OUTPUT_QUEUE")

while True:
    result = r_in.brpop(input_queue, timeout=5)
    if not result:
        break
    # 处理任务...
    r_out.lpush(output_queue, "result")
```

---

## 内置任务模板

### 模板 1：图片处理

```python
# 自动生成的消费者代码
from PIL import Image
import os

input_path = os.getenv("TASK_INPUT")
output_path = os.getenv("TASK_OUTPUT")
operation = os.getenv("OPERATION")  # resize/watermark/convert

img = Image.open(input_path)

if operation == "resize":
    width = int(os.getenv("WIDTH", 300))
    img.thumbnail((width, width))
elif operation == "watermark":
    # 添加水印逻辑
    pass

img.save(output_path)
```

### 模板 2：HTTP 批量请求

```python
import requests
import redis
import os

# 从队列取 URL，请求后存结果
r_in = redis.from_url(os.getenv("INPUT_REDIS_URL"))
r_out = redis.from_url(os.getenv("OUTPUT_REDIS_URL"))

while True:
    result = r_in.brpop(os.getenv("INPUT_QUEUE"), timeout=5)
    if not result:
        break
    
    url = result[1].decode()
    try:
        resp = requests.get(url, timeout=30)
        r_out.lpush(os.getenv("OUTPUT_QUEUE"), 
                   f"{url}:{resp.status_code}:{len(resp.text)}")
    except Exception as e:
        r_out.lpush(os.getenv("OUTPUT_QUEUE"), f"{url}:ERROR:{str(e)}")
```

---

## 构建可靠的任务镜像

### 推荐：使用 ENTRYPOINT 而非依赖 cmd 参数

GridNode 注册任务时可以传递 `cmd` 参数来覆盖容器默认命令，但实践中发现这不够可靠（GridNode 可能因版本或配置问题未能正确传递）。

**推荐做法**：使用 `ENTRYPOINT` 脚本将启动逻辑内置于镜像中。

#### 不可靠的方式

```dockerfile
FROM python:3.11-slim
COPY consumer.py /app/
CMD ["python", "/app/consumer.py"]  # 依赖 GridNode 传 cmd 覆盖
```

```bash
# 注册任务时传 cmd（可能不生效）
curl -X POST "${COMPUTEHUB_URL}/api/tasks" \
  -d '{
    "name": "my-task",
    "image": "my-image",
    "cmd": ["python", "/app/consumer.py"],
    ...
  }'
```

#### 推荐方式

**entrypoint.sh**:
```bash
#!/bin/bash
# 从环境变量读取配置（GridNode 自动注入）
INPUT_REDIS_URL="${INPUT_REDIS_URL:-redis://localhost:6379}"
OUTPUT_QUEUE="${OUTPUT_QUEUE:-task:output}"

# 启动任务
exec python /app/consumer.py \
  --redis-url "$INPUT_REDIS_URL" \
  --output-queue "$OUTPUT_QUEUE"
```

**Dockerfile**:
```dockerfile
FROM python:3.11-slim

# 安装依赖
RUN pip install redis

# 复制代码
COPY consumer.py /app/

# 复制启动脚本
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# 使用 ENTRYPOINT（不依赖外部 cmd 参数）
ENTRYPOINT ["/entrypoint.sh"]
```

```bash
# 注册任务时无需传 cmd
curl -X POST "${COMPUTEHUB_URL}/api/tasks" \
  -d '{
    "name": "my-task",
    "image": "my-image",
    "input_redis": "redis://localhost:6379",
    "input_queue": "task:input",
    "output_queue": "task:output"
  }'
```

**好处**：
- 镜像自包含，不依赖 GridNode 正确传递 `cmd`
- 可以从环境变量读取动态配置（GridNode 自动注入）
- 更容易测试：`docker run my-image` 即可

---

## 故障排查

### 问题 1：Docker 权限不足

**症状**：GridNode 启动报错 "permission denied"

**解决**：
```bash
# 将用户加入 docker 组
sudo usermod -aG docker $USER
newgrp docker

# 或临时使用 sudo
sudo gridnode
```

### 问题 2：GridNode 无法注册

**症状**：日志显示 "Failed to register: HTTP 401"

**排查**：
```bash
# 获取配置路径
if [[ "$OSTYPE" == "darwin"* ]]; then
    CONFIG_DIR="$HOME/Library/Application Support/idm-gridcore"
else
    CONFIG_DIR="$HOME/.config/idm-gridcore"
fi

# 检查 token 是否匹配
grep token "$CONFIG_DIR/computehub.toml"
grep token "$CONFIG_DIR/gridnode.toml"

# 检查网络连通性
curl http://localhost:8080/health
```

### 问题 3：任务已注册但容器不启动

**检查清单**：
1. 任务状态是否为 Running？`curl .../api/tasks`
2. 镜像是否存在？`docker images`
3. GridNode 日志查看错误
4. 手动测试容器：`docker run --rm idm-task:xxx`

### 问题 4：节点状态为 Error 且新任务不启动

**症状**：
- 查看节点状态显示 `"runtime_status": "Error"`
- 注册新任务后容器不启动
- GridNode 日志显示之前的错误状态未清除

**原因**：
GridNode 只有在检测到**新任务**（任务变化）时才会清除错误状态。如果当前任务一直处于 Error 状态，新注册的任务可能不会触发状态清除。

**解决方案**：

**推荐**：调用 finish 接口完成当前任务
```bash
# 将当前报错任务标记为完成，自动切换到下一个任务
# GridNode 检测到任务变化，自动清除错误状态
curl -X POST "${COMPUTEHUB_URL}/api/tasks/finish" \
  -H "Authorization: Bearer ${TOKEN}"

# 然后注册新任务
curl -X POST "${COMPUTEHUB_URL}/api/tasks" \
  -H "Authorization: Bearer ${TOKEN}" \
  -d '{"name": "my-task", "image": "..."}'
```

**备选 1**：使用不同名称重新注册任务
```bash
# 使用新名称（如加版本号）
curl -X POST "${COMPUTEHUB_URL}/api/tasks" \
  -d '{"name": "my-task-v2", ...}'
```

**备选 2**：重启 GridNode
```bash
kill $(cat /tmp/gridnode.pid)
nohup ./gridnode -c ~/.config/idm-gridcore/gridnode.toml &
```

### 问题 5：队列有数据但无输出

**排查**：
```bash
# 检查 Redis 连接
redis-cli -u $REDIS_URL ping

# 查看容器日志
docker logs idm-taskname-nodeid-0

# 检查环境变量
docker inspect idm-taskname-nodeid-0 | grep Env
```

---

## 最佳实践

1. **任务数据分片大小**：每个任务处理 100ms-1s 为宜，太小会增加调度开销
2. **批量推送**：使用管道批量推送，比单条快 10 倍以上
3. **监控队列**：输入队列应保持非空，确保节点满载
4. **优雅停止**：任务完成后调用 `/api/tasks/finish` 切换，不直接杀进程
5. **资源清理**：定期清理已停止的容器 `docker container prune`

### 后台运行 ComputeHub 和 GridNode

**重要**：ComputeHub 和 GridNode 默认在前台运行，关闭终端会导致它们退出。

**方案 1：使用 nohup（简单快速）**
```bash
# ComputeHub
nohup ./computehub > /tmp/computehub.log 2>&1 &
echo $! > /tmp/computehub.pid

# GridNode
nohup ./gridnode > /tmp/gridnode.log 2>&1 &
echo $! > /tmp/gridnode.pid

# 停止时
kill $(cat /tmp/computehub.pid)
kill $(cat /tmp/gridnode.pid)
```

**方案 2：使用 systemd（生产环境推荐）**
```bash
# /etc/systemd/system/computehub.service
[Unit]
Description=IDM-GridCore ComputeHub
After=network.target

[Service]
Type=simple
ExecStart=/usr/local/bin/computehub
Restart=always
RestartSec=5
User=compute

[Install]
WantedBy=multi-user.target
```

**方案 3：使用 launchd（macOS）**
```xml
# ~/Library/LaunchAgents/com.idm.gridnode.plist
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "...">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.idm.gridnode</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/local/bin/gridnode</string>
    </array>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/gridnode.log</string>
</dict>
</plist>
```

---

## 状态文件说明

skill 自动管理的配置文件：

```
~/.config/agents/skills/idm-gridcore/
├── skill.toml              # 集群连接配置
├── credentials.toml        # 敏感凭证（token）
└── state/
    ├── local_cluster.json  # 本机部署信息
    └── remote_nodes.json   # 远程节点记录
```

**不要手动编辑 state/ 下的文件**，skill 会自动维护。

---

## 相关链接

- **IDM-GridCore 项目（接口源码）**: https://github.com/Wolido/idm-gridcore
  - 所有 API 接口定义、数据模型、协议规范请查阅此仓库
- 架构文档：https://github.com/Wolido/idm-gridcore/blob/main/ARCHITECTURE.md
- 故障排查：https://github.com/Wolido/idm-gridcore/blob/main/TROUBLESHOOTING.md

---

## 快速参考规则

以下规则凝练自实战经验，无需理解上下文即可直接应用。

### 规则0：Redis 密码是全局契约，必须首先确认

**部署前必须明确 Redis 密码**，并在所有环节保持一致：

```yaml
涉及密码的环节:
  - Redis 启动: --requirepass $PASSWORD
  - 数据推送:   --redis-password $PASSWORD 或 URL 中包含密码
  - 任务注册:   input_redis URL 必须包含密码
  - 容器内:     通过 INPUT_REDIS_URL 环境变量传递（已包含密码）

密码不匹配的后果:
  - 推送阶段: "NOAUTH: Authentication required"
  - 容器启动: 连接 Redis 失败，容器反复退出
  - GridNode: runtime_status 变为 Error

最佳实践:
  - 生成随机密码并记录
  - 在所有命令中使用同一变量 $REDIS_PASSWORD
  - 避免硬编码密码，通过环境变量传递
```

**示例流程**：
```bash
# 1. 定义密码（一次定义，全局使用）
export REDIS_PASSWORD="$(openssl rand -hex 16)"

# 2. 启动 Redis（使用密码）
docker run -d --name redis -e REDIS_PASSWORD=$REDIS_PASSWORD redis:7-alpine \
  redis-server --requirepass $REDIS_PASSWORD

# 3. 推送数据（使用密码）
./myapp push --redis-password $REDIS_PASSWORD

# 4. 注册任务（URL 包含密码）
REDIS_URL="redis://:$REDIS_PASSWORD@host:6379"
curl -X POST /api/tasks -d "{\"input_redis\":\"$REDIS_URL\",...}"
```

### 规则1：信任编排器注入的完整URL

**禁止拆解** `INPUT_REDIS_URL`，必须作为不透明字符串使用。

```bash
# 正确
myapp --redis-url "$INPUT_REDIS_URL"

# 错误（丢失可能的TLS参数、集群拓扑信息）
REDIS_HOST=$(echo $INPUT_REDIS_URL | sed 's/.*@//;s/:.*//')
myapp --redis-host "$REDIS_HOST" --port 6379
```

### 规则2：entrypoint必须使用ENTRYPOINT

Dockerfile 中**永不使用 CMD**，确保 GridNode 不传 `cmd` 参数也能运行。

```dockerfile
# 正确
ENTRYPOINT ["/entrypoint.sh"]

# 错误（依赖 GridNode 传递 cmd）
CMD ["python", "app.py"]
```

### 规则3：启动阶段必须验证连接并快速失败

```bash
#!/bin/bash
set -e

if [ -z "$INPUT_REDIS_URL" ]; then
    echo '{"error":"INPUT_REDIS_URL not set"}' >&2
    exit 1
fi

# 可选：立即测试连接
if ! myapp --test-connection "$INPUT_REDIS_URL" 2>/dev/null; then
    echo '{"error":"Redis connection failed"}' >&2
    exit 1
fi

exec myapp --redis-url "$INPUT_REDIS_URL"
```

### 规则4：跨平台构建必须多阶段

**绝对禁止**复制宿主机编译的二进制到 Linux 容器。

```dockerfile
FROM rustlang/rust:nightly-bookworm AS builder
COPY . .
RUN cargo build --release

FROM debian:bookworm-slim
COPY --from=builder /app/target/release/myapp /usr/local/bin/myapp
```

### 规则5：观测只看两个端点

GridNode 远程时，**唯一可信观测点**：

```yaml
ComputeHub_API:
  endpoint: /api/nodes
  fields:
    - runtime_status    # Online/Error
    - active_containers # 实际运行的容器数
  meaning: 节点健康状态

Redis:
  commands:
    - llen input   # 待处理任务数
    - llen output  # 已完成任务数
  meaning: 任务处理进度

禁止依赖:
  - 容器日志
  - Docker 命令
  - 宿主机文件系统
```

### 规则6：修复配置后必须重置状态

GridNode 的 `runtime_status: Error` 是**粘滞状态**。

```bash
# 修复镜像/配置后，必须执行：
curl -X POST /api/tasks/finish -H "Authorization: Bearer $TOKEN"
# 或重启 GridNode
```

### 规则7：任务必须是幂等的

同一任务可以安全运行多次，结果一致。GridNode 可能在容器失败后重发任务。

```python
# 消费者逻辑
while True:
    task = redis.brpop(INPUT_QUEUE, timeout=5)
    if not task:
        break
    result = process(task)  # 幂等：重复执行结果相同
    redis.lpush(OUTPUT_QUEUE, result)
```

### 规则8：数据文件打包进镜像

将只读数据（如 `data.csv`）打包进镜像，减少运行时依赖。

```dockerfile
COPY data.csv /data/data.csv
```

避免运行时通过 volume 挂载，因为远程 GridNode 不一定能访问本机路径。

### 规则9：Redis CLI 是必需工具

远程 Redis 场景下，**必须**在宿主机安装 redis-cli：

```bash
brew install redis
```

唯一观测手段：
```bash
redis-cli -h $REDIS_HOST -a $PASSWORD llen input
redis-cli -h $REDIS_HOST -a $PASSWORD lrange output 0 9
```

### 规则10：标准流水线三阶段

所有任务遵循相同模式：

```yaml
pipeline:
  generator:   # 本机运行
    action: push
    target: Redis input queue
    
  consumer:    # GridNode 运行（容器内）
    action: process
    properties:
      - stateless
      - idempotent
      
  collector:   # 本机运行
    action: pull
    source: Redis output queue
    target: persistent storage
```

---

## 最小可复用模板

### Dockerfile 模板

```dockerfile
FROM rustlang/rust:nightly-bookworm AS builder
WORKDIR /app
COPY Cargo.toml Cargo.lock ./
COPY src ./src
RUN cargo build --release

FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y ca-certificates libssl3 && rm -rf /var/lib/apt/lists/*
COPY --from=builder /app/target/release/myapp /usr/local/bin/myapp
COPY data.csv /data/data.csv
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
```

### entrypoint.sh 模板

```bash
#!/bin/bash
set -e

INPUT_REDIS_URL="${INPUT_REDIS_URL}"
INPUT_QUEUE="${INPUT_QUEUE:-tasks}"
OUTPUT_QUEUE="${OUTPUT_QUEUE:-results}"

if [ -z "$INPUT_REDIS_URL" ]; then
    echo '{"error":"INPUT_REDIS_URL not set"}' >&2
    exit 1
fi

echo "Starting task..."
echo "Queue: $INPUT_QUEUE -> $OUTPUT_QUEUE"

exec myapp \
    --redis-url "$INPUT_REDIS_URL" \
    --input-queue "$INPUT_QUEUE" \
    --output-queue "$OUTPUT_QUEUE"
```

### 部署检查清单

```yaml
steps:
  build:
    command: docker build -t mytask:latest .
    
  push_data:
    command: ./myapp push --redis-url redis://:pass@host:6379
    
  register_task:
    endpoint: POST /api/tasks
    headers:
      Authorization: Bearer $TOKEN
    body:
      name: mytask
      image: mytask:latest
      input_redis: redis://:pass@host:6379
      input_queue: tasks
      output_queue: results
      
  monitor:
    command: watch -n 1 'redis-cli -a pass llen tasks && redis-cli -a pass llen results'
```

---

## 故障排查速查表

```yaml
symptoms:
  - phenomenon: 队列不减少
    check: curl /api/nodes 看 runtime_status
    fix:
      - if Error: 调用 /finish 或重启 GridNode
      
  - phenomenon: active_containers=0
    check: docker ps 看镜像是否存在
    fix: 重新构建/推送镜像
    
  - phenomenon: 容器反复退出
    check: docker run --rm mytask:latest 本机测试
    fix: 检查 entrypoint.sh 是否正确读取环境变量
    
  - phenomenon: Redis 连接失败
    check: redis-cli ping
    fix: 检查密码、网络、URL 格式
    
  - phenomenon: 节点状态 Error 不恢复
    root_cause: 状态机粘滞性
    fix: 必须触发任务切换或重启 GridNode
```
