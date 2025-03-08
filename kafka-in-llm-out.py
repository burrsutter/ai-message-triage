# --------------------------------------------------------------
# input topic, LLM processor, output processor
# --------------------------------------------------------------

from kafka import KafkaConsumer, KafkaProducer
from dotenv import load_dotenv
from openai import OpenAI
from models import Message
from models import AnalyzedMessage
import json
import os
import logging
from openai import OpenAI


# Load env vars
load_dotenv()

KAFKA_BROKER=os.getenv("KAFKA_BROKER")
KAFKA_INPUT_TOPIC=os.getenv("KAFKA_INPUT_TOPIC") 
KAFKA_OUTPUT_TOPIC=os.getenv("KAFKA_OUTPUT_TOPIC")
KAFKA_REVIEW_TOPIC=os.getenv("KAFKA_REVIEW_TOPIC")
MODEL_NAME=os.getenv("MODEL_NAME")
API_KEY=os.getenv("API_KEY")
INFERENCE_SERVER_URL=os.getenv("INFERENCE_SERVER_URL")

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

llmclient = OpenAI(
    api_key=API_KEY,
    base_url=INFERENCE_SERVER_URL
    )


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
    def process(self, message:Message) -> Message:
        try:
            logger.info("LLM Processing: " + message.content)

            # -------------------------------------------------------
            # LLM Magic Happens
            # -------------------------------------------------------

            completion = client.beta.chat.completions.parse(
                model=MODEL_NAME,
                messages=[
                    {"role": "system", "content": "Extract the customer support email information."},
                    {"role": "user", "content": message.content},
                ],
                response_format=AnalyzedMessage,
            )
            logger.info("chat completions")
            emailanalysis = completion.choices[0].message.parsed

            logger.info("-------")
            # logger.info(emailanalysis)            
            logger.info(f"Reason:   {emailanalysis.reason}")
            logger.info(f"Customer: {emailanalysis.customer_name}")
            logger.info(f"Email:    {emailanalysis.email_address}")
            logger.info(f"Product:  {emailanalysis.product_name}")
            logger.info(f"Sentiment:{emailanalysis.sentiment}")
            logger.info(f"Escalate: {emailanalysis.escalate}")
            logger.info("-------")

            message.structured=emailanalysis
            # -------------------------------------------------------
            # LLM Magic Happens
            # -------------------------------------------------------

            return message
        except Exception as e:
            # Need to say something about what when wrong
            logger.error(f"BAD Thing: {e}")
            return message
    
    def to_review(self, message: Message):
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

                # Convert JSON data into a Pydantic Message object
                message = Message(**message_data)

                # Process the message
                processed_message = self.process(message)
                logger.info(f"After Processing message: {processed_message}")

                # Send the message to output
                self.producer.send(KAFKA_OUTPUT_TOPIC,processed_message)


        except Exception as e:
            logger.error(f"Error processing message: {str(e)}")
            error_message = Message(
                id="error",
                filename="error.txt",
                content=str(e),
                error=[str(e)]
            )
            self.to_review(error_message)
        finally:
          self.consumer.close()
          self.producer.close()
          logger.info("Closed Kafka connections")

if __name__ == "__main__":
    processor = MessageProcessor()
    processor.run()
