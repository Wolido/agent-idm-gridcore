#!/usr/bin/env python3
"""
IDM-GridCore 消费者模板
从 Redis 队列取任务，处理后写回结果队列
"""

import redis
import os
import sys
import json
import time

# Redis 连接配置（GridNode 自动注入的环境变量）
INPUT_REDIS_URL = os.getenv("INPUT_REDIS_URL", "redis://localhost:6379")
OUTPUT_REDIS_URL = os.getenv("OUTPUT_REDIS_URL", INPUT_REDIS_URL)
INPUT_QUEUE = os.getenv("INPUT_QUEUE", "task:input")
OUTPUT_QUEUE = os.getenv("OUTPUT_QUEUE", "task:output")

# 实例标识（用于日志）
INSTANCE_ID = os.getenv("INSTANCE_ID", "0")
NODE_ID = os.getenv("NODE_ID", "unknown")[:8]
TASK_NAME = os.getenv("TASK_NAME", "unknown")


def process_task(task_data: str) -> str:
    """
    处理单个任务
    
    Args:
        task_data: 从队列取出的任务数据（字符串或 JSON）
    
    Returns:
        处理结果（字符串）
    """
    # TODO: 在这里实现具体的计算逻辑
    # 示例：计算平方
    try:
        n = float(task_data)
        result = n * n
        return f"{n}:{result}"
    except ValueError:
        return f"ERROR:Invalid input: {task_data}"


def main():
    print(f"[{NODE_ID}:{INSTANCE_ID}] Task '{TASK_NAME}' consumer starting...")
    print(f"  Input:  {INPUT_QUEUE}")
    print(f"  Output: {OUTPUT_QUEUE}")
    
    # 连接 Redis
    try:
        r_in = redis.from_url(INPUT_REDIS_URL)
        r_out = redis.from_url(OUTPUT_REDIS_URL)
        r_in.ping()
        print(f"[{NODE_ID}:{INSTANCE_ID}] ✓ Redis connected")
    except Exception as e:
        print(f"[{NODE_ID}:{INSTANCE_ID}] ✗ Redis connection failed: {e}")
        sys.exit(1)
    
    processed = 0
    errors = 0
    start_time = time.time()
    
    try:
        while True:
            try:
                # 阻塞等待任务（超时5秒，便于优雅退出）
                result = r_in.brpop(INPUT_QUEUE, timeout=5)
                
                if result is None:
                    # 超时，检查队列是否为空
                    if r_in.llen(INPUT_QUEUE) == 0:
                        elapsed = time.time() - start_time
                        print(f"[{NODE_ID}:{INSTANCE_ID}] Queue empty, exiting. "
                              f"Processed: {processed} (errors: {errors}) in {elapsed:.1f}s")
                        break
                    continue
                
                # 解析任务
                _, task_data = result
                task_str = task_data.decode() if isinstance(task_data, bytes) else task_data
                
                # 处理任务
                try:
                    output = process_task(task_str)
                    r_out.lpush(OUTPUT_QUEUE, output)
                    processed += 1
                except Exception as e:
                    # 处理失败，记录错误但不中断
                    error_msg = f"ERROR:{task_str}:{str(e)}"
                    r_out.lpush(OUTPUT_QUEUE, error_msg)
                    errors += 1
                
                # 每处理 1000 条打印一次进度
                if processed % 1000 == 0:
                    elapsed = time.time() - start_time
                    speed = processed / elapsed
                    print(f"[{NODE_ID}:{INSTANCE_ID}] Progress: {processed:,} tasks "
                          f"@ {speed:.0f}/s (errors: {errors})")
                    
            except Exception as e:
                print(f"[{NODE_ID}:{INSTANCE_ID}] Error: {e}")
                time.sleep(1)
    
    except KeyboardInterrupt:
        elapsed = time.time() - start_time
        print(f"\n[{NODE_ID}:{INSTANCE_ID}] Interrupted. "
              f"Processed: {processed} (errors: {errors}) in {elapsed:.1f}s")
    
    print(f"[{NODE_ID}:{INSTANCE_ID}] Done. Total processed: {processed}, errors: {errors}")


if __name__ == "__main__":
    main()
