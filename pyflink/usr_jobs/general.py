# general.py
import logging
from pyflink.datastream.connectors.kafka import KafkaSource, KafkaSink, KafkaRecordSerializationSchema, DeliveryGuarantee, KafkaOffsetsInitializer
from pyflink.common.serialization import SimpleStringSchema



def configure_logging():

    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(levelname)s %(message)s')
    logger = logging.getLogger(__name__)
    return logger


def get_root_dir():
    root_dir_list = __file__.split("/")[:-2]
    root_dir = "/".join(root_dir_list)
    return root_dir

def add_jars_to_env(env, root_dir):
    env.add_jars(
        f"file://{root_dir}/lib/flink-connector-jdbc-3.1.2-1.18.jar",
        f"file://{root_dir}/lib/postgresql-42.7.3.jar",
        f"file://{root_dir}/lib/flink-sql-connector-kafka-3.1.0-1.18.jar",
    )


def create_kafka_source(topic, group_id):
    return KafkaSource.builder() \
        .set_bootstrap_servers('broker:29092') \
        .set_group_id(group_id) \
        .set_starting_offsets(KafkaOffsetsInitializer.earliest()) \
        .set_topic_pattern(topic) \
        .set_value_only_deserializer(SimpleStringSchema()) \
        .build()

def create_kafka_sink(topic, value_serializer):
    return KafkaSink.builder() \
        .set_bootstrap_servers('broker:29092') \
        .set_record_serializer(KafkaRecordSerializationSchema.builder()
                               .set_topic(topic)
                               .set_value_serialization_schema(value_serializer)
                               .build()) \
        .set_delivery_guarantee(DeliveryGuarantee.AT_LEAST_ONCE) \
        .build()

