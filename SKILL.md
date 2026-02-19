---
name: agent-idm-gridcore
description: Use when needing to process 10k+ small tasks in parallel using distributed computing cluster. For batch image processing, API calls, data transformation, or numerical computations.
---

# IDM-GridCore 分布式计算

调用分布式计算集群加速"小计算、大批量"任务。

**源码与接口文档**: https://github.com/Wolido/idm-gridcore

## 何时使用

**适合:**
- 1万+ 次重复计算，单次 < 1秒
- 数据可分片独立处理
- 批量图片处理、API 调用、数据清洗、数值计算

**不适合:**
- 单次计算数小时的大型科学计算
- 任务间有强依赖必须串行
- 需要严格事务一致性
- 数据量 < 1000条

## 使用模式

```yaml
模式选择:
  从零启动: 没有集群，临时本地部署
  连接已有: 使用公司/团队共享集群
```

## 从零启动（本地部署）

### 1. 检查环境

```bash
docker ps  # 确认 Docker 可用
lsof -i :8080  # 检查端口占用
lsof -i :6379
```

### 2. 下载二进制

```bash
# 查看 release 文件
RELEASE_URL="https://api.github.com/repos/Wolido/idm-gridcore/releases/latest"
curl -s "$RELEASE_URL" | grep "browser_download_url"

# 根据实际文件名下载（示例）
mkdir -p ~/.local/share/idm-gridcore/bin
curl -L -o computehub "<download_url_computehub>"
curl -L -o gridnode "<download_url_gridnode>"
chmod +x computehub gridnode
```

### 3. 生成配置

```bash
# 检测平台
if [[ "$OSTYPE" == "darwin"* ]]; then
    CONFIG_DIR="$HOME/Library/Application Support/idm-gridcore"
else
    CONFIG_DIR="$HOME/.config/idm-gridcore"
fi
mkdir -p "$CONFIG_DIR"

# 生成 token
TOKEN="skill-$(openssl rand -hex 16)"

# ComputeHub 配置
cat > "$CONFIG_DIR/computehub.toml" << EOF
bind = "0.0.0.0:8080"
token = "$TOKEN"
EOF

# GridNode 配置
cat > "$CONFIG_DIR/gridnode.toml" << EOF
server_url = "http://localhost:8080"
token = "$TOKEN"
EOF
```

### 4. 启动服务

```bash
# 启动 Redis
docker run -d --name redis -p 6379:6379 redis:7-alpine \
  redis-server --requirepass changeme

# 启动 ComputeHub
nohup computehub -c "$CONFIG_DIR/computehub.toml" > /tmp/computehub.log 2>&1 &
curl http://localhost:8080/health  # 验证

# 启动 GridNode
nohup gridnode -c "$CONFIG_DIR/gridnode.toml" > /tmp/gridnode.log 2>&1 &
curl -H "Authorization: Bearer $TOKEN" http://localhost:8080/api/nodes
```

## 连接已有集群

```bash
# 保存配置
mkdir -p ~/.config/agents/skills/agent-idm-gridcore

cat > skill.toml << EOF
[cluster.production]
computehub_url = "http://host:8080"
redis_url = "redis://:pass@host:6379"
EOF

cat > credentials.toml << EOF
[cluster.production]
token = "your-token"
EOF
chmod 600 credentials.toml
```

## 任务提交流程

### 完整示例：批量计算平方根

```bash
#!/bin/bash

# ========== 配置 ==========
CONFIG_DIR="$HOME/.config/agents/skills/agent-idm-gridcore"

if [ -f "$CONFIG_DIR/state/local_cluster.json" ]; then
    COMPUTEHUB_URL=$(jq -r '.computehub.url' "$CONFIG_DIR/state/local_cluster.json")
    TOKEN=$(jq -r '.token' "$CONFIG_DIR/state/local_cluster.json")
    REDIS_URL=$(jq -r '.redis.url' "$CONFIG_DIR/state/local_cluster.json")
elif [ -f "$CONFIG_DIR/skill.toml" ]; then
    source "$CONFIG_DIR/skill.toml"
    COMPUTEHUB_URL=$CLUSTER_PRODUCTION_COMPUTEHUB_URL
    TOKEN=$(grep token "$CONFIG_DIR/credentials.toml" | cut -d'"' -f2)
    REDIS_URL=$CLUSTER_PRODUCTION_REDIS_URL
else
    echo "错误：未找到集群配置"
    exit 1
fi

# ========== 1. 创建计算容器 ==========
WORKDIR=$(mktemp -d)
cd "$WORKDIR"

# 消费者代码
cat > consumer.py << 'EOF'
import redis, os, math

r_in = redis.from_url(os.getenv("INPUT_REDIS_URL"))
r_out = redis.from_url(os.getenv("OUTPUT_REDIS_URL"))
input_q = os.getenv("INPUT_QUEUE")
output_q = os.getenv("OUTPUT_QUEUE")

while True:
    result = r_in.brpop(input_q, timeout=5)
    if result is None:
        if r_in.llen(input_q) == 0:
            break
        continue
    _, data = result
    n = float(data.decode() if isinstance(data, bytes) else data)
    r_out.lpush(output_q, f"{n}:{math.sqrt(n)}")
EOF

# Dockerfile
cat > Dockerfile << 'EOF'
FROM python:3.11-slim
RUN pip install redis
COPY consumer.py /app/
CMD ["python", "/app/consumer.py"]
EOF

docker build -t idm-task:sqrt .

# ========== 2. 注册任务 ==========
curl -X POST "${COMPUTEHUB_URL}/api/tasks" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d "{
    \"name\": \"sqrt-calc\",
    \"image\": \"idm-task:sqrt\",
    \"input_redis\": \"${REDIS_URL}\",
    \"output_redis\": \"${REDIS_URL}\",
    \"input_queue\": \"sqrt:input\",
    \"output_queue\": \"sqrt:output\"
  }"

# ========== 3. 推送数据 ==========
python3 << EOF
import redis
r = redis.from_url("$REDIS_URL")
r.delete("sqrt:input", "sqrt:output")
for i in range(1, 10001):
    r.lpush("sqrt:input", str(i))
print(f"已推送 {r.llen('sqrt:input')} 个任务")
EOF

# ========== 4. 监控进度 ==========
python3 << EOF
import redis, time, sys
r = redis.from_url("$REDIS_URL")
total = r.llen("sqrt:input") + r.llen("sqrt:output")
while True:
    pending = r.llen("sqrt:input")
    done = r.llen("sqrt:output")
    if total > 0:
        print(f"\r进度: {done}/{total} ({done/total*100:.1f}%)", end='', flush=True)
    if pending == 0:
        print("\n完成!")
        break
    time.sleep(1)
EOF

# 查看结果
redis-cli -u "$REDIS_URL" lrange sqrt:output 0 9
rm -rf "$WORKDIR"
```

## 常用命令

```yaml
查看状态:
  在线节点: curl -H "Authorization: Bearer ${TOKEN}" ${URL}/api/nodes
  任务列表: curl -H "Authorization: Bearer ${TOKEN}" ${URL}/api/tasks
  队列长度: redis-cli -u ${REDIS} llen queue:input

数据操作:
  推送单个: redis-cli -u ${REDIS} lpush queue:data "task"
  批量推送: echo -e "LPUSH q:d 1\nLPUSH q:d 2" | redis-cli --pipe
  查看结果: redis-cli -u ${REDIS} lrange queue:output 0 9

任务管理:
  完成切换: curl -X POST ${URL}/api/tasks/finish -H "Authorization: Bearer ${TOKEN}"
  停止节点: curl -X POST ${URL}/api/nodes/${NODE_ID}/stop -H "Authorization: Bearer ${TOKEN}"

健康检查:
  ComputeHub: curl ${URL}/health
  Redis: redis-cli -u ${REDIS} ping
```

## 关键规则

**规则1: Redis 密码全局一致**
```bash
export REDIS_PASSWORD="$(openssl rand -hex 16)"
# 启动 Redis、推送数据、注册任务必须使用同一密码
```

**规则2: 信任完整 Redis URL**
```bash
# 正确
myapp --redis-url "$INPUT_REDIS_URL"

# 错误（丢失参数）
REDIS_HOST=$(echo $INPUT_REDIS_URL | sed 's/.*@//;s/:.*//')
```

**规则3: Dockerfile 使用 ENTRYPOINT**
```dockerfile
# 正确
ENTRYPOINT ["/app/entrypoint.sh"]

# 错误
CMD ["python", "app.py"]
```

**规则4: 跨平台必须多阶段构建**
```dockerfile
FROM rustlang/rust:nightly AS builder
COPY . .
RUN cargo build --release

FROM debian:bookworm-slim
COPY --from=builder /app/target/release/myapp /usr/local/bin/myapp
```

## 容器环境变量

容器启动时自动注入：
- `TASK_NAME` - 任务名称
- `INPUT_REDIS_URL` / `OUTPUT_REDIS_URL` - Redis 连接
- `INPUT_QUEUE` / `OUTPUT_QUEUE` - 队列名
- `NODE_ID` / `INSTANCE_ID` - 节点信息

## 故障排查

| 症状 | 原因 | 解决 |
|------|------|------|
| Exec format error | macOS 二进制复制到 Linux 容器 | 使用多阶段构建 |
| NOAUTH 错误 | Redis 密码不匹配 | 检查所有环节密码一致 |
| 容器反复退出 | 连接 Redis 失败 | 检查 URL 和密码 |
| 节点不在线 | GridNode 未启动或 token 错误 | 检查日志和配置 |

**详细排查**: 参见 `references/troubleshooting.md`

## 参考

- **完整规则**: `references/rules.md`
- **Docker 构建**: `references/docker-build.md`
- **故障排查**: `references/troubleshooting.md`
- **项目源码**: https://github.com/Wolido/idm-gridcore
