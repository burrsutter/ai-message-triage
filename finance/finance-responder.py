# --------------------------------------------------------------
# input topic, LLM processor, output processor
# --------------------------------------------------------------

# Add the parent directory to the Python path
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kafka import KafkaConsumer, KafkaProducer
from dotenv import load_dotenv
from models import OuterWrapper, FinanceResponse
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

API_KEY=os.getenv("FINANCE_API_KEY")
INFERENCE_SERVER_URL=os.getenv("FINANCE_SERVER_URL")
MODEL_NAME=os.getenv("FINANCE_MODEL_NAME")

KAFKA_BROKER=os.getenv("KAFKA_BROKER")
KAFKA_INPUT_TOPIC=os.getenv("KAFKA_FINANCE_INPUT_TOPIC")
KAFKA_OUTPUT_TOPIC=os.getenv("KAFKA_OUTFLOW_TOPIC")
KAFKA_REVIEW_TOPIC=os.getenv("KAFKA_REVIEW_TOPIC")

API_HOST = os.getenv("FINANCE_API_HOST")
API_PORT = int(os.getenv("FINANCE_API_PORT"))

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
            "name": "get_order_history",
            "description": "Retrieve a customer's order history based on their email.",
            "parameters": {
                "type": "object",
                "properties": {
                    "email": {
                        "type": "string",
                        "description": "Customer's email address"
                    }
                },                
                "required": ["email"],
                "additionalProperties": False 
            },
            "strict": True
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_invoice_history",
            "description": "Retrieve a customer's invoice history based on their email.",
            "parameters": {
                "type": "object",
                "properties": {
                    "email": {
                        "type": "string",
                        "description": "The email address of the customer whose invoice history is being requested."
                    }
                },
                "required": ["email"],
                "additionalProperties": False  
            },
            "strict": True
        }
    },
    {
        "type": "function",
        "function": {
            "name": "start_duplicate_charge_dispute",
            "description": "Start the process to dispute a duplicate charge for a customer.",
            "parameters": {
                "type": "object",
                "properties": {
                    "email": {
                        "type": "string",
                        "description": "The email address of the customer initiating the dispute."
                    }
                },
                "required": ["email"],
                "additionalProperties": False  
            },
            "strict": True
        }
    },
    {
        "type": "function",
        "function": {
            "name": "find_lost_receipt",
            "description": "Start the process to find a lost receipt for a customer.",
            "parameters": {
                "type": "object",
                "properties": {
                    "email": {
                        "type": "string",
                        "description": "The email address of the customer who lost their receipt."
                    }
                },
                "required": ["email"],
                "additionalProperties": False  
            },
            "strict": True
        }
    }
]

# --------------------------------------------------------------
# Any tool invoker
# --------------------------------------------------------------
def call_function(name, args):
    if name == "get_order_history":
        return get_order_history(**args)
    if name == "get_invoice_history":
        return get_invoice_history(**args)
    if name == "start_duplicate_charge_dispute":
        return start_duplicate_charge_dispute(**args)
    if name == "find_lost_receipt":
        return find_lost_receipt(**args)    

# --------------------------------------------------------------
# Tool call: order_history
# --------------------------------------------------------------
def get_order_history(email):
    finance_api_url = f"http://{API_HOST}:{API_PORT}/get_order_history"
    
    payload = {"email": email}
    try:
        response = requests.post(finance_api_url,json=payload)
        logger.info(f"\nget_order_history invoked: {email}")
        # logger.info(f"for API: {finance_api_url}\n")

    except requests.exceptions.RequestException as e:
        print(f"\nError: {e}")
        return None

# --------------------------------------------------------------
# Tool call: get_invoice_history
# --------------------------------------------------------------
def get_invoice_history(email):
    finance_api_url = f"http://{API_HOST}:{API_PORT}/get_invoice_history"
    
    payload = {"email": email}
    try:
        response = requests.post(finance_api_url,json=payload)
        logger.info(f"\get_invoice_history invoked: {email}")
        # logger.info(f"for API: {finance_api_url}\n")

    except requests.exceptions.RequestException as e:
        print(f"\nError: {e}")
        return None

# --------------------------------------------------------------
# Tool call: start_duplicate_charge_dispute
# --------------------------------------------------------------
def start_duplicate_charge_dispute(email):
    finance_api_url = f"http://{API_HOST}:{API_PORT}/start_duplicate_charge_dispute"
    
    payload = {"email": email}
    try:
        response = requests.post(finance_api_url,json=payload)
        logger.info(f"\start_duplicate_charge_dispute: {email}")
        # logger.info(f"for API: {finance_api_url}\n")

    except requests.exceptions.RequestException as e:
        print(f"\nError: {e}")
        return None

# --------------------------------------------------------------
# Tool call: find_lost_receipt
# --------------------------------------------------------------
def find_lost_receipt(email):
    finance_api_url = f"http://{API_HOST}:{API_PORT}/find_lost_receipt"
    
    payload = {"email": email}
    try:
        response = requests.post(finance_api_url,json=payload)
        logger.info(f"\nfind_lost_receipt invoked: {email}")
        # logger.info(f"for API: {finance_api_url}\n")

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
            auto_offset_reset='earliest', # aids debugging
            # auto_offset_reset='latest',
            enable_auto_commit=False # aids debugging
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
                temperature=.1
            )

            logger.info(f"LLM Response: {response.choices[0].message.tool_calls}")

            # look for tool calls and dynamically invoke those tools

            if response.choices[0].message.tool_calls:
                for tool_call in response.choices[0].message.tool_calls:
                    name = tool_call.function.name
                    args = json.loads(tool_call.function.arguments)                    
                    llmmessages.append(response.choices[0].message)
                    logger.info(f"attempting to call: {name}")
                    tool_result = call_function(name, args)
                    tool_call_invoked=True
                    llmmessages.append(
                        {"role": "tool", "tool_call_id": tool_call.id, "content": json.dumps(tool_result)}
                    )
            
            # if tool call fails, send to review
            if not tool_call_invoked:
                fin_response = FinanceResponse(
                    response="Tool NOT Invoked",
                    toolinvoked=False
                )
                message.finance = fin_response
            else:
                fin_response = FinanceResponse(
                    response="Tool Invoked",
                    toolinvoked=True
                )                
                message.finance = fin_response

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
                # logger.info(f"Before Processing message: {type(kafka_message)}")          
                # Extract the JSON payload from the Kafka message
                message_data = kafka_message.value  # `value` contains the deserialized JSON payload
                # logger.info(f"Message data type: {type(message_data)}")
                # logger.info(f"Message data: {message_data}")

                # Convert JSON data into a Pydantic Message object
                try:                 
                    message = OuterWrapper(**message_data)
                    # Process the message
                    processed_message = self.process(message)
                    logger.info(f"After processing: {processed_message.finance}")
                    if processed_message.finance and processed_message.finance.toolinvoked:
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
