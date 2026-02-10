---
name: idm-gridcore
description: Agent 的算力调用工具。透明利用 IDM-GridCore 分布式集群加速"小计算、大批量"任务，支持从零快速部署或连接已有集群。
---

# IDM-GridCore Skill 使用指南

让 AI Agent 能够调用分布式计算集群，加速处理大批量小任务。

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

| 场景 | 处理方式 |
|------|----------|
| 没有集群，需要临时启动 | 使用"从零启动"模式 |
| 已有公司/团队共享集群 | 使用"连接已有集群"模式 |
| 不确定 | 默认推荐"从零启动"（最简单） |

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

```bash
# 创建目录
mkdir -p ~/.local/share/idm-gridcore/bin
cd ~/.local/share/idm-gridcore/bin

# 下载对应架构的预编译二进制（从 GitHub Releases）
# 检测当前架构
ARCH=$(uname -m)
if [ "$ARCH" = "x86_64" ]; then
    PLATFORM="linux-x64"
elif [ "$ARCH" = "aarch64" ] || [ "$ARCH" = "arm64" ]; then
    PLATFORM="linux-arm64"
else
    echo "不支持的架构: $ARCH，需要本地编译"
    exit 1
fi

# 下载最新 release
curl -L "https://github.com/Wolido/idm-gridcore/releases/latest/download/computehub-${PLATFORM}" -o computehub
curl -L "https://github.com/Wolido/idm-gridcore/releases/latest/download/gridnode-${PLATFORM}" -o gridnode

chmod +x computehub gridnode
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

```bash
# 创建配置目录
sudo mkdir -p /etc/idm-gridcore

# 生成 ComputeHub 配置
sudo tee /etc/idm-gridcore/computehub.toml > /dev/null << 'EOF'
bind = "0.0.0.0:8080"
token = "skill-generated-token-$(openssl rand -hex 8)"
EOF

# 生成 GridNode 配置
sudo tee /etc/idm-gridcore/gridnode.toml > /dev/null << EOF
server_url = "http://localhost:8080"
token = "$(grep token /etc/idm-gridcore/computehub.toml | cut -d'"' -f2)"
heartbeat_interval = 30
stop_timeout = 30
container_memory = 1024
EOF
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
# 前台启动（调试用）
~/.local/share/idm-gridcore/bin/computehub

# 或后台启动
nohup ~/.local/share/idm-gridcore/bin/computehub > /tmp/computehub.log 2>&1 &
echo $! > /tmp/computehub.pid

# 验证
curl http://localhost:8080/health
# 应返回 OK
```

#### 步骤 5：启动 GridNode

```bash
# 需要 sudo 访问 Docker
sudo ~/.local/share/idm-gridcore/bin/gridnode &
# 注意：首次启动会保存 node_id 到配置文件

# 验证节点注册
curl -H "Authorization: Bearer $(grep token /etc/idm-gridcore/computehub.toml | cut -d'"' -f2)" \
  http://localhost:8080/api/nodes
```

#### 步骤 6：记录部署信息

```bash
# 保存到 skill 配置目录，方便后续管理
mkdir -p ~/.config/agents/skills/idm-gridcore/state

cat > ~/.config/agents/skills/idm-gridcore/state/local_cluster.json << EOF
{
  "mode": "local",
  "computehub": {
    "pid": $(cat /tmp/computehub.pid),
    "binary_path": "$HOME/.local/share/idm-gridcore/bin/computehub",
    "config_path": "/etc/idm-gridcore/computehub.toml",
    "url": "http://localhost:8080"
  },
  "gridnode": {
    "config_path": "/etc/idm-gridcore/gridnode.toml"
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
    TOKEN=$(grep token /etc/idm-gridcore/computehub.toml | cut -d'"' -f2)
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
# 检查 token 是否匹配
grep token /etc/idm-gridcore/computehub.toml
grep token /etc/idm-gridcore/gridnode.toml

# 检查网络连通性
curl http://localhost:8080/health
```

### 问题 3：任务已注册但容器不启动

**检查清单**：
1. 任务状态是否为 Running？`curl .../api/tasks`
2. 镜像是否存在？`docker images`
3. GridNode 日志查看错误
4. 手动测试容器：`docker run --rm idm-task:xxx`

### 问题 4：队列有数据但无输出

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

- IDM-GridCore 项目：https://github.com/Wolido/idm-gridcore
- 架构文档：https://github.com/Wolido/idm-gridcore/blob/main/ARCHITECTURE.md
- 故障排查：https://github.com/Wolido/idm-gridcore/blob/main/TROUBLESHOOTING.md
