import os
import joblib
import json
import time
import logging
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, ExtraTreesClassifier, GradientBoostingClassifier
from xgboost import XGBClassifier
from lightgbm import LGBMClassifier
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
from pyflink.common import WatermarkStrategy, Types
from pyflink.common.serialization import SimpleStringSchema
from pyflink.datastream import StreamExecutionEnvironment, MapFunction
from pyflink.datastream.connectors.kafka import KafkaSource, KafkaSink, KafkaRecordSerializationSchema, \
    DeliveryGuarantee, KafkaOffsetsInitializer
from general import *
from river.drift import ADWIN

data_points = {}
feature_configs = {}
logger = configure_logging()

class CollectAndProcessData(MapFunction):
    def __init__(self, topic):
        self.topic = topic
        self.model_trained = False
        self.adwin = ADWIN()

    def map(self, value):
        global feature_configs, data_points

        data = json.loads(value)
        if self.topic not in feature_configs:
            logger.warning(f"No feature configuration found for topic {self.topic}")
            return value

        feature_config = feature_configs[self.topic]
        features = [data.get(feature) for feature in feature_config["features"]]
        is_malicious = data.get("Is_Malicious")

        if self.adwin.update(features):
            logger.info(f"Drift detected in topic {self.topic}! Retraining models.")
            self.model_trained = False
            data_points[self.topic] = []

        if len(data_points.get(self.topic, [])) < 5000:
            data_points.setdefault(self.topic, []).append((features, is_malicious))
            if len(data_points[self.topic]) >= 5000 and not self.model_trained:
                self.train_and_save_models()
                self.model_trained = True
                env.stop()
        else:
            logger.debug(f"5000 data points collected for topic {self.topic}. No more data points are being processed for model training.")

        data["processed"] = True
        return json.dumps(data)

    def train_and_save_models(self):
        global data_points
        df = pd.DataFrame(data_points[self.topic], columns=['features', 'is_malicious'])
        X = pd.DataFrame(df['features'].tolist(), columns=feature_configs[self.topic]["features"])
        y = df['is_malicious']
        metrics_list = []

        models = {
            'RandomForest': RandomForestClassifier(n_estimators=100, random_state=42),
            'XGBoost': XGBClassifier(n_estimators=100, random_state=42),
            'LightGBM': LGBMClassifier(n_estimators=100, random_state=42),
            'ExtraTrees': ExtraTreesClassifier(n_estimators=100, random_state=42),
            'GradientBoosting': GradientBoostingClassifier(n_estimators=100, random_state=42)
        }

        for model_name, model in models.items():
            start_time = time.time()
            model.fit(X, y)
            y_pred = model.predict(X)
            accuracy = accuracy_score(y, y_pred)
            precision = precision_score(y, y_pred, average='weighted')
            recall = recall_score(y, y_pred, average='weighted')
            f1 = f1_score(y, y_pred, average='weighted')
            training_time = time.time() - start_time

            logger.info(f"{model_name} model trained for topic {self.topic}.")
            logger.info(f"{model_name} Model Accuracy: {accuracy:.4f}")
            logger.info(f"{model_name} Model Precision: {precision:.4f}")
            logger.info(f"{model_name} Model Recall: {recall:.4f}")
            logger.info(f"{model_name} Model F1 Score: {f1:.4f}")

            metrics_list.append({
                'Model': model_name,
                'Accuracy': accuracy,
                'Precision': precision,
                'Recall': recall,
                'F1': f1,
                'Training Time': training_time
            })

            model_path = f'/opt/flink/saved_models/{self.topic}_{model_name.lower()}_model.pkl'
            os.makedirs(os.path.dirname(model_path), exist_ok=True)
            joblib.dump(model, model_path)
            logger.info("%s model saved to disk at '%s'", model_name, model_path)

        metrics_df = pd.DataFrame(metrics_list)
        metrics_csv_path = f'/opt/flink/saved_models/{self.topic}_metrics.csv'
        metrics_df.to_csv(metrics_csv_path, index=False)
        logger.info(f"Metrics saved to CSV at '{metrics_csv_path}'")

        metrics_pkl_path = f'/opt/flink/saved_models/{self.topic}_metrics.pkl'
        metrics_df.to_pickle(metrics_pkl_path)
        logger.info(f"Metrics saved to pickle at '{metrics_pkl_path}'")


class ReadFeatureSelectionConfig(MapFunction):
    def __init__(self, result_type):
        self.result_type = result_type

    def map(self, value):
        global feature_configs
        config = json.loads(value)
        topic = self.result_type + "_sensor_data_topic"
        feature_configs[topic] = config
        logger.info(f"Feature selection configuration updated for {self.result_type}: {config}")
        return value


def create_kafka_source(topic_pattern):
    return KafkaSource.builder() \
        .set_bootstrap_servers("broker:29092") \
        .set_group_id("flink-group") \
        .set_topic_pattern(topic_pattern) \
        .set_value_only_deserializer(SimpleStringSchema()) \
        .build()


def create_kafka_sink(topic, schema):
    return KafkaSink.builder() \
        .set_bootstrap_servers("broker:29092") \
        .set_record_serializer(
            KafkaRecordSerializationSchema.builder() \
            .set_topic(topic) \
            .set_value_serialization_schema(schema) \
            .build()
        ) \
        .set_delivery_guarantee(DeliveryGuarantee.AT_LEAST_ONCE) \
        .build()



def execute_flink_job():
    logger.info("Starting the Kafka read and write job")
    env = StreamExecutionEnvironment.get_execution_environment()
    env.enable_checkpointing(5000)
    env.get_checkpoint_config().enable_unaligned_checkpoints()

    root_dir = get_root_dir()
    logger.debug(f"Root directory: {root_dir}")
    add_jars_to_env(env, root_dir)
    logger.debug("JAR files added successfully")

    # Create Kafka sources for feature selection results
    kafka_source_lst = create_kafka_source("lst_results")
    kafka_source_ga = create_kafka_source("ga_optimisation_results")
    kafka_source_pso = create_kafka_source("pso_optimization_results")
    kafka_source_dnn = create_kafka_source("dnn_result")

    # Create Kafka sources for sensor data topics
    kafka_source_sensor = create_kafka_source("sensor_data_topic_.*")

    # Create streams for feature selection results
    feature_selection_stream_lst = env.from_source(kafka_source_lst, WatermarkStrategy.no_watermarks(), "KafkaSourceLST")
    feature_selection_stream_ga = env.from_source(kafka_source_ga, WatermarkStrategy.no_watermarks(), "KafkaSourceGA")
    feature_selection_stream_pso = env.from_source(kafka_source_pso, WatermarkStrategy.no_watermarks(), "KafkaSourcePSO")
    feature_selection_stream_dnn = env.from_source(kafka_source_dnn, WatermarkStrategy.no_watermarks(), "KafkaSourceDNN")

    # Process feature selection configurations
    feature_selection_stream_lst.map(ReadFeatureSelectionConfig("lst"), output_type=Types.STRING())
    feature_selection_stream_ga.map(ReadFeatureSelectionConfig("ga"), output_type=Types.STRING())
    feature_selection_stream_pso.map(ReadFeatureSelectionConfig("pso"), output_type=Types.STRING())
    feature_selection_stream_dnn.map(ReadFeatureSelectionConfig("dnn"), output_type=Types.STRING())

    # Process sensor data and apply feature configurations
    sensor_data_stream = env.from_source(kafka_source_sensor, WatermarkStrategy.for_monotonous_timestamps(), "KafkaSourceSensor")

    topics = ["lst_sensor_data_topic", "ga_sensor_data_topic", "pso_sensor_data_topic", "dnn_sensor_data_topic"]
    for topic in topics:
        data_stream = env.from_source(create_kafka_source(topic), WatermarkStrategy.for_monotonous_timestamps(), f"KafkaSource_{topic}")
        processed_data_stream = data_stream.map(CollectAndProcessData(topic), output_type=Types.STRING())
        kafka_sink = create_kafka_sink("processed_data_topic", SimpleStringSchema())
        processed_data_stream.sink_to(kafka_sink)

    logger.info("Executing the Flink environment")
    env.execute('Kafka Read and Write with Data Collection, Feature Selection, and Model Training')
    logger.info("Flink environment executed successfully")


if __name__ == '__main__':
    execute_flink_job()
