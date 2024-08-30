import os
import joblib
import json
import pandas as pd
import shutil
import logging
from pyflink.common import WatermarkStrategy, Types
from pyflink.common.serialization import SimpleStringSchema
from pyflink.datastream import StreamExecutionEnvironment, MapFunction, RuntimeContext
from pyflink.datastream.connectors.kafka import KafkaSource, KafkaSink
from general import *
from confluent_kafka import Consumer
# Setup logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(handler)

# Kafka consumer configuration
config = {
        'bootstrap.servers': 'broker:29092',
        'group.id': 'features_for_data_prediction',
        'auto.offset.reset': 'earliest'
    }    
consumer = Consumer(config)
topic = "race"
consumer.subscribe([topic])    

# Poll for new messages from Kafka and print them.
try:
    while True:
        msg = consumer.poll(1.0)
        if msg is None:
            print("Waiting...")
        elif msg.error():
            print(f"ERROR: {msg.error()}")
        else:
            key = msg.key().decode('utf-8') if msg.key() is not None else None
            value = msg.value().decode('utf-8')
            print(f"Consumed event from topic {msg.topic()}: key = {key} value = {value}")
            feature_config = json.loads(value)
            break
except KeyboardInterrupt:
    pass
finally:
    consumer.close()
    

def select_best_model(metrics_csv_path, models_dir):
    """Select the best model based on metrics from the CSV file and copy it to the target path."""
    # Read metrics CSV
    metrics_df = pd.read_csv(metrics_csv_path)

    # Determine the best model based on metrics
    best_row = metrics_df.sort_values(by=['Average Accuracy', 'Average Precision', 'Average Recall', 'Average F1', 'Training Time'],
                                      ascending=[False, False, False, False, True]).iloc[0]
    best_model_name = best_row['Model'].lower()
    best_model_path = os.path.join(models_dir, f'{best_model_name}_model.pkl')

    # Define the source and destination paths
    best_model_temp_path = '/opt/flink/saved_models/best_model.pkl'

    # Copy the best model to the temporary path
    shutil.copy(best_model_path, best_model_temp_path)
    logger.info("Best model '%s' copied to '%s'", best_model_name, best_model_temp_path)
    return best_model_temp_path


class PredictData(MapFunction):
    def __init__(self, model_path):
        self.model_path = model_path
        self.model = None

    def open(self, runtime_context: RuntimeContext):
        logger.info("Loading model from %s", self.model_path)
        with open(self.model_path, 'rb') as model_file:
            self.model = joblib.load(model_file)
        logger.info("Model loaded successfully")

    def map(self, value):
        global feature_config

        data = json.loads(value)
        features = [data.get(feature) for feature in feature_config["features"]]
    
        prediction = int(self.model.predict([features])[0])  # Convert to Python int
        data["prediction"] = prediction
        logger.debug("Predicted data: %s", data)
        return json.dumps(data)


def execute_flink_job():
    """Set up and execute the Flink job with Kafka source and sink."""
    logger.info("Starting the Kafka read and write job")

    # Set up the execution environment with checkpointing enabled
    env = StreamExecutionEnvironment.get_execution_environment()
    env.enable_checkpointing(5000)  # Checkpoint every 5000 milliseconds (5 seconds)
    env.get_checkpoint_config().enable_unaligned_checkpoints()  # Enable unaligned checkpoints for better performance

    # Get the root directory
    root_dir = get_root_dir()
    logger.debug(f"Root directory: {root_dir}")

    # Add necessary JAR files to the Flink environment
    add_jars_to_env(env, root_dir)
    logger.debug("JAR files added successfully")

    # Path to the metrics CSV file and models directory
    metrics_csv_path = '/opt/flink/saved_models/metrics.csv'
    models_dir = '/opt/flink/saved_models'

    # Select and copy the best model
    model_path = select_best_model(metrics_csv_path, models_dir)

    # Create the Kafka source
    kafka_source = create_kafka_source("sensor_pred_.*", "prediction_job")
    logger.debug("Kafka source set up successfully")

    # Create the data stream from the Kafka source
    data_stream = env.from_source(kafka_source, WatermarkStrategy.for_monotonous_timestamps(), "KafkaSource")
    logger.debug("Data stream created successfully")

    # Load and apply the model for prediction
    prediction_data_stream = data_stream.map(PredictData(model_path), output_type=Types.STRING())
    logger.debug("Prediction transformation applied successfully")

    # Create the Kafka sink for processed data
    kafka_sink = create_kafka_sink("predicted_data_topic", SimpleStringSchema())
    logger.debug("Kafka sink set up successfully")

    # Write the transformed stream to the Kafka sink
    prediction_data_stream.sink_to(kafka_sink)
    logger.debug("Transformed stream written to Kafka sink successfully")

    # Execute the environment
    logger.info("Executing the Flink environment")
    env.execute('Kafka Read and Write with Predictions')
    logger.info("Flink environment executed successfully")


if __name__ == '__main__':
    execute_flink_job()