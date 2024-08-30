import os
import joblib
import json
import time
import logging
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, ExtraTreesClassifier, GradientBoostingClassifier
from xgboost import XGBClassifier
from lightgbm import LGBMClassifier
from sklearn.model_selection import KFold
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
from pyflink.common import WatermarkStrategy, Types
from pyflink.common.serialization import SimpleStringSchema
from pyflink.datastream import StreamExecutionEnvironment, MapFunction
from pyflink.datastream.connectors.kafka import KafkaSource, KafkaSink
from confluent_kafka import Consumer
from sklearn.utils import resample
from general import *

data_points = []

# Kafka consumer configuration
config = {
    'bootstrap.servers': 'broker:29092',
    'group.id': 'features_for_model_training',
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

# Set default feature_config if no message was received
# if 'feature_config' not in globals():
#     feature_config = {"features": ["Packet_Drop_Rate", "Energy_Consumption_Rate", "Error_Rate"]}

logger = configure_logging()

class CollectAndProcessData(MapFunction):
    def __init__(self):
        self.model_trained = False

    def map(self, value):
        global feature_config

        data = json.loads(value)
        features = [data.get(feature) for feature in feature_config["features"]]
        is_malicious = data.get("Is_Malicious")

        if len(data_points) < 5000:
            data_points.append((features, is_malicious))
            if len(data_points) >= 5000 and not self.model_trained:
                self.train_and_save_models()
                self.model_trained = True
        else:
            logger.debug("5000 data points collected. No more data points are being processed for model training.")

        data["processed"] = True
        return json.dumps(data)

    def resample_data(self, df, class_column):
        # Determine the target count based on the chosen strategy
        class_counts = df[class_column].value_counts()
        majority_class = class_counts.max()
        minority_class = class_counts.min()

        target_count = (majority_class + minority_class) // 2  # Target count for balancing

        # List to store the resampled data
        resampled_dfs = []

        for class_value, count in class_counts.items():
            class_df = df[df[class_column] == class_value]

            if count < target_count:
                # Oversample minority classes
                resampled_df = resample(class_df,
                                        replace=True,  # Sample with replacement
                                        n_samples=target_count,  # Match target count
                                        random_state=42)
            elif count > target_count:
                # Undersample majority classes
                resampled_df = resample(class_df,
                                        replace=False,  # Sample without replacement
                                        n_samples=target_count,  # Match target count
                                        random_state=42)
            else:
                # No resampling needed
                resampled_df = class_df

            resampled_dfs.append(resampled_df)

        # Combine all resampled dataframes into a single dataframe
        resampled_df = pd.concat(resampled_dfs)

        return resampled_df

    def train_and_save_models(self):
        global data_points

        df = pd.DataFrame(data_points, columns=['features', 'is_malicious'])

        # Resample the dataset to balance classes
        resampled_df = self.resample_data(df, 'is_malicious')

        X = pd.DataFrame(resampled_df['features'].tolist(), columns=feature_config["features"])
        y = resampled_df['is_malicious']

        metrics_list = []
        models = {
            'RandomForest': RandomForestClassifier(n_estimators=100, random_state=42),
            'XGBoost': XGBClassifier(n_estimators=100, random_state=42),
            'LightGBM': LGBMClassifier(n_estimators=100, random_state=42),
            'ExtraTrees': ExtraTreesClassifier(n_estimators=100, random_state=42),
            'GradientBoosting': GradientBoostingClassifier(n_estimators=100, random_state=42)
        }

        kf = KFold(n_splits=5, shuffle=True, random_state=42)

        for model_name, model in models.items():
            start_time = time.time()

            fold_metrics = []

            for fold_number, (train_index, test_index) in enumerate(kf.split(X), start=1):
                X_train, X_test = X.iloc[train_index], X.iloc[test_index]
                y_train, y_test = y.iloc[train_index], y.iloc[test_index]

                model.fit(X_train, y_train)
                y_pred = model.predict(X_test)

                accuracy = accuracy_score(y_test, y_pred)
                precision = precision_score(y_test, y_pred, average='weighted')
                recall = recall_score(y_test, y_pred, average='weighted')
                f1 = f1_score(y_test, y_pred, average='weighted')

                fold_metrics.append({
                    'Fold': fold_number,
                    'Accuracy': accuracy,
                    'Precision': precision,
                    'Recall': recall,
                    'F1': f1
                })

                # Save metrics for each fold to a separate CSV file
                fold_metrics_df = pd.DataFrame(fold_metrics)
                fold_metrics_csv_path = f'/opt/flink/saved_models/{model_name.lower()}_fold_metrics_fold_{fold_number}.csv'
                fold_metrics_df.to_csv(fold_metrics_csv_path, index=False)
                logger.info(f"Metrics for {model_name} model, fold {fold_number}, saved to '{fold_metrics_csv_path}'")

            # Compute average metrics across all folds
            avg_metrics = pd.DataFrame(fold_metrics).mean().to_dict()
            avg_accuracy = avg_metrics['Accuracy']
            avg_precision = avg_metrics['Precision']
            avg_recall = avg_metrics['Recall']
            avg_f1 = avg_metrics['F1']
            training_time = time.time() - start_time

            logger.info(f"{model_name} model trained with 5-fold cross-validation.")
            logger.info(f"{model_name} Model Accuracy (Average): {avg_accuracy:.4f}")
            logger.info(f"{model_name} Model Precision (Average): {avg_precision:.4f}")
            logger.info(f"{model_name} Model Recall (Average): {avg_recall:.4f}")
            logger.info(f"{model_name} Model F1 Score (Average): {avg_f1:.4f}")

            metrics_list.append({
                'Model': model_name,
                'Average Accuracy': avg_accuracy,
                'Average Precision': avg_precision,
                'Average Recall': avg_recall,
                'Average F1': avg_f1,
                'Training Time': training_time
            })

            model_path = f'/opt/flink/saved_models/{model_name.lower()}_model.pkl'
            os.makedirs(os.path.dirname(model_path), exist_ok=True)
            joblib.dump(model, model_path)
            logger.info("%s model saved to disk at '%s'", model_name, model_path)

        metrics_df = pd.DataFrame(metrics_list)
        metrics_csv_path = '/opt/flink/saved_models/metrics.csv'
        metrics_df.to_csv(metrics_csv_path, index=False)
        logger.info(f"Metrics saved to CSV at '{metrics_csv_path}'")
        metrics_pkl_path = '/opt/flink/saved_models/metrics.pkl'
        metrics_df.to_pickle(metrics_pkl_path)
        logger.info(f"Metrics saved to pickle at '{metrics_pkl_path}'")


def execute_flink_job():
    logger.info("Starting the Kafka read and write job")

    env = StreamExecutionEnvironment.get_execution_environment()
    env.enable_checkpointing(5000)
    env.get_checkpoint_config().enable_unaligned_checkpoints()

    root_dir = get_root_dir()
    logger.debug(f"Root directory: {root_dir}")
    add_jars_to_env(env, root_dir)
    logger.debug("JAR files added successfully")

    kafka_source = create_kafka_source("sensor_train_.*", "model_trainer")
    logger.debug("Kafka source set up successfully")

    data_stream = env.from_source(kafka_source, WatermarkStrategy.for_monotonous_timestamps(), "KafkaSource")
    logger.debug("Data stream created successfully")

    processed_data_stream = data_stream.map(CollectAndProcessData(), output_type=Types.STRING())
    logger.debug("Data transformation applied successfully")

    kafka_sink = create_kafka_sink("processed_data_topic", SimpleStringSchema())
    logger.debug("Kafka sink set up successfully")

    processed_data_stream.sink_to(kafka_sink)
    logger.debug("Transformed stream written to Kafka sink successfully")

    logger.info("Executing the Flink environment")
    env.execute('Kafka Read and Write with Data Collection and Model Training')
    logger.info("Flink environment executed successfully")


if __name__ == '__main__':
    execute_flink_job()
