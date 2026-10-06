FROM python:3.12-slim

WORKDIR /app

# 先装依赖（利用 Docker 缓存，代码改不动依赖层）；--no-cache-dir 避免 pip 缓存进镜像
# 源用清华 PyPI：阿里云源这次实测既慢（百 kB/s 级）又出现过下载文件哈希对不上
COPY requirements.txt .
RUN pip install --no-cache-dir --timeout 60 --retries 5 -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 再复制代码
COPY . .

# 不缓冲 stdout：否则 print 会被攒在缓冲区里，Docker 日志中 print 与 uvicorn
# 日志的先后顺序会错乱（uvicorn 的启动日志走 stderr、即时输出，访问日志才走 stdout）
ENV PYTHONUNBUFFERED=1

# 关闭 reload（避免容器内文件变动触发重启死循环）
ENV DISABLE_RELOAD=true

# 暴露端口
EXPOSE 8001

# 启动
CMD ["python", "main.py"]
