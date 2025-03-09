from kafka import KafkaProducer
from models import OuterWrapper
from models import StructuredObject
import os
import uuid
import json
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
KAFKA_BROKER=os.getenv("KAFKA_BROKER")
TOPIC_NAME=os.getenv("KAFKA_ROUTER_INPUT_TOPIC") 

# Create a Kafka producer with a serializer
producer = KafkaProducer(
    bootstrap_servers=KAFKA_BROKER,
    value_serializer=lambda x: json.dumps(x, default=str).encode('utf-8')
)

json_string = json.dumps(
{
    "id": "234771423",
    "filename": "help-password.txt",
    "content": "To whom it may concern, I forgot my password, how do I login?\n\nThomas \nthomashardy@example.com",
    "metadata": {
        "original_path": "/Users/burr/ai-projects/ai-message-triage/data/intake/help-password.txt",
        "size_bytes": 94,
        "created_timestamp": 1741548172.3606374,
        "modified_timestamp": 1741548172.3605683
    },
    "timestamp": "2025-03-09T19:22:52.383988",
    "structured": {
        "reason": "Customer needs help logging in",
        "sentiment": "neutral",
        "company_id": "AROUT",
        "company_name": "Around the Horn",
        "customer_name": "Thomas Hardy",
        "country": "UK",
        "email_address": "thomashardy@example.com",
        "phone": "(171) 555-7788",
        "product_name": "password change",
        "escalate": False
    },
    "route": None,
    "comment": None,
    "error": []
}
)

message = OuterWrapper.model_validate_json(json_string)

# Send the message as a dictionary
producer.send(TOPIC_NAME, message.model_dump())

print(f"Sent: {message.model_dump()}")

# Ensure all messages are sent before exiting
producer.flush()
producer.close()
