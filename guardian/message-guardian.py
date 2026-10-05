# --------------------------------------------------------------
# input topic, LLM processor, output processor
# --------------------------------------------------------------

from kafka import KafkaConsumer, KafkaProducer
from dotenv import load_dotenv
from openai import OpenAI
from models import OuterWrapper
from guardian.classifier import POLICIES, classify_content, resolve_guardian_mode
import json
import os
import logging


# Load env vars
load_dotenv()
KAFKA_BROKER=os.getenv("KAFKA_BROKER")
KAFKA_INPUT_TOPIC=os.getenv("KAFKA_GUARDIAN_INPUT_TOPIC")
KAFKA_OUTPUT_TOPIC=os.getenv("KAFKA_GUARDIAN_OUTPUT_TOPIC")
KAFKA_REVIEW_TOPIC=os.getenv("KAFKA_REVIEW_TOPIC")

MODEL_NAME=os.getenv("GUARDIAN_MODEL_NAME") or os.getenv("MODEL_NAME")
API_KEY=os.getenv("GUARDIAN_API_KEY") or os.getenv("API_KEY")
INFERENCE_SERVER_URL=os.getenv("GUARDIAN_SERVER_URL") or os.getenv("INFERENCE_SERVER_URL")
GUARDIAN_MODE=os.getenv("GUARDIAN_MODE", "auto")

client = OpenAI(api_key=API_KEY, base_url=INFERENCE_SERVER_URL)


# Set up logging configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)
logging.getLogger("kafka").setLevel(logging.WARNING)
logging.getLogger("kafka.conn").setLevel(logging.WARNING)

logger.info(f"Kafka bootstrap servers: {KAFKA_BROKER}")
logger.info(f"Kafka input topic: {KAFKA_INPUT_TOPIC}")
logger.info(f"Kafka output topic: {KAFKA_OUTPUT_TOPIC}")
logger.info(f"Inference Server: {INFERENCE_SERVER_URL}")
logger.info(f"Model: {MODEL_NAME}")
logger.info(f"Guardian mode: {resolve_guardian_mode(MODEL_NAME, GUARDIAN_MODE)}")

# -------------------------------------------------------
# Debugging function
# -------------------------------------------------------
def log_dict_elements(d, prefix=""):
    """
    Recursively logs each key-value pair in a dictionary.
    
    :param d: Dictionary to log.
    :param prefix: String prefix for nested keys.
    """
    for key, value in d.items():
        full_key = f"{prefix}.{key}" if prefix else key
        
        if isinstance(value, dict):  # Recursively log nested dictionaries
            logging.info(f"{full_key}: [Nested Dictionary]")
            log_dict_elements(value, full_key)
        else:
            logging.info(f"{full_key}: {value}")


class MessageProcessor():
    def __init__(self):
        self.consumer = KafkaConsumer(
            KAFKA_INPUT_TOPIC,
            bootstrap_servers=KAFKA_BROKER,
            value_deserializer=lambda x: json.loads(x.decode('utf-8')),
            auto_offset_reset=os.getenv("KAFKA_AUTO_OFFSET_RESET", "latest"),
            group_id=os.getenv("KAFKA_GUARDIAN_GROUP_ID"),
            enable_auto_commit=True
        )

        self.producer = KafkaProducer(
            bootstrap_servers=KAFKA_BROKER,
            value_serializer=lambda x: json.dumps(x, default=str).encode('utf-8')
        )

    # Takes the input, modifies, returns it back    
    def process(self, message:OuterWrapper) -> OuterWrapper:
        logger.info("LLM Processing: " + message.content)
        if message.error is None:
            message.error = []

        for category in POLICIES:
            try:
                decision = classify_content(
                    client=client,
                    model_name=MODEL_NAME,
                    category=category,
                    content=message.content,
                    mode=GUARDIAN_MODE,
                )
                logger.info(
                    "Guardian decision category=%s unsafe=%s reason=%s",
                    category,
                    decision.unsafe,
                    decision.reason,
                )
                if decision.unsafe:
                    message.error.append(f"guardian:{category}")
            except Exception as e:
                # A safety service must not silently clear a message it could not
                # classify. Mark the result indeterminate so it is sent to review.
                logger.error("Guardian classification failed for %s: %s", category, e)
                message.error.append(f"guardian:{category}:classification_error")

        return message
    
    def to_review(self, message: OuterWrapper):
        try:
            self.producer.send(KAFKA_REVIEW_TOPIC, message.model_dump())
            self.producer.flush()
            logger.info(f"Message sent to topic: {KAFKA_REVIEW_TOPIC}")
        except Exception as e:
            logger.error(f"Error sending message to topic {KAFKA_REVIEW_TOPIC}: {str(e)}")
        
    # -------------------------------------------------------
    # Action Happens
    # -------------------------------------------------------
    def run(self):       
        try:
            logger.info("Starting message processor...")
            for kafka_message in self.consumer:
                logger.info(f"Before Processing message: {type(kafka_message)}")                
                # Extract the JSON payload from the Kafka message
                message_data = kafka_message.value  # `value` contains the deserialized JSON payload
                logger.info(f"Kafka Message: {message_data}")
                # Convert Kafka JSON data into a Pydantic Message object                
                try:
                    message = OuterWrapper(**message_data)
                except Exception as e:
                    logger.error(f"Failed to create Message object: {str(e)}")
                    logger.error(f"Message data that caused error: {message_data}")
                    raise

                logger.info(f"Pydantic Message: {message}")
                # Process the message via LLM calls
                processed_message = self.process(message)
                logger.info(f"After Processing message: {processed_message}")
                
                # If there are errors attached, route to the review topic/queue
                if len(processed_message.error) > 0:
                    self.to_review(processed_message)
                else:                
                    self.producer.send(KAFKA_OUTPUT_TOPIC,processed_message.model_dump())
                    

        except Exception as e:
            logger.error(f"Error processing message: {str(e)}")
            error_message = OuterWrapper(
                id="error",
                filename="error.txt",
                content="Error processing message", 
                error=["guardian"]
            )
            self.to_review(error_message)
        finally:
          self.consumer.close()
          self.producer.close()
          logger.info("Closed Kafka connections")

if __name__ == "__main__":
    processor = MessageProcessor()
    processor.run()
