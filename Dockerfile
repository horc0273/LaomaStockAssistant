FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

COPY requirements.txt .
RUN pip config set global.index-url https://mirrors.aliyun.com/pypi/simple/ \
 && pip config set global.trusted-host mirrors.aliyun.com \
 && pip install --no-cache-dir --timeout 60 --retries 5 -r requirements.txt

COPY app ./app
COPY static ./static

RUN useradd --create-home --uid 10001 laoma && mkdir -p /data && chown -R laoma:laoma /app /data
USER laoma

ENV LAOMA_STOCK_DATA_DIR=/data
EXPOSE 8787
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8787", "--workers", "2", "--proxy-headers"]
