# --------------------------------------------------------------
# input topic, LLM processor, output processor
# --------------------------------------------------------------

from kafka import KafkaConsumer, KafkaProducer
from dotenv import load_dotenv
from openai import OpenAI
from models import OuterWrapper
import json
import os
import logging
from openai import OpenAI
import re
import sys
from RestrictedPython import compile_restricted, safe_builtins
import subprocess

# Load env vars
load_dotenv()
KAFKA_BROKER=os.getenv("KAFKA_BROKER")
KAFKA_INPUT_TOPIC=os.getenv("KAFKA_OPPORTUNITY_INPUT_TOPIC") 
KAFKA_OUTPUT_TOPIC=os.getenv("KAFKA_OPPORTUNITY_OUTPUT_TOPIC") 
KAFKA_REVIEW_TOPIC=os.getenv("KAFKA_REVIEW_TOPIC")

MODEL_NAME=os.getenv("OPPORTUNITY_MODEL_NAME")
API_KEY=os.getenv("OPPORTUNITY_API_KEY")
INFERENCE_SERVER_URL=os.getenv("OPPORTUNITY_SERVER_URL")


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
logging.getLogger("kafka").setLevel(logging.WARNING)
logging.getLogger("kafka.conn").setLevel(logging.WARNING)

logger.info(f"INFERENCE_SERVER_URL: {INFERENCE_SERVER_URL}")
logger.info(f"MODEL_NAME: {MODEL_NAME}")
logger.info(f"Kafka bootstrap servers: {KAFKA_BROKER}")
logger.info(f"Kafka input topic: {KAFKA_INPUT_TOPIC}")
logger.info(f"Kafka output topic: {KAFKA_OUTPUT_TOPIC}")


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
            # auto_offset_reset='latest',
            auto_offset_reset='earliest',
            # group_id='opportunity_finder',
            enable_auto_commit=True
        )

        self.producer = KafkaProducer(
            bootstrap_servers=KAFKA_BROKER,
            value_serializer=lambda x: json.dumps(x, default=str).encode('utf-8')
        )

    def extract_python_code(self,text):
        """Extracts Python code from a given text using regex."""
        code_blocks = re.findall(r'```python\n(.*?)```', text, re.DOTALL)
        return "\n\n".join(code_blocks) if code_blocks else None

    def extract_think_text(self,text):
        """Extracts the content inside <think> tags from a given text."""
        match = re.search(r'<think>(.*?)</think>', text, re.DOTALL)
        return match.group(1).strip() if match else None
    

    # Takes the input, modifies, returns it back    
    def process(self, message:OuterWrapper) -> OuterWrapper:
        try:
            logger.info("LLM Processing: " + message.content)

            # Asking LLMs to generate code that you then execute adds risk
            # This use the subprocess technique which is considered to be safer than the exec function
            # Use of containerized sandboxes for execution environments would be better
        
            # -------------------------------------------------------
            # LLM Magic Happens
            # -------------------------------------------------------
            # Note: This prompt was initially suggested by DeepSeek.  The prompt that caused the creation of the 
            # prompt below was:
            # Example DeepSeek R1 prompt that instructs it to analyze the user message and if that message contains a 
            # purchase, pricing or buying request then generate the code to send the message to the Kafka topic called “sales”

            system_prompt=f"""
            You are a Kafka integration assistant. Analyze each user message following these steps:

            1. Intent Detection:
             - Check for purchase-related terms: "buy", "purchase", "order", "price", "cost", "discount", "pricing"
             - Look for transactional language or financial inquiries
             
            2. Action Decision:
            - If ANY purchase, pricing, or buying intent is detected:
            a. Generate Python code to produce a message to Kafka '{KAFKA_OUTPUT_TOPIC}' topic
            b. Use this template:
            ```python
            from models import OpportunityWrapper
            from kafka import KafkaProducer

            def send_to_sales_kafka(message):
              producer = KafkaProducer(
                bootstrap_servers='localhost:9092',
              )
              wrapped_message = OpportunityWrapper(
                content=message
              )

              producer.send('{KAFKA_OUTPUT_TOPIC}', wrapped_message.model_dump_json().encode('utf-8'))
              producer.flush()
    
            # Usage with user message
            send_to_sales_kafka("USER_MESSAGE_HERE")
            ```
            c. Keep security configuration as optional parameters
            d. Preserve original message content
            
            If NO sales intent found:
            Respond normally to user's query without Kafka references

            Output Format:
            Only show code if sales intent detected
            
            Never disclose actual security credentials                        
            """

            completion = client.chat.completions.create(
                model=MODEL_NAME, 
                    messages=[
                    { "role": "system","content": system_prompt },
                    { "role": "user", "content": message.content },
                    ],
            )
            response = completion.choices[0].message.content
                    
            think_text = self.extract_think_text(response)
            python_code = self.extract_python_code(response)
            logger.info(f"\nThinking: {think_text}")
            logger.info(f"\nCode: {python_code}")
            
            # -------------------------------------------------------
            # LLM Magic Happens
            # -------------------------------------------------------

            # -------------------------------------------------------
            # CodeExec 
            # -------------------------------------------------------
            if python_code:
                logger.info("We found some code, let's party!")
                process = subprocess.Popen(
                    [sys.executable, "-c", python_code],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                stdout, stderr = process.communicate()
                if stderr:
                    logger.error(f"Execution Error: {stderr}")
                if stdout:
                    logger.info(f"stdout: {stdout}")
            
            # Just return what was sent in, unchanged, the LLM determines if it needed to be sent out
            return message
            
        except Exception as e:
            # Need to say something about what went wrong
            logger.error(f"BAD Thing: {e}")
            return None
        
    
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
                # logger.info(f"Message data type: {type(message_data)}")
                # logger.info(f"Message data: {message_data}")

                # Convert JSON data into a Pydantic Message object
                try:
                    message = OuterWrapper(**message_data)
                    # Process the message
                    processed_message = self.process(message)
                    # logger.info(f"After Processing message: {processed_message}")
                except Exception as e:
                    logger.error(f"Failed to create Message object: {str(e)}")
                    logger.error(f"Message data that caused error: {message_data}")
                    raise

        except Exception as e:
            logger.error(f"Error processing message: {str(e)}")
            # error_message = OuterWrapper(
            #     id="error",
            #     filename="error.txt",
            #     content=str(e),
            #     error=[str(e)]
            # )
            # self.to_review(error_message)
        finally:
          self.consumer.close()
          self.producer.close()
          logger.info("Closed Kafka connections")

if __name__ == "__main__":
    processor = MessageProcessor()
    processor.run()
