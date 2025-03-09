# --------------------------------------------------------------
# input topic, LLM processor, output processor
# --------------------------------------------------------------

from kafka import KafkaConsumer, KafkaProducer
from dotenv import load_dotenv
from openai import OpenAI
from models import OuterWrapper
from models import StructuredObject
import json
import os
import logging
from openai import OpenAI


# Load env vars
load_dotenv()
KAFKA_BROKER=os.getenv("KAFKA_BROKER")
KAFKA_INPUT_TOPIC=os.getenv("KAFKA_GUARDIAN_INPUT_TOPIC")
KAFKA_OUTPUT_TOPIC=os.getenv("KAFKA_GUARDIAN_OUTPUT_TOPIC")
KAFKA_REVIEW_TOPIC=os.getenv("KAFKA_REVIEW_TOPIC")

MODEL_NAME=os.getenv("GUARDIAN_MODEL_NAME")
API_KEY=os.getenv("GUARDIAN_API_KEY")
INFERENCE_SERVER_URL=os.getenv("GUARDIAN_SERVER_URL")

client = OpenAI(
    api_key=API_KEY,
    base_url=INFERENCE_SERVER_URL
    )


# Set up logging configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


logger.info(f"Kafka bootstrap servers: {KAFKA_BROKER}")
logger.info(f"Kafka input topic: {KAFKA_INPUT_TOPIC}")
logger.info(f"Kafka output topic: {KAFKA_OUTPUT_TOPIC}")
logger.info(f"Inference Server: {INFERENCE_SERVER_URL}")
logger.info(f"Model: {MODEL_NAME}")

llmclient = OpenAI(
    api_key=API_KEY,
    base_url=INFERENCE_SERVER_URL
    )

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
            auto_offset_reset='latest',
            enable_auto_commit=True
        )

        self.producer = KafkaProducer(
            bootstrap_servers=KAFKA_BROKER,
            value_serializer=lambda x: json.dumps(x, default=str).encode('utf-8')
        )

    # Takes the input, modifies, returns it back    
    def process(self, message:OuterWrapper) -> OuterWrapper:
        try:
            logger.info("LLM Processing: " + message.content)

            # -------------------------------------------------------
            # LLM Magic Happens
            # -------------------------------------------------------
            system_test="violence"
            completion = client.chat.completions.create(
                model=MODEL_NAME, # granite3-guardian:8b-fp16
                    messages=[
                    { "role": "system","content": system_test },
                    { "role": "user", "content": message.content, },
                    ],
            )
            response = completion.choices[0].message.content
            logger.info(f"violence {response}")
            if (response == "Yes"):                 
                message.error.append(f"guardian:{system_test}")

            system_test="social_bias"
            completion = client.chat.completions.create(
                model=MODEL_NAME, 
                    messages=[
                    { "role": "system","content": system_test },
                    { "role": "user", "content": message.content, },
                    ],
            )
            response = completion.choices[0].message.content
            logger.info(f"social_bias {response}")
            if (response == "Yes"):                 
                message.error.append(f"guardian:{system_test}")

            # too many false positives with the jailbreak test at this moment
            # system_test="jailbreak"
            # completion = client.chat.completions.create(
            #     model=MODEL_NAME, 
            #         messages=[
            #         { "role": "system","content": system_test },
            #         { "role": "user", "content": message.content, },
            #         ],
            # )
            # response = completion.choices[0].message.content
            # logger.info(f"jailbreak {response}")
            # if (response == "Yes"):                 
            #     message.error.append(f"guardian:{system_test}")

            system_test="profanity"
            completion = client.chat.completions.create(
                model=MODEL_NAME, 
                    messages=[
                    { "role": "system","content": system_test },
                    { "role": "user", "content": message.content, },
                    ],
            )
            response = completion.choices[0].message.content
            logger.info(f"profanity {response}")
            if (response == "Yes"):                 
                message.error.append(f"guardian:{system_test}")


            # -------------------------------------------------------
            # LLM Magic Happens
            # -------------------------------------------------------

            return message
        except Exception as e:
            # Need to say something about what when wrong
            logger.error(f"Exception in LLM Processing: {e}")
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
