# IDM-GridCore 计算容器模板
# 基于 Python 的轻量级消费者

FROM python:3.11-slim

# 安装依赖
RUN pip install --no-cache-dir redis

# 复制消费者代码
COPY consumer.py /app/consumer.py

# 设置工作目录
WORKDIR /app

# 运行消费者
CMD ["python", "/app/consumer.py"]
