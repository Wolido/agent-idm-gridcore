#!/usr/bin/env python3
"""
IDM-GridCore 示例：批量 HTTP 请求
并行抓取多个 URL
"""

import subprocess
import tempfile
import os
import json


def create_http_consumer(timeout=30):
    """生成 HTTP 请求消费者代码"""
    return f'''
import redis
import os
import requests
import time

INPUT_REDIS_URL = os.getenv("INPUT_REDIS_URL")
OUTPUT_REDIS_URL = os.getenv("OUTPUT_REDIS_URL", INPUT_REDIS_URL)
INPUT_QUEUE = os.getenv("INPUT_QUEUE", "http:input")
OUTPUT_QUEUE = os.getenv("OUTPUT_QUEUE", "http:output")
INSTANCE_ID = os.getenv("INSTANCE_ID", "0")
NODE_ID = os.getenv("NODE_ID", "unknown")[:8]

TIMEOUT = {timeout}

r_in = redis.from_url(INPUT_REDIS_URL)
r_out = redis.from_url(OUTPUT_REDIS_URL)

processed = 0
errors = 0

while True:
    result = r_in.brpop(INPUT_QUEUE, timeout=5)
    if result is None:
        if r_in.llen(INPUT_QUEUE) == 0:
            break
        continue
    
    _, task_data = result
    url = task_data.decode() if isinstance(task_data, bytes) else task_data
    
    try:
        start = time.time()
        resp = requests.get(url, timeout=TIMEOUT)
        elapsed = time.time() - start
        
        # 结果格式: "url|status_code|content_length|elapsed_time"
        result_str = f"{{url}}|{{resp.status_code}}|{{len(resp.text)}}|{{elapsed:.2f}}"
        r_out.lpush(OUTPUT_QUEUE, result_str)
        processed += 1
        
    except requests.exceptions.Timeout:
        r_out.lpush(OUTPUT_QUEUE, f"{{url}}|TIMEOUT|0|{{TIMEOUT}}")
        errors += 1
    except Exception as e:
        r_out.lpush(OUTPUT_QUEUE, f"{{url}}|ERROR|0|{{str(e)}}")
        errors += 1
    
    if (processed + errors) % 100 == 0:
        print(f"[{NODE_ID}:{{INSTANCE_ID}}] Processed: {{processed}}, Errors: {{errors}}")

print(f"[{NODE_ID}:{{INSTANCE_ID}}] Done. Processed: {{processed}}, Errors: {{errors}}")
'''


def main():
    # 配置
    URLS_FILE = "urls.txt"  # 每行一个 URL
    COMPUTEHUB_URL = "http://localhost:8080"
    TOKEN = "your-token-here"
    REDIS_URL = "redis://:password@localhost:6379"
    
    print("批量 HTTP 请求示例")
    print("=" * 50)
    
    # 检查 URL 文件或使用示例 URL
    urls = []
    if os.path.exists(URLS_FILE):
        with open(URLS_FILE) as f:
            urls = [line.strip() for line in f if line.strip()]
        print(f"\n从 {URLS_FILE} 读取了 {len(urls)} 个 URL")
    else:
        # 使用示例 URL
        urls = [
            "https://httpbin.org/get",
            "https://httpbin.org/ip",
            "https://httpbin.org/user-agent",
            "https://httpbin.org/headers",
        ] * 100  # 重复 100 次，共 400 个请求
        print(f"\n使用示例 URL（httpbin.org），共 {len(urls)} 个请求")
        print(f"提示: 创建 {URLS_FILE} 文件可以自定义 URL 列表")
    
    with tempfile.TemporaryDirectory() as workdir:
        print(f"\n1. 创建工作目录...")
        
        # 生成消费者代码
        print("2. 生成 HTTP 请求代码...")
        consumer_code = create_http_consumer(timeout=30)
        
        with open(os.path.join(workdir, "consumer.py"), "w") as f:
            f.write(consumer_code)
        
        # 创建 Dockerfile
        print("3. 生成 Dockerfile...")
        dockerfile = '''FROM python:3.11-slim
RUN pip install redis requests
COPY consumer.py /app/consumer.py
CMD ["python", "/app/consumer.py"]
'''
        
        with open(os.path.join(workdir, "Dockerfile"), "w") as f:
            f.write(dockerfile)
        
        # 构建镜像
        print("4. 构建镜像...")
        result = subprocess.run(
            ["docker", "build", "-t", "idm-example:http", "."],
            cwd=workdir, capture_output=True, text=True
        )
        
        if result.returncode != 0:
            print(f"✗ 构建失败: {result.stderr}")
            return
        print("   ✓ 镜像构建成功: idm-example:http")
        
        # 注册任务
        print("\n5. 注册任务...")
        task_config = json.dumps({
            "name": "batch-http",
            "image": "idm-example:http",
            "input_redis": REDIS_URL,
            "output_redis": REDIS_URL,
            "input_queue": "http:input",
            "output_queue": "http:output"
        })
        
        result = subprocess.run([
            "curl", "-s", "-X", "POST", f"{COMPUTEHUB_URL}/api/tasks",
            "-H", f"Authorization: Bearer {TOKEN}",
            "-H", "Content-Type: application/json",
            "-d", task_config
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            print("   ✓ 任务已注册: batch-http")
        else:
            print(f"   ✗ 注册失败")
            return
        
        # 推送 URL
        print(f"\n6. 推送 {len(urls)} 个 URL...")
        
        import redis
        r = redis.from_url(REDIS_URL)
        r.delete("http:input", "http:output")
        
        # 批量推送
        batch = []
        for url in urls:
            batch.append(url)
            if len(batch) >= 1000:
                r.lpush("http:input", *batch)
                batch = []
        if batch:
            r.lpush("http:input", *batch)
        
        print(f"   ✓ 已推送 {r.llen('http:input')} 个 URL")
        
        print("\n" + "=" * 50)
        print("任务已提交，正在并行请求...")
        print("=" * 50)
        print(f"\n监控进度:")
        print(f"  redis-cli -u {REDIS_URL} llen http:output")
        print(f"\n查看结果:")
        print(f"  redis-cli -u {REDIS_URL} lrange http:output 0 9")
        print(f"\n统计状态码分布:")
        print(f"  redis-cli -u {REDIS_URL} lrange http:output 0 -1 | cut -d'|' -f2 | sort | uniq -c")


if __name__ == "__main__":
    main()
