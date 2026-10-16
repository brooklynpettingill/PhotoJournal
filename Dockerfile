FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py apple_sync.py phone_import.py security.py wsgi.py ./
COPY static ./static
RUN useradd --uid 10001 --create-home journal && mkdir /data && chown journal:journal /data
USER journal
ENV PHOTOJOURNAL_DATA=/data PORT=3000
EXPOSE 3000
CMD ["sh", "-c", "exec gunicorn --bind 0.0.0.0:${PORT:-3000} --workers 1 --threads 4 --timeout 120 wsgi:app"]
