import os
import json
import logging
import psycopg2
import re
import sys
from confluent_kafka import Consumer, KafkaException, KafkaError
from psycopg2 import pool

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load configuration from environment variables
KAFKA_BROKER = os.getenv('KAFKA_BROKER', 'broker:29092')
KAFKA_GROUP_ID = os.getenv('KAFKA_GROUP_ID', 'postgres_consumer')
KAFKA_TOPIC_PATTERN = os.getenv('KAFKA_TOPIC_PATTERN', '^sensor_data_topic_.*')

# Kafka consumer configuration
kafka_config = {
    'bootstrap.servers': KAFKA_BROKER,
    'group.id': KAFKA_GROUP_ID,
    'auto.offset.reset': 'earliest'
}

# Create Kafka consumer
consumer = Consumer(kafka_config)

# Retrieve all available topics
metadata = consumer.list_topics(timeout=10)

# Filter topics that match the pattern
topic_pattern = re.compile(KAFKA_TOPIC_PATTERN)
matching_topics = [topic for topic in metadata.topics.keys() if topic_pattern.match(topic)]

if not matching_topics:
    logger.error("No matching topics found.")
    sys.exit(1)

# Subscribe to the filtered list of topics
consumer.subscribe(matching_topics)

# PostgreSQL connection configuration
DB_NAME = os.getenv('DB_NAME', 'postgres')
DB_USER = os.getenv('DB_USER', 'postgres')
DB_PASSWORD = os.getenv('DB_PASSWORD', 'postgres')
DB_HOST = os.getenv('DB_HOST', 'postgres')
DB_PORT = os.getenv('DB_PORT', '5432')

# Use a connection pool for PostgreSQL
try:
    postgres_pool = psycopg2.pool.SimpleConnectionPool(
        1, 20,  # Min and max number of connections in the pool
        user=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME
    )
    if postgres_pool:
        logger.info("Connection pool created successfully")
except Exception as e:
    logger.error(f"Error creating PostgreSQL connection pool: {e}")
    sys.exit(1)

def create_table_if_not_exists():
    try:
        conn = postgres_pool.getconn()
        if conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sensor_data (
                    id SERIAL PRIMARY KEY,
                    client_id TEXT NOT NULL,
                    data JSONB NOT NULL,
                    received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
            cursor.close()
            postgres_pool.putconn(conn)
    except Exception as e:
        logger.error(f"Error creating table in PostgreSQL: {e}")
        if conn:
            postgres_pool.putconn(conn, close=True)
        sys.exit(1)

def get_existing_columns():
    try:
        conn = postgres_pool.getconn()
        if conn:
            cursor = conn.cursor()
            cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'sensor_data'")
            existing_columns = {row[0].lower() for row in cursor.fetchall()}  # Normalize to lowercase
            cursor.close()
            postgres_pool.putconn(conn)
            return existing_columns
    except Exception as e:
        logger.error(f"Error fetching existing columns from PostgreSQL: {e}")
        if conn:
            postgres_pool.putconn(conn, close=True)
        return set()

def alter_table_add_columns(new_columns, existing_columns):
    try:
        conn = postgres_pool.getconn()
        if conn:
            cursor = conn.cursor()
            for column in new_columns:
                column_name = column.lower()  # Normalize to lowercase
                if column_name not in existing_columns:
                    cursor.execute(f"ALTER TABLE sensor_data ADD COLUMN {column} JSONB")
            conn.commit()
            cursor.close()
            postgres_pool.putconn(conn)
    except Exception as e:
        logger.error(f"Error altering table in PostgreSQL: {e}")
        if conn:
            postgres_pool.putconn(conn, close=True)
        sys.exit(1)

def insert_sensor_data(data, existing_columns):
    try:
        conn = postgres_pool.getconn()
        if conn:
            cursor = conn.cursor()

            # Ensure all keys are columns in the table
            json_keys = set(data.keys())
            new_columns = json_keys - existing_columns
            if new_columns:
                logger.info(f"Adding new columns to PostgreSQL table: {new_columns}")
                alter_table_add_columns(new_columns, existing_columns)

            # Insert data into PostgreSQL
            query = """
            INSERT INTO sensor_data (client_id, data)
            VALUES (%s, %s)
            """
            cursor.execute(query, (
                data.get('clientId'),  # Assuming clientId is present in every data object
                json.dumps(data)
            ))
            conn.commit()
            cursor.close()
            postgres_pool.putconn(conn)
    except Exception as e:
        logger.error(f"Error inserting data into PostgreSQL: {e}")
        if conn:
            postgres_pool.putconn(conn, close=True)

try:
    # Ensure table exists
    create_table_if_not_exists()

    logger.info("Starting Kafka consumer")
    while True:
        msg = consumer.poll(timeout=1.0)
        if msg is None:
            continue
        if msg.error():
            if msg.error().code() == KafkaError._PARTITION_EOF:
                logger.info('End of partition reached')
                continue
            else:
                raise KafkaException(msg.error())

        # Process the message
        key = json.loads(msg.key().decode('utf-8')) if msg.key() else None
        value = json.loads(msg.value().decode('utf-8'))
        logger.info(f"Consumed message with key: {key} and value: {value}")

        # Get existing columns
        existing_columns = get_existing_columns()

        # Insert sensor data into PostgreSQL
        insert_sensor_data(value, existing_columns)

except Exception as e:
    logger.error(f"An error occurred: {e}")
finally:
    logger.info("Closing Kafka consumer and database connection pool")
    consumer.close()
    if postgres_pool:
        postgres_pool.closeall()
