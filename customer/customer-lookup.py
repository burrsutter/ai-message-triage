# --------------------------------------------------------------
# Using a LLM for a simple sql lookup is totally overkill
# --------------------------------------------------------------


from kafka import KafkaConsumer, KafkaProducer
from dotenv import load_dotenv
from openai import OpenAI
from models import Message
from models import AnalyzedMessage
import json
import os
import logging
import psycopg2
from psycopg2 import sql
from openai import OpenAI
from pydantic import BaseModel
from typing import List

# Load env vars
load_dotenv()

KAFKA_BROKER=os.getenv("KAFKA_BROKER")
KAFKA_INPUT_TOPIC=os.getenv("KAFKA_CUSTOMER_INPUT_TOPIC") 
KAFKA_OUTPUT_TOPIC=os.getenv("KAFKA_CUSTOMER_OUTPUT_TOPIC")
KAFKA_REVIEW_TOPIC=os.getenv("KAFKA_REVIEW_TOPIC")
MODEL_NAME=os.getenv("CUSTOMER_MODEL_NAME")
API_KEY=os.getenv("CUSTOMER_API_KEY")
INFERENCE_SERVER_URL=os.getenv("CUSTOMER_SERVER_URL")

DBNAME=os.getenv("CUSTOMER_DBNAME")
DBUSER=os.getenv("CUSTOMER_DBUSER")
DBPASSWORD=os.getenv("CUSTOMER_DBPASSWORD")
DBHOST=os.getenv("CUSTOMER_DBHOST")
DBPORT=os.getenv("CUSTOMER_DBPORT")


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
logger.info(f"Database Host+Port: {DBHOST}:{DBPORT}")
logger.info(f"Database: {DBNAME}")


llmclient = OpenAI(
    api_key=API_KEY,
    base_url=INFERENCE_SERVER_URL
    )


class CustomerDetails(BaseModel):
    customer_id: str
    company_name: str
    contact_name: str
    contact_email: str
    country: str
    phone: str

class CustomerList(BaseModel):
    customers: List[CustomerDetails]    

llm_messages = [
    {"role": "system", "content": "You are a helpful assistant that must the contact_search tool"}
]

# --------------------------------------------------------------
# Tool Execution Logic
# --------------------------------------------------------------

def find_the_customer_by_contact_email(contact_email) -> CustomerList:
    logger.info(f"find_the_customer_by_contact_email: {contact_email}")

    connection = None
    cursor = None

    try:
        # Establish a connection to the PostgreSQL database
        connection = psycopg2.connect(
            dbname=DBNAME,
            user=DBUSER,
            password=DBPASSWORD,
            host=DBHOST,
            port=DBPORT
        )

        logger.info(f"Database {DBNAME}")
        logger.info(f"Database Host+Port: {DBHOST}:{DBPORT}")
        
        # Create a cursor object to interact with the database
        cursor = connection.cursor()

        # Execute a query to retrieve the desired customers by contact name        
        query = sql.SQL("""
        SELECT customer_id, company_name, contact_name, contact_email, country, phone
        FROM customers
        WHERE contact_email = '%s'
        """)

        cursor.execute(query, contact_email)
        logger.info("cursor.execute")

        # Fetch all customer records
        customers = cursor.fetchall()
        logger.info("cursor.fetchall")

        if customers:
            customers_list = [
                CustomerDetails(
                    customer_id=customer[0],
                    company_name=customer[1],
                    contact_name=customer[2],
                    contact_email=customer[3],
                    country=customer[4],
                    phone=customer[5]
                )
                for customer in customers
            ]
            logger.info("Database query found customer(s):")
            for customer in customers_list:                
                logger.info("Customer ID: %s, Company Name: %s", customer.customer_id, customer.company_name)
            return customers_list
        else:
            return None

    except Exception as error:
        logger.error(f"Error connecting to PostgreSQL database: {error}")
        return json.dumps({"error": str(error)})

    finally:
        # Close the cursor and connection to clean up
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# --------------------------------------------------------------
# Tool Definition (OpenAI)
# --------------------------------------------------------------

tools = [
    {
        "type" : "function",
        "function" : {
            "name": "find_the_customer_by_contact_email",
            "description": "Find and return the customer details by contact email address",
            "parameters": {
                "type": "object",
                "properties" : {
                    "contact_email": {"type": "string", "description": "contact email address"},
                },
                "required": ["contact_email"],
                "additionalProperties": False,
            },
            "strict": True,
        },
    }
]


class MessageProcessor():
    def __init__(self):
        self.consumer = KafkaConsumer(
            KAFKA_INPUT_TOPIC,
            bootstrap_servers=KAFKA_BROKER,
            value_deserializer=lambda x: json.loads(x.decode('utf-8')),
            auto_offset_reset='earliest',
            # auto_offset_reset='latest',
            enable_auto_commit=True
        )

        self.producer = KafkaProducer(
            bootstrap_servers=KAFKA_BROKER,
            value_serializer=lambda x: json.dumps(x, default=str).encode('utf-8')
        )

    # Takes the input, modifies, returns it back    
    def process(self, email_address) -> CustomerList:
        try:
            logger.info("LLM Processing: " + email_address)

            # -------------------------------------------------------
            # LLM Magic Happens
            # -------------------------------------------------------
            llm_messages.append(
                {"role": "user", "content": "Contact email " + email_address}
            )
            completion = client.chat.completions.create(
                model=MODEL_NAME,    
                messages=llm_messages,
                tools=tools, 
                # tool_choice="required", # works with openai.com and ollama, not vLLM
                tool_choice="auto",
                temperature=0.1
            )

            completion.model_dump()

            # the callback

            def call_function(name, args):
                if name == "find_the_customer_by_contact_email":
                    logger.info("calling find_the_customer_by_contact_email")
                    return find_the_customer_by_contact_email(**args)


            # look inside the result for tool calls and make those tool calls

            if completion.choices[0].message.tool_calls:
                for tool_call in completion.choices[0].message.tool_calls:
                    name = tool_call.function.name
                    args = json.loads(tool_call.function.arguments)
                    # append the chatcompletion to the messages list
                    llm_messages.append(completion.choices[0].message)
                    result = call_function(name, args)  
                    # append the results of the tool call
                    llm_messages.append(
                        {"role": "tool", "tool_call_id": tool_call.id, "content": json.dumps(result)}
                    )
                    # log_messages(messages)


            # call the model again with the results of the tool/function call added
            completion_2 = client.beta.chat.completions.parse(
                model=MODEL_NAME,
                messages=llm_messages,
                tools=tools,
                response_format=CustomerList
            )

            final_response = completion_2.choices[0].message.parsed



            # -------------------------------------------------------
            # LLM Magic Happens
            # -------------------------------------------------------

            return final_response
        except Exception as e:
            # Need to say something about what when wrong
            logger.error(f"BAD Thing: {e}")
            return final_response
    
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
                logger.info(f"Kafka Message: {message_data}")
                
                # hard coding for now to see if the tool invocation works
                contact_email_address="liuwong@example.com"

                # Process the message via LLM calls
                processed_message = self.process(contact_email_address)
                logger.info(f"After Processing message: {processed_message}")
                
                # If there are errors attached, route to the review topic/queue
                if len(processed_message.error) > 0:
                    self.to_review(processed_message)
                else:                
                    self.producer.send(KAFKA_OUTPUT_TOPIC,processed_message)


        except Exception as e:
            logger.error(f"Error processing message: {str(e)}")
            error_message = Message(
                id="error",
                filename="error.txt",
                content="Error processing message", 
                error=["customer"]
            )
            self.to_review(error_message)
        finally:
          self.consumer.close()
          self.producer.close()
          logger.info("Closed Kafka connections")

if __name__ == "__main__":
    processor = MessageProcessor()
    processor.run()
