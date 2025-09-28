# --------------------------------------------------------------
# input topic, LLM processor, output processor
# --------------------------------------------------------------

# Add the parent directory to the Python path
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kafka import KafkaConsumer, KafkaProducer
from dotenv import load_dotenv
from models import OuterWrapper, WebsiteResponse
import json
import logging
from openai import OpenAI
import requests

# Set up logging configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)
logging.getLogger("kafka").setLevel(logging.WARNING)
logging.getLogger("kafka.conn").setLevel(logging.WARNING)

# Load env vars
load_dotenv()

API_KEY=os.getenv("WEBSITE_API_KEY")
INFERENCE_SERVER_URL=os.getenv("WEBSITE_SERVER_URL")
MODEL_NAME=os.getenv("WEBSITE_MODEL_NAME")

KAFKA_BROKER=os.getenv("KAFKA_BROKER")
KAFKA_INPUT_TOPIC=os.getenv("KAFKA_WEBSITE_INPUT_TOPIC")
KAFKA_OUTPUT_TOPIC=os.getenv("KAFKA_OUTFLOW_TOPIC")
KAFKA_REVIEW_TOPIC=os.getenv("KAFKA_REVIEW_TOPIC")

API_HOST = os.getenv("WEBSITE_API_HOST")
API_PORT = int(os.getenv("WEBSITE_API_PORT"))

logger.info(f"INFERENCE_SERVER_URL: {INFERENCE_SERVER_URL}")
logger.info(f"MODEL_NAME: {MODEL_NAME}")
logger.info(f"Kafka bootstrap servers: {KAFKA_BROKER}")
logger.info(f"Kafka input topic: {KAFKA_INPUT_TOPIC}")
logger.info(f"API HOST: {API_HOST}")
logger.info(f"API PORT: {API_PORT}")


llmclient = OpenAI(
    api_key=API_KEY,
    base_url=INFERENCE_SERVER_URL
    )


system_prompt = "You are an expert tool calling, review the user message and call the best matching tool"

# --------------------------------------------------------------
# Tool OpenAI definition 
# --------------------------------------------------------------
tools = [
    {
        "type": "function",
        "function": {
            "name": "password_reset",
            "description": "Reset password based on provided email address",
            "parameters": {
                "type": "object",
                "properties": {
                    "email": {
                        "type": "string",
                        "description": "The email address of the customer who needs their password reset."
                    }
                },
                "required": ["email"],
                "additionalProperties": False  
            },
            "strict": True,
        },
    }
]

# --------------------------------------------------------------
# Any tool invoker
# --------------------------------------------------------------
def call_function(name, args):
    if name == "password_reset":
        return password_reset(**args)

# --------------------------------------------------------------
# Actual Tool call 
# --------------------------------------------------------------
def password_reset(email):
    password_api_url = f"http://{API_HOST}:{API_PORT}/password-reset"
    
    logger.info(f"\npassword reset invoked: {email}")
    logger.info(f"for API: {password_api_url}\n")

    payload = {"email": email}
    try:
        response = requests.post(password_api_url,json=payload)
    except requests.exceptions.RequestException as e:
        print(f"\nError: {e}")
        return None


# --------------------------------------------------------------
# Handles each message, processes, sends the message on
# --------------------------------------------------------------
class MessageProcessor():
    def __init__(self):
        self.consumer = KafkaConsumer(
            KAFKA_INPUT_TOPIC,
            bootstrap_servers=KAFKA_BROKER,
            value_deserializer=lambda x: json.loads(x.decode('utf-8')),
            # auto_offset_reset='earliest', # aids debugging
            auto_offset_reset='latest',
            enable_auto_commit=False            
            # group_id='support_responder',            
        )

        self.producer = KafkaProducer(
            bootstrap_servers=KAFKA_BROKER,
            value_serializer=lambda x: json.dumps(x, default=str).encode('utf-8')
        )

    

    # --------------------------------------------------------------
    # process each message
    # --------------------------------------------------------------
    def process(self, message:OuterWrapper) -> OuterWrapper:
        try:
            tool_call_invoked = False
            # -------------------------------------------------------
            # LLM Magic Happens
            # -------------------------------------------------------
            
            llmmessages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": message.content}
            ]
            
            response = llmclient.chat.completions.create(
                model=MODEL_NAME,  
                messages=llmmessages,
                tools=tools,
                tool_choice="auto",
            )
            logger.info(f"LLM Response: {response}")

            # look for tool calls and dynamically invoke those tools

            if response.choices[0].message.tool_calls:
                for tool_call in response.choices[0].message.tool_calls:
                    name = tool_call.function.name
                    args = json.loads(tool_call.function.arguments)
        
                    # logger.info("What? %s", response.choices[0].message)
                    llmmessages.append(response.choices[0].message)

                    result = call_function(name, args)
                    tool_call_invoked=True
                    llmmessages.append(
                        {"role": "tool", "tool_call_id": tool_call.id, "content": json.dumps(result)}
                    )
            # if tool call fails, send to review
            if not tool_call_invoked:
                reset_response = WebsiteResponse(
                    response="Tool NOT Invoked",
                    toolinvoked=False
                )
                message.website = reset_response
            else:
                reset_response = WebsiteResponse(
                    response="Tool Invoked",
                    toolinvoked=True
                )                
                message.website = reset_response

            # -------------------------------------------------------
            # LLM Magic Happens
            # -------------------------------------------------------

            return message
        except Exception as e:
            # Need to say something about what when wrong
            logger.error(f"BAD Thing: {e}")
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
                # logger.info(f"Message data type: {type(message_data)}")
                # logger.info(f"Message data: {message_data}")

                # Convert JSON data into a Pydantic Message object
                try:                 
                    message = OuterWrapper(**message_data)
                    # Process the message
                    processed_message = self.process(message)
                    logger.info(f"After Processing message: {processed_message}")
                    if processed_message.website and processed_message.website.toolinvoked:
                        self.producer.send(KAFKA_OUTPUT_TOPIC, processed_message.model_dump())
                    else: 
                        self.producer.send(KAFKA_REVIEW_TOPIC, processed_message.model_dump())
                except Exception as e:
                    logger.error(f"Failed to create Message object: {str(e)}")
                    logger.error(f"Message data that caused error: {message_data}")
                    raise
    
        except Exception as e:
            logger.error(f"Error processing message: {str(e)}")
            error_message = OuterWrapper(
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
