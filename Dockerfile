# 使用官方轻量级 Python 镜像
FROM python:3.10-slim

# 设置工作目录
WORKDIR /app

# 设置环境变量，防止 Python 产生缓存文件并确保日志实时输出
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 安装运行所需的依赖库
RUN pip install --no-cache-dir python-telegram-bot python-dotenv

# 将当前目录的所有文件复制到容器的 /app 目录
COPY . .

# 启动机器人
CMD ["python", "bot.py"]