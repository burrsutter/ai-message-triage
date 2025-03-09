from kafka import KafkaProducer
import sys
import os
# Add the parent directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models import OuterWrapper
import os
import uuid
import json
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
KAFKA_BROKER=os.getenv("KAFKA_BROKER")
TOPIC_NAME=os.getenv("KAFKA_INPUT_TOPIC") # use this when wrapping the kafka-in-out.py
# OR
# TOPIC_NAME = "test_topic"  

# Create a Kafka producer with a serializer
producer = KafkaProducer(
    bootstrap_servers=KAFKA_BROKER,
    value_serializer=lambda x: json.dumps(x, default=str).encode('utf-8')
)

kafka_message = OuterWrapper(
    id=str(uuid.uuid4()),
    filename="test-message.txt",
    timestamp=datetime.utcnow().isoformat(), 
    content="Hello, I purchased a TechGear Pro Laptop, but I can't find the invoice in my email. Sincerely, David Jones david@example.org"
)

# Send the message as a dictionary
producer.send(TOPIC_NAME, kafka_message.model_dump())

print(f"Sent: {kafka_message.model_dump()}")

# Ensure all messages are sent before exiting
producer.flush()
producer.close()
