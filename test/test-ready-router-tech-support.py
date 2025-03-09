import sys
import os
# Add the parent directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models import OuterWrapper, StructuredObject
from kafka import KafkaProducer
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

json_string = """
{
    "id": "234767430",
    "filename": "technical-support.txt",
    "content": "Hello, I purchased a TechGear Pro Laptop, but it won't boot.  Liu Wong liuwong@example.com",
    "metadata": {
        "original_path": "/Users/burr/ai-projects/ai-message-triage/data/intake/technical-support.txt",
        "size_bytes": 90,
        "created_timestamp": 1741547094.6227882,
        "modified_timestamp": 1741547094.6227417
    },
    "timestamp": "2025-03-09T19:04:54.648310",
    "structured": {
        "reason": "laptop does not boot",
        "sentiment": "negative",
        "company_id": "THECR",
        "company_name": "The Cracker Box",
        "customer_name": "Liu Wong",
        "country": "USA",
        "email_address": "liuwong@example.com",
        "phone": "(406) 555-5834",
        "product_name": "TechGear Pro Laptop",
        "escalate": true
    },
    "route": null,
    "comment": null,
    "error": []
}
"""

message = OuterWrapper.model_validate_json(json_string)

# Send the message as a dictionary
producer.send(TOPIC_NAME, message.model_dump())

print(f"Sent: {message.model_dump()}")

# Ensure all messages are sent before exiting
producer.flush()
producer.close()
