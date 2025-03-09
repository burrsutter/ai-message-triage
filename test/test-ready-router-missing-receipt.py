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
    "id": "234755672",
    "filename": "missing-receipt.txt",
    "content": "Hello, I need a copy of the receipt for my annual CloudSync subscription. Can you send it to me?\nSincerely,\nFran Wilson\nfranwilson@example.com",
    "metadata": {
        "original_path": "/Users/burr/ai-projects/ai-message-triage/data/intake/missing-receipt.txt",
        "size_bytes": 142,
        "created_timestamp": 1741546397.8146265,
        "modified_timestamp": 1741546397.8145192
    },
    "timestamp": "2025-03-09T18:53:17.827870",
    "structured": {
        "reason": "Receipt for Subscription",
        "sentiment": "positive",
        "company_id": "LONEP",
        "company_name": "Lonesome Pine Restaurant",
        "customer_name": "Fran Wilson",
        "country": "USA",
        "email_address": "franwilson@example.com",
        "phone": "(503) 555-9573",
        "product_name": "CloudSync",
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
