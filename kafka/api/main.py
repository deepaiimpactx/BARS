import os
import json
import logging
from datetime import datetime
from flask import Flask, request, jsonify
from confluent_kafka import Producer

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load configuration from environment variables or default values
KAFKA_BROKER = os.getenv('KAFKA_BROKER', 'broker:29092')
KAFKA_TOPIC_TRAIN = os.getenv('KAFKA_TOPIC_TRAIN', 'sensor_train')
KAFKA_TOPIC_PRED = os.getenv('KAFKA_TOPIC_PRED', 'sensor_pred')

# Kafka configuration
kafka_config = {
    'bootstrap.servers': KAFKA_BROKER,
    'client.id': 'sensor_data_producer'
}

# Create Kafka producer
kafka_producer = Producer(kafka_config)

def delivery_report(err, msg):
    if err is not None:
        logger.error(f'Message delivery failed: {err}')
    else:
        logger.info(f"Message delivered to {msg.topic()} [{msg.partition()}]")

@app.route('/send_sensor_data/<data_type>/<client_id>', methods=['POST'])
def send_sensor_data(data_type, client_id):
    logger.info(f"Received POST request for client {client_id}, data type: {data_type}")
    try:
        data = request.json
        if not data:
            raise ValueError("No data received")

        # Log client-specific request
        logger.info(f"Client {client_id} data: {data}")

        # Prepare the sensor data payload dynamically from the received data
        sensor_data = {
            "clientId": client_id,
            "DATE_TIME": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        }

        # Add all key-value pairs from request data except clientId and DATE_TIME
        for key in data:
            if key not in ['clientId', 'DATE_TIME']:
                sensor_data[key] = data[key]

        # Determine the topic based on the data type
        if data_type == "train":
            topic = f"{KAFKA_TOPIC_TRAIN}_{client_id}"
        elif data_type == "pred":
            topic = f"{KAFKA_TOPIC_PRED}_{client_id}"
        else:
            raise ValueError("Invalid data type. Use 'train' or 'pred'.")

        send_to_kafka(sensor_data, topic)
        return jsonify({"success": True, "message": f"Data for client {client_id} (type: {data_type}) received successfully and sent to Kafka"}), 200

    except Exception as e:
        logger.error(f"Error processing request for client {client_id}, data type: {data_type}: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

def send_to_kafka(data, topic):
    try:
        kafka_producer.produce(
            topic,
            key=json.dumps({"sensorId": data.get('sensorId')}).encode('utf-8'),
            value=json.dumps(data).encode('utf-8'),
            on_delivery=delivery_report
        )
        # Poll for events to ensure the message is delivered
        kafka_producer.poll(0)
        # Flushing to ensure all messages are sent before exiting
        kafka_producer.flush()
    except Exception as e:
        logger.error(f"Error sending data to Kafka: {e}")
        raise

def start_server():
    logger.info("Starting production server")
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)))

if __name__ == "__main__":
    start_server()
