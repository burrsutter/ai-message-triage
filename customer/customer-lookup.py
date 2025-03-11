# --------------------------------------------------------------
# Grabs additional data from RDBMS
# --------------------------------------------------------------

from math import log
from kafka import KafkaConsumer, KafkaProducer
from dotenv import load_dotenv

from models import OuterWrapper
from models import StructuredObject
import json
import os
import logging
import psycopg2
from psycopg2 import sql

from pydantic import BaseModel, InstanceOf


# Load env vars
load_dotenv()

KAFKA_BROKER=os.getenv("KAFKA_BROKER")
KAFKA_INPUT_TOPIC=os.getenv("KAFKA_CUSTOMER_INPUT_TOPIC") 
KAFKA_OUTPUT_TOPIC=os.getenv("KAFKA_CUSTOMER_OUTPUT_TOPIC")
KAFKA_REVIEW_TOPIC=os.getenv("KAFKA_REVIEW_TOPIC")

DBNAME=os.getenv("CUSTOMER_DBNAME")
DBUSER=os.getenv("CUSTOMER_DBUSER")
DBPASSWORD=os.getenv("CUSTOMER_DBPASSWORD")
DBHOST=os.getenv("CUSTOMER_DBHOST")
DBPORT=os.getenv("CUSTOMER_DBPORT")



# Set up logging configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)
logging.getLogger("kafka").setLevel(logging.WARNING)
logging.getLogger("kafka.conn").setLevel(logging.WARNING)

logger.info(f"Kafka bootstrap servers: {KAFKA_BROKER}")
logger.info(f"Kafka input topic: {KAFKA_INPUT_TOPIC}")
logger.info(f"Kafka output topic: {KAFKA_OUTPUT_TOPIC}")
logger.info(f"Database Host+Port: {DBHOST}:{DBPORT}")
logger.info(f"Database: {DBNAME}")


class CustomerDetails(BaseModel):
    customer_id: str
    company_name: str
    contact_name: str
    contact_email: str
    country: str
    phone: str

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
    

# -------------------------------------------------------
# The meat and potatoes
# -------------------------------------------------------
def find_the_customer_by_contact_email(contact_email) -> CustomerDetails:
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
        WHERE contact_email = %s
        """)

        cursor.execute(query, (contact_email,))
        logger.info("cursor.execute")

        # Fetch all customer records
        customer = cursor.fetchone()
        logger.info("cursor.fetchone")

        if customer:            
            found_customer = CustomerDetails(
                customer_id=customer[0],
                company_name=customer[1],
                contact_name=customer[2],
                contact_email=customer[3],
                country=customer[4],
                phone=customer[5]
            )            
            logger.info("Database Customer: %s", found_customer.model_dump_json())
            return found_customer
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




class MessageProcessor():
    def __init__(self):
        self.consumer = KafkaConsumer(
            KAFKA_INPUT_TOPIC,
            bootstrap_servers=KAFKA_BROKER,
            value_deserializer=lambda x: json.loads(x.decode('utf-8')),            
            # auto_offset_reset='earliest', # debugging
            auto_offset_reset='latest',
            group_id='customer_lookup',
            enable_auto_commit=False
        )

        self.producer = KafkaProducer(
            bootstrap_servers=KAFKA_BROKER,
            value_serializer=lambda x: json.dumps(x, default=str).encode('utf-8'),
            acks="all",  # Wait for all replicas to acknowledge
            retries=3,   # Retry a few times if sending fails
        )

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
                # Extract the str dict payload from the Kafka message
                logger.info(f"Kafka message type: {type(kafka_message.value)}") # str
                logger.info(f"Kafka message value: {kafka_message.value}")
                if not kafka_message.value:
                    logger.error("Received an empty Kafka message!")
                    continue  # Skip processing this message

                try:
                    message_data = kafka_message.value
                    # logger.info(f"message_data: {message_data}")
                    # logger.info(f"message_data keys: {message_data.keys()}")
                    logger.info("\n----------------------------------")
                    log_dict_elements(message_data)
                    logger.info("\n----------------------------------")                    

                    # convert to Pydantic model
                    message = OuterWrapper(**message_data)

                    logger.info(f"Converted to Pydantic Message: {message}")
                    logger.info(f"type: {type(message)}")
                    
                    contact_email_address=message.structured.email_address
                    logger.info(f"Contact email address: {contact_email_address}")

                    the_found_customer = find_the_customer_by_contact_email(contact_email_address)
                    if the_found_customer:
                        logger.info(f"the_customer type: {type(the_found_customer)}")
                        # update the input message with the found database data
                        message.structured.company_id=the_found_customer.customer_id
                        message.structured.company_name=the_found_customer.company_name
                        message.structured.country=the_found_customer.country
                        message.structured.phone=the_found_customer.phone

                        logger.info(f"JSON: {message.model_dump_json()} ")

                        self.producer.send(KAFKA_OUTPUT_TOPIC,message.model_dump())
                    else: # if there is no match in the database, this is a prospect, not a customer
                        logger.info(f"No contact with email address: {contact_email_address}")
                        message.error = message.error.append(f"no contact: {contact_email_address}")
                        self.to_review(message)

                except json.JSONDecodeError as e:
                    logger.error(f"JSON decoding failed: {e}")
                except Exception as e:
                    logger.error(f"Failed to create Message object: {str(e)}")
                    logger.error(f"Message data that caused error: {message_data}")
                    raise

        except Exception as e:
            logger.error(f"Error processing message: {str(e)}")
            error_message = OuterWrapper(
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
