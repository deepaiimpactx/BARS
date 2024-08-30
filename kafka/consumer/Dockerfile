FROM python:3.12-slim

WORKDIR /app

COPY . /app

RUN pip install --no-cache-dir confluent_kafka psycopg2-binary

CMD ["python", "consumer.py"]
