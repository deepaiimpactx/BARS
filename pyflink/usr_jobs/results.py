import json
from pyflink.common import Types, WatermarkStrategy
from pyflink.common.serialization import SimpleStringSchema
from pyflink.datastream import StreamExecutionEnvironment, MapFunction
from pyflink.datastream.connectors.kafka import KafkaSink, KafkaSource
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
from general import *

# Initialize logger
logger = configure_logging()


class CalculateMetrics(MapFunction):
    def __init__(self):
        self.true_labels = []
        self.predicted_labels = []

    def map(self, value):
        data = json.loads(value)
        true_label = data.get('Is_Malicious')  # Assuming the prediction job added this field
        predicted_label = data.get('prediction')

        self.true_labels.append(true_label)
        self.predicted_labels.append(predicted_label)

        # For demonstration, let's say we calculate metrics every 1000 predictions
        if len(self.true_labels) >= 1000:
            accuracy = accuracy_score(self.true_labels, self.predicted_labels)
            precision = precision_score(self.true_labels, self.predicted_labels, average='weighted')
            recall = recall_score(self.true_labels, self.predicted_labels, average='weighted')
            f1 = f1_score(self.true_labels, self.predicted_labels, average='weighted')

            metrics = {
                'accuracy': accuracy,
                'precision': precision,
                'recall': recall,
                'f1_score': f1
            }
            logger.info(f"Calculated Metrics: {metrics}")

            # Clear the lists to start accumulating for the next batch
            self.true_labels.clear()
            self.predicted_labels.clear()

            # Return the metrics as a JSON string
            return json.dumps(metrics)

        # Return None if the metrics are not yet ready to be calculated
        return None


def execute_metrics_job():
    # Set up the execution environment
    env = StreamExecutionEnvironment.get_execution_environment()
    env.enable_checkpointing(5000)

    # Kafka source to read predictions
    kafka_source = create_kafka_source('predicted_data_topic', 'metrics_calculation_group')

    # Kafka sink to write metrics
    kafka_sink = create_kafka_sink('metrics_data_topic', SimpleStringSchema())

    # Create a data stream from Kafka source
    data_stream = env.from_source(kafka_source, WatermarkStrategy.for_monotonous_timestamps(), 'KafkaSource')

    # Calculate metrics and output as a JSON string, filtering out None values
    metrics_stream = data_stream.map(CalculateMetrics(), output_type=Types.STRING()).filter(lambda x: x is not None)

    # Sink metrics to Kafka
    metrics_stream.sink_to(kafka_sink)

    # Execute the Flink environment
    env.execute('Metrics Calculation Job')


if __name__ == '__main__':
    execute_metrics_job()
