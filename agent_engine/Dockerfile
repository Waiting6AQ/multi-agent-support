FROM python:3.12-slim

WORKDIR /app

# 先装依赖（利用 Docker 缓存，代码改不动依赖层）；--no-cache-dir 避免 pip 缓存进镜像
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/

# 再复制代码
COPY . .

# 关闭 reload（避免容器内文件变动触发重启死循环）
ENV DISABLE_RELOAD=true

# 暴露端口
EXPOSE 8001

# 启动
CMD ["python", "main.py"]
