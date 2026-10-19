FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir "mcp==1.12.4" "httpx==0.28.1"
COPY server.py .
EXPOSE 8000
CMD ["python", "server.py"]
