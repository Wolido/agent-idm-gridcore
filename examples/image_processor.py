#!/usr/bin/env python3
"""
IDM-GridCore 示例：批量图片处理
将目录中的所有图片生成缩略图
"""

import os
import subprocess
import tempfile


def create_image_consumer(width=300, height=300):
    """生成图片处理消费者代码"""
    return f'''
import redis
import os
from PIL import Image
import io

INPUT_REDIS_URL = os.getenv("INPUT_REDIS_URL")
OUTPUT_REDIS_URL = os.getenv("OUTPUT_REDIS_URL", INPUT_REDIS_URL)
INPUT_QUEUE = os.getenv("INPUT_QUEUE", "image:input")
OUTPUT_QUEUE = os.getenv("OUTPUT_QUEUE", "image:output")
INSTANCE_ID = os.getenv("INSTANCE_ID", "0")
NODE_ID = os.getenv("NODE_ID", "unknown")[:8]

# 缩略图尺寸
THUMB_WIDTH = {width}
THUMB_HEIGHT = {height}

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
    task = task_data.decode() if isinstance(task_data, bytes) else task_data
    
    try:
        # 任务格式: "input_path|output_path"
        input_path, output_path = task.split("|")
        
        # 打开并处理图片
        with Image.open(input_path) as img:
            # 转换为 RGB（处理 RGBA 等模式）
            if img.mode in ('RGBA', 'LA', 'P'):
                img = img.convert('RGB')
            
            # 生成缩略图
            img.thumbnail((THUMB_WIDTH, THUMB_HEIGHT))
            
            # 保存
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            img.save(output_path, "JPEG", quality=85)
        
        r_out.lpush(OUTPUT_QUEUE, f"OK:{{input_path}}")
        processed += 1
        
    except Exception as e:
        r_out.lpush(OUTPUT_QUEUE, f"ERROR:{{task}}:{{str(e)}}")
        errors += 1
    
    if (processed + errors) % 100 == 0:
        print(f"[{NODE_ID}:{{INSTANCE_ID}}] Processed: {{processed}}, Errors: {{errors}}")

print(f"[{NODE_ID}:{{INSTANCE_ID}}] Done. Processed: {{processed}}, Errors: {{errors}}")
'''


def main():
    # 配置
    INPUT_DIR = "~/images"  # 替换为实际的输入目录
    OUTPUT_DIR = "~/thumbnails"  # 替换为实际的输出目录
    COMPUTEHUB_URL = "http://localhost:8080"
    TOKEN = "your-token-here"
    REDIS_URL = "redis://:password@localhost:6379"
    
    print("图片批量处理示例")
    print("=" * 50)
    print(f"\n输入目录: {INPUT_DIR}")
    print(f"输出目录: {OUTPUT_DIR}")
    
    # 展开用户目录
    INPUT_DIR = os.path.expanduser(INPUT_DIR)
    OUTPUT_DIR = os.path.expanduser(OUTPUT_DIR)
    
    # 检查输入目录
    if not os.path.exists(INPUT_DIR):
        print(f"\n✗ 输入目录不存在: {INPUT_DIR}")
        print("请修改 INPUT_DIR 为实际的图片目录")
        return
    
    # 获取所有图片文件
    image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'}
    images = [f for f in os.listdir(INPUT_DIR) 
              if os.path.splitext(f.lower())[1] in image_extensions]
    
    if not images:
        print(f"\n✗ 输入目录中没有图片文件")
        return
    
    print(f"\n找到 {len(images)} 张图片")
    
    with tempfile.TemporaryDirectory() as workdir:
        print(f"\n1. 创建工作目录...")
        
        # 生成消费者代码
        print("2. 生成图片处理代码...")
        consumer_code = create_image_consumer(300, 300)
        
        with open(os.path.join(workdir, "consumer.py"), "w") as f:
            f.write(consumer_code)
        
        # 创建 Dockerfile
        print("3. 生成 Dockerfile...")
        dockerfile = '''FROM python:3.11-slim
RUN pip install redis pillow
COPY consumer.py /app/consumer.py
CMD ["python", "/app/consumer.py"]
'''
        
        with open(os.path.join(workdir, "Dockerfile"), "w") as f:
            f.write(dockerfile)
        
        # 构建镜像
        print("4. 构建镜像...")
        result = subprocess.run(
            ["docker", "build", "-t", "idm-example:image", "."],
            cwd=workdir, capture_output=True, text=True
        )
        
        if result.returncode != 0:
            print(f"✗ 构建失败: {result.stderr}")
            return
        print("   ✓ 镜像构建成功: idm-example:image")
        
        # 注册任务
        print("\n5. 注册任务...")
        import json
        task_config = json.dumps({
            "name": "image-thumbnails",
            "image": "idm-example:image",
            "input_redis": REDIS_URL,
            "output_redis": REDIS_URL,
            "input_queue": "image:input",
            "output_queue": "image:output"
        })
        
        result = subprocess.run([
            "curl", "-s", "-X", "POST", f"{COMPUTEHUB_URL}/api/tasks",
            "-H", f"Authorization: Bearer {TOKEN}",
            "-H", "Content-Type: application/json",
            "-d", task_config
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            print("   ✓ 任务已注册: image-thumbnails")
        else:
            print(f"   ✗ 注册失败")
            return
        
        # 推送任务
        print(f"\n6. 推送 {len(images)} 个图片处理任务...")
        
        import redis
        r = redis.from_url(REDIS_URL)
        r.delete("image:input", "image:output")
        
        for img in images:
            input_path = os.path.join(INPUT_DIR, img)
            output_path = os.path.join(OUTPUT_DIR, img)
            # 任务格式: input_path|output_path
            r.lpush("image:input", f"{input_path}|{output_path}")
        
        print(f"   ✓ 已推送 {r.llen('image:input')} 个任务")
        
        print("\n" + "=" * 50)
        print("任务已提交，正在并行处理...")
        print("=" * 50)
        print(f"\n监控命令:")
        print(f"  redis-cli -u {REDIS_URL} llen image:output")
        print(f"\n检查错误:")
        print(f"  redis-cli -u {REDIS_URL} lrange image:output 0 9")


if __name__ == "__main__":
    main()
