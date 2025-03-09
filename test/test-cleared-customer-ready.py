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
TOPIC_NAME=os.getenv("KAFKA_CUSTOMER_INPUT_TOPIC") 

# Create a Kafka producer with a serializer
producer = KafkaProducer(
    bootstrap_servers=KAFKA_BROKER,
    value_serializer=lambda x: json.dumps(x, default=str).encode('utf-8')
)

json_string = """
{
    "id": "234725096",
    "filename": "missing-invoice.txt",
    "content": "Hello, I purchased a TechGear Pro Laptop, but I can't find the invoice in my email. Sincerely, Liu liuwong@example.com",
    "metadata": {
        "original_path": "/Users/burr/ai-projects/ai-message-triage/data/intake/missing-invoice.txt",
        "size_bytes": 118,
        "created_timestamp": 1741540092.395851,
        "modified_timestamp": 1741540092.3957803
    },
    "timestamp": "2025-03-09T17:08:12.418664",
    "structured": {
        "reason": "cannot find invoice",
        "sentiment": " neutral , possibly disappointed. but did show identity of being a customer",
        "company_id": "Not requested",
        "company_name": "Not provided",
        "customer_name": "Liu",
        "country": "Not disclosed , can use info to track",
        "email_address": "liuwong@example.com",
        "phone": "Not provided",
        "product_name": "TechGear Pro Laptop",
        "escalate": False
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
