FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .
COPY evaluation_cases.json .
EXPOSE 8081
CMD ["python", "app.py"]
