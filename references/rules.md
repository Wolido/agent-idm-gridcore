# IDM-GridCore 快速参考规则

## 规则0：Redis 密码是全局契约

**部署前必须明确 Redis 密码**，所有环节保持一致：

```yaml
密码使用环节:
  Redis 启动: --requirepass $PASSWORD
  数据推送: --redis-password $PASSWORD
  任务注册: input_redis URL 必须包含密码
  容器内: 通过 INPUT_REDIS_URL 环境变量传递

密码不匹配后果:
  推送阶段: "NOAUTH: Authentication required"
  容器启动: 连接失败，容器反复退出
  GridNode: runtime_status 变为 Error

最佳实践:
  - 生成随机密码并记录
  - 所有命令使用同一变量 $REDIS_PASSWORD
  - 避免硬编码，通过环境变量传递
```

**示例流程:**
```bash
# 1. 定义密码（一次定义，全局使用）
export REDIS_PASSWORD="$(openssl rand -hex 16)"

# 2. 启动 Redis
docker run -d --name redis -e REDIS_PASSWORD=$REDIS_PASSWORD redis:7-alpine \
  redis-server --requirepass $REDIS_PASSWORD

# 3. 推送数据
./myapp push --redis-password $REDIS_PASSWORD

# 4. 注册任务（URL 包含密码）
REDIS_URL="redis://:$REDIS_PASSWORD@host:6379"
curl -X POST /api/tasks -d "{\"input_redis\":\"$REDIS_URL\",...}"
```

## 规则1：信任编排器注入的完整URL

**禁止拆解** `INPUT_REDIS_URL`，必须作为不透明字符串使用。

```bash
# 正确
myapp --redis-url "$INPUT_REDIS_URL"

# 错误（丢失TLS参数、集群拓扑信息）
REDIS_HOST=$(echo $INPUT_REDIS_URL | sed 's/.*@//;s/:.*//')
myapp --redis-host "$REDIS_HOST" --port 6379
```

## 规则2：entrypoint必须使用ENTRYPOINT

Dockerfile 中**永不使用 CMD**，确保 GridNode 不传 `cmd` 参数也能运行。

```dockerfile
# 正确
ENTRYPOINT ["/entrypoint.sh"]

# 错误（依赖 GridNode 传递 cmd）
CMD ["python", "app.py"]
```

## 规则3：启动阶段必须验证连接并快速失败

```bash
#!/bin/bash
set -e

if [ -z "$INPUT_REDIS_URL" ]; then
    echo '{"error":"INPUT_REDIS_URL not set"}' >&2
    exit 1
fi

# 可选：测试连接
if ! myapp --test-connection "$INPUT_REDIS_URL" 2>/dev/null; then
    echo '{"error":"Redis connection failed"}' >&2
    exit 1
fi

exec myapp --redis-url "$INPUT_REDIS_URL"
```

## 规则4：跨平台构建必须多阶段

**绝对禁止**复制宿主机编译的二进制到 Linux 容器。

```dockerfile
# Rust
FROM rustlang/rust:nightly-bookworm AS builder
COPY . .
RUN cargo build --release

FROM debian:bookworm-slim
COPY --from=builder /app/target/release/myapp /usr/local/bin/myapp
```

```dockerfile
# Python
FROM python:3.11-slim AS builder
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
COPY requirements.txt .
RUN pip install -r requirements.txt

FROM python:3.11-slim
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
COPY . /app
WORKDIR /app
CMD ["python", "app.py"]
```

## 规则5：观测只看两个端点

GridNode 远程时，**唯一可信观测点**：

```yaml
/api/nodes: 查看所有节点 runtime_status（Running/Error/Offline）
Redis 队列: 查看输入/输出队列长度
```

**永远不要**依赖本地日志或进程状态。

## 规则6：幂等消费

消费者必须能够**安全地重复处理**同一任务。

```python
# 非幂等（危险）
result = r_in.brpop(input_queue)
process(result)  # 如果处理完但写输出前崩溃，任务丢失
r_out.lpush(output_queue, result)

# 幂等（安全）
result = r_in.brpop(input_queue)
output = process(result)
# 使用事务或唯一ID确保不重复写入
r_out.lpush(output_queue, json.dumps({
    "task_id": task_id,
    "result": output,
    "timestamp": time.time()
}))
```

## 规则7：优雅停止

**禁止直接 kill -9**，使用 API 请求优雅停止：

```bash
# 正确：请求停止，等待当前任务完成
curl -X POST "${COMPUTEHUB_URL}/api/nodes/${NODE_ID}/stop" \
  -H "Authorization: Bearer ${TOKEN}"

# 或完成任务后自动切换
curl -X POST "${COMPUTEHUB_URL}/api/tasks/finish" \
  -H "Authorization: Bearer ${TOKEN}"
```

## 规则8：监控队列非空

**保持输入队列非空**是性能关键：

```python
# 监控脚本
import redis, time

r = redis.from_url(REDIS_URL)
while True:
    input_len = r.llen("task:input")
    output_len = r.llen("task:output")
    
    if input_len < 100:  # 队列即将空了
        print("警告：输入队列不足，推送更多数据")
        push_more_data()
    
    print(f"输入队列: {input_len}, 输出队列: {output_len}")
    time.sleep(1)
```

## 规则9：批量推送

**使用管道批量推送**，比单条快 10 倍以上：

```bash
# 错误：1000次网络往返
for i in {1..1000}; do
    redis-cli lpush queue:data "$i"
done

# 正确：1次网络往返
echo -e "LPUSH queue:data 1\nLPUSH queue:data 2\n..." | \
  redis-cli --pipe
```

Python:
```python
import redis

r = redis.from_url(REDIS_URL)
pipe = r.pipeline()

for i in range(10000):
    pipe.lpush("queue:input", str(i))
    if i % 1000 == 0:
        pipe.execute()
pipe.execute()  # 执行剩余
```

## 规则10：任务数据大小

**每个任务处理 100ms-1s 为宜**：

```yaml
太小（<10ms）:
  问题: 调度开销占比高
  解决: 合并多个小任务

适中（100ms-1s）:
  效果: 最佳吞吐量

太大（>10s）:
  问题: 节点利用率不均
  解决: 拆分任务
```
