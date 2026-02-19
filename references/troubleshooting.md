# IDM-GridCore 故障排查

## 容器启动失败

### Exec format error

**现象:**
```
exec /app/myapp: exec format error
```

**原因:** 在 macOS 上编译的二进制直接复制到 Linux 容器中运行。

**解决:** 使用多阶段构建
```dockerfile
FROM rustlang/rust:nightly-bookworm AS builder
WORKDIR /app
COPY . .
RUN cargo build --release

FROM debian:bookworm-slim
COPY --from=builder /app/target/release/myapp /usr/local/bin/myapp
CMD ["myapp"]
```

### NOAUTH: Authentication required

**现象:**
- 推送数据时返回 `NOAUTH`
- 容器无法连接 Redis

**原因:** Redis 密码不一致。

**解决:** 确保所有环节使用同一密码：
```bash
export REDIS_PASSWORD="$(openssl rand -hex 16)"

# 1. 启动 Redis
docker run -d --name redis redis:7-alpine \
  redis-server --requirepass $REDIS_PASSWORD

# 2. 推送数据
redis-cli -a $REDIS_PASSWORD lpush queue:data "task"

# 3. 注册任务（URL 包含密码）
REDIS_URL="redis://:$REDIS_PASSWORD@host:6379"
```

### 容器反复退出

**排查步骤:**

1. **查看容器日志**
```bash
docker logs <container-id>
```

2. **检查环境变量**
```bash
docker run --rm your-image env | grep REDIS
# 应看到 INPUT_REDIS_URL 等变量
```

3. **手动测试连接**
```bash
docker run --rm -e INPUT_REDIS_URL="redis://:pass@host:6379" \
  your-image redis-cli -u $INPUT_REDIS_URL ping
```

## 节点问题

### GridNode 无法注册

**现象:** 调用 `/api/nodes` 返回空列表。

**排查:**
```bash
# 检查 GridNode 日志
tail -f /tmp/gridnode.log

# 验证 token 一致
grep token ~/.config/idm-gridcore/computehub.toml
grep token ~/.config/idm-gridcore/gridnode.toml

# 检查网络连接
curl http://localhost:8080/health
```

### 节点状态为 Error

**现象:** `runtime_status` 显示 `Error`。

**常见原因:**
- Docker 镜像不存在
- 容器启动失败（见上文）
- Redis 连接失败

**解决:**
```bash
# 查看 GridNode 日志
tail -100 /tmp/gridnode.log | grep ERROR

# 重新启动 GridNode
pkill gridnode
nohup gridnode -c "$CONFIG_DIR/gridnode.toml" &
```

## 任务执行问题

### 任务不执行

**排查:**
```bash
# 1. 检查队列是否有数据
redis-cli -u "$REDIS_URL" llen task:input

# 2. 检查节点是否在线
curl -H "Authorization: Bearer $TOKEN" \
  $COMPUTEHUB_URL/api/nodes

# 3. 检查任务配置
curl -H "Authorization: Bearer $TOKEN" \
  $COMPUTEHUB_URL/api/tasks | jq '.[] | {name, input_queue, output_queue}'
```

### 结果为空

**原因:**
- 消费者代码没有写入 output 队列
- 队列名称拼写错误
- 数据处理异常被吞掉

**调试:**
```bash
# 查看容器日志
docker ps -q --filter "label=task=your-task" | xargs docker logs

# 临时修改消费者代码，添加详细日志
```

## 性能问题

### 处理速度低于预期

**排查:**
```bash
# 1. 检查节点数量
curl -H "Authorization: Bearer $TOKEN" $COMPUTEHUB_URL/api/nodes | jq 'length'

# 2. 检查输入队列是否保持非空
watch -n 1 'redis-cli -u $REDIS_URL llen task:input'

# 3. 检查容器资源使用
docker stats

# 4. 检查 GridNode 日志中的处理速度
tail -f /tmp/gridnode.log | grep "processed"
```

### 内存不足

**现象:** 容器被 OOM Kill。

**解决:**
```bash
# 调整容器内存限制（GridNode 配置）
# ~/.config/idm-gridcore/gridnode.toml
container_memory = 2048  # 增加到 2GB
```

## 网络问题

### 连接被拒绝

**现象:** `Connection refused`。

**原因:**
- ComputeHub 未启动
- 防火墙阻止
- 端口配置错误

**排查:**
```bash
# 检查进程
pgrep computehub

# 检查端口监听
lsof -i :8080

# 检查防火墙
sudo iptables -L | grep 8080
```

### Redis 连接超时

**现象:** `Redis connection timeout`。

**排查:**
```bash
# 检查 Redis 是否运行
docker ps | grep redis

# 检查网络连通性
telnet localhost 6379

# 检查密码
redis-cli -a wrong_password ping
```

## 日志收集

```bash
# 收集所有日志用于排查
mkdir -p /tmp/idm-debug

cp /tmp/computehub.log /tmp/idm-debug/
cp /tmp/gridnode.log /tmp/idm-debug/
docker ps -q | xargs -I {} docker logs {} > /tmp/idm-debug/docker.log 2>&1

tar -czf /tmp/idm-debug.tar.gz /tmp/idm-debug/
```
