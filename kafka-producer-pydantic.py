from kafka import KafkaProducer
from models import Message # Pydantic class defined in message.py
import os
import uuid
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
KAFKA_BROKER=os.getenv("KAFKA_BROKER")
TOPIC_NAME=os.getenv("KAFKA_INPUT_TOPIC") # use this when wrapping the kafka-in-out.py
# OR
# TOPIC_NAME = "test_topic"  

# Create a Kafka producer
producer = KafkaProducer(bootstrap_servers=KAFKA_BROKER)

kafka_message = Message(
    id=str(uuid.uuid4()),
    timestamp=datetime.utcnow().isoformat(), 
    content="Hello, I purchased a TechGear Pro Laptop, but I can't find the invoice in my email. Sincerely, David Jones david@example.org"
)

# Send the JSON object as one message
value = kafka_message.model_dump_json().encode('utf-8')

producer.send(TOPIC_NAME, value)

print(f"Sent: {value}")

# Ensure all messages are sent before exiting
producer.flush()
producer.close()

