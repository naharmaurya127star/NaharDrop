FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY run.py NaharDrop.md ./

VOLUME ["/data/received", "/app/data"]
EXPOSE 8000

ENTRYPOINT ["python", "run.py"]
CMD ["--host", "0.0.0.0", "--port", "8000", "--dest", "/data/received"]
