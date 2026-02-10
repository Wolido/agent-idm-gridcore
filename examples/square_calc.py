#!/usr/bin/env python3
"""
IDM-GridCore 示例：计算 1 到 N 的平方
展示完整的任务提交流程
"""

import subprocess
import tempfile
import os
import json


def run_command(cmd, cwd=None):
    """运行 shell 命令"""
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=cwd)
    return result.returncode == 0, result.stdout, result.stderr


def main():
    # 配置
    N = 10000  # 计算 1 到 10000 的平方
    COMPUTEHUB_URL = "http://localhost:8080"
    TOKEN = "your-token-here"  # 替换为实际的 token
    REDIS_URL = "redis://:password@localhost:6379"
    
    print(f"示例：计算 1 到 {N} 的平方")
    print("=" * 50)
    
    # 创建临时工作目录
    with tempfile.TemporaryDirectory() as workdir:
        print(f"\n1. 创建临时目录: {workdir}")
        
        # 步骤 1：创建消费者代码
        print("\n2. 生成消费者代码...")
        consumer_code = '''
import redis
import os
import math

INPUT_REDIS_URL = os.getenv("INPUT_REDIS_URL")
OUTPUT_REDIS_URL = os.getenv("OUTPUT_REDIS_URL", INPUT_REDIS_URL)
INPUT_QUEUE = os.getenv("INPUT_QUEUE", "square:input")
OUTPUT_QUEUE = os.getenv("OUTPUT_QUEUE", "square:output")
INSTANCE_ID = os.getenv("INSTANCE_ID", "0")
NODE_ID = os.getenv("NODE_ID", "unknown")[:8]

r_in = redis.from_url(INPUT_REDIS_URL)
r_out = redis.from_url(OUTPUT_REDIS_URL)

processed = 0

while True:
    result = r_in.brpop(INPUT_QUEUE, timeout=5)
    if result is None:
        if r_in.llen(INPUT_QUEUE) == 0:
            break
        continue
    
    _, task_data = result
    n = int(task_data.decode() if isinstance(task_data, bytes) else task_data)
    
    # 计算平方
    result = n * n
    
    # 写回结果: "n:result"
    r_out.lpush(OUTPUT_QUEUE, f"{n}:{result}")
    
    processed += 1
    if processed % 1000 == 0:
        print(f"[{NODE_ID}:{INSTANCE_ID}] Progress: {processed}")

print(f"[{NODE_ID}:{INSTANCE_ID}] Done. Total: {processed}")
'''
        
        with open(os.path.join(workdir, "consumer.py"), "w") as f:
            f.write(consumer_code)
        
        # 步骤 2：创建 Dockerfile
        print("3. 生成 Dockerfile...")
        dockerfile = '''FROM python:3.11-slim
RUN pip install redis
COPY consumer.py /app/consumer.py
CMD ["python", "/app/consumer.py"]
'''
        
        with open(os.path.join(workdir, "Dockerfile"), "w") as f:
            f.write(dockerfile)
        
        # 步骤 3：构建镜像
        print("4. 构建 Docker 镜像...")
        success, stdout, stderr = run_command("docker build -t idm-example:square .", cwd=workdir)
        if not success:
            print(f"构建失败: {stderr}")
            return
        print("   ✓ 镜像构建成功: idm-example:square")
        
        # 步骤 4：注册任务
        print("\n5. 注册任务到 ComputeHub...")
        task_config = {
            "name": "square-calc",
            "image": "idm-example:square",
            "input_redis": REDIS_URL,
            "output_redis": REDIS_URL,
            "input_queue": "square:input",
            "output_queue": "square:output"
        }
        
        import json
        cmd = f"""curl -s -X POST {COMPUTEHUB_URL}/api/tasks \\
  -H "Authorization: Bearer {TOKEN}" \\
  -H "Content-Type: application/json" \\
  -d '{json.dumps(task_config)}'"""
        
        success, stdout, stderr = run_command(cmd)
        if success:
            print("   ✓ 任务已注册: square-calc")
        else:
            print(f"   ✗ 注册失败: {stderr}")
            return
        
        # 步骤 5：推送数据
        print(f"\n6. 推送 {N} 个任务到队列...")
        push_script = f'''
import redis
r = redis.from_url("{REDIS_URL}")
r.delete("square:input", "square:output")

# 批量推送
batch = []
for i in range(1, {N+1}):
    batch.append(str(i))
    if len(batch) >= 1000:
        r.lpush("square:input", *batch)
        batch = []
if batch:
    r.lpush("square:input", *batch)

print(f"已推送 {{r.llen('square:input')}} 个任务")
'''
        
        with open(os.path.join(workdir, "push_data.py"), "w") as f:
            f.write(push_script)
        
        success, stdout, stderr = run_command(f"python3 {workdir}/push_data.py")
        if success:
            print(f"   ✓ {stdout.strip()}")
        else:
            print(f"   ✗ 推送失败: {stderr}")
            return
        
        # 步骤 6：监控进度
        print("\n7. 监控任务进度...")
        print("   提示: 在另一个终端运行以下命令查看实时进度:")
        print(f"   redis-cli -u {REDIS_URL} llen square:output")
        print("\n   等待 10 秒后检查结果...")
        
        import time
        time.sleep(10)
        
        # 步骤 7：检查结果
        print("\n8. 检查结果...")
        check_script = f'''
import redis
r = redis.from_url("{REDIS_URL}")
output_len = r.llen("square:output")
input_len = r.llen("square:input")
print(f"已完成: {{output_len}}")
print(f"待处理: {{input_len}}")

# 显示前 10 个结果
if output_len > 0:
    print("\\n前 10 个结果:")
    for item in r.lrange("square:output", 0, 9):
        print(f"  {{item.decode()}}")
'''
        
        with open(os.path.join(workdir, "check_result.py"), "w") as f:
            f.write(check_script)
        
        run_command(f"python3 {workdir}/check_result.py")
        
        print("\n" + "=" * 50)
        print("示例完成！")
        print("=" * 50)
        print(f"\n清理命令:")
        print(f"  redis-cli -u {REDIS_URL} del square:input square:output")
        print(f"  docker rmi idm-example:square")


if __name__ == "__main__":
    main()
