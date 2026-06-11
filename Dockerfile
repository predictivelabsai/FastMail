FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV FASTMAIL_DB=/data/fastmail.sqlite
ENV FASTMAIL_PORT=5009
EXPOSE 5009
CMD ["sh", "-c", "python -c 'import db,seed; seed.build() if not db.db_exists() else None' && python web_app.py"]
