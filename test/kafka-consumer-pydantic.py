from kafka import KafkaConsumer
from models import OuterWrapper
import os
from dotenv import load_dotenv

load_dotenv()
KAFKA_BROKER=os.getenv("KAFKA_BROKER")
TOPIC_NAME=os.getenv("KAFKA_OUTPUT_TOPIC") # use this when wrapping the kafka-in-out.py
# OR
# TOPIC_NAME = "test_topic"  

# Create Kafka consumer
consumer = KafkaConsumer(
    TOPIC_NAME,
    bootstrap_servers=KAFKA_BROKER,
    auto_offset_reset="earliest",  # Start from the earliest message
    enable_auto_commit=True,  # Automatically commit offsets
    #group_id="simple_consumer_group"
)

print(f"Listening for messages on topic: {TOPIC_NAME}")

# Consume messages
for kafka_message in consumer:
    print(f"Received: {kafka_message.value.decode('utf-8')}")