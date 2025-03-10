# --------------------------------------------------------------
# input topic, LLM processor, output processor
# --------------------------------------------------------------

# Add the parent directory to the Python path
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# from email import message
from kafka import KafkaConsumer, KafkaProducer
from dotenv import load_dotenv
from models import OuterWrapper, SupportResponse, StructuredObject
import json
import logging
import psycopg2
from pgvector.psycopg2 import register_vector
from transformers import AutoTokenizer, AutoModel
import torch
from openai import OpenAI

# Set up logging configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Load env vars
load_dotenv()

API_KEY=os.getenv("SUPPORT_API_KEY")
INFERENCE_SERVER_URL=os.getenv("SUPPORT_SERVER_URL")
MODEL_NAME=os.getenv("SUPPORT_MODEL_NAME")

KAFKA_BROKER=os.getenv("KAFKA_BROKER")
KAFKA_INPUT_TOPIC=os.getenv("KAFKA_SUPPORT_INPUT_TOPIC") 
KAFKA_OUTPUT_TOPIC=os.getenv("KAFKA_OUTFLOW_TOPIC")
KAFKA_REVIEW_TOPIC=os.getenv("KAFKA_REVIEW_TOPIC")

DBNAME=os.getenv("KBASE_DBNAME")
DBUSER=os.getenv("KBASE_DBUSER")
DBPASSWORD=os.getenv("KBASE_DBPASSWORD")
DBHOST=os.getenv("KBASE_DBHOST")
DBPORT=os.getenv("KBASE_DBPORT")
RAG_TABLE=os.getenv("KBASE_RAG_TABLE")

MAX_CONTEXT_LENGTH=4000

logger.info(f"INFERENCE_SERVER_URL: {INFERENCE_SERVER_URL}")
logger.info(f"MODEL_NAME: {MODEL_NAME}")
logger.info(f"Kafka bootstrap servers: {KAFKA_BROKER}")
logger.info(f"Kafka input topic: {KAFKA_INPUT_TOPIC}")
logger.info(f"DBNAME: {DBNAME}")
logger.info(f"DBHOST: {DBHOST}")
logger.info(f"DBPORT: {DBPORT}")


llmclient = OpenAI(
    api_key=API_KEY,
    base_url=INFERENCE_SERVER_URL
    )

# Load Sentence Transformer model (all-mpnet-base-v2)
os.environ["TOKENIZERS_PARALLELISM"] = "false"
tokenizer = AutoTokenizer.from_pretrained("sentence-transformers/all-mpnet-base-v2")
model = AutoModel.from_pretrained("sentence-transformers/all-mpnet-base-v2")

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
            enable_auto_commit=False            
            # group_id='support_responder',            
        )

        self.producer = KafkaProducer(
            bootstrap_servers=KAFKA_BROKER,
            value_serializer=lambda x: json.dumps(x, default=str).encode('utf-8')
        )

        self.connection = psycopg2.connect(
            dbname=DBNAME,
            user=DBUSER,
            password=DBPASSWORD,
            host=DBHOST,
            port=DBPORT
        )

    def retrievecontext(self, message:OuterWrapper) -> OuterWrapper:
        return message


    # --------------------------------------------------------------
    # Function to convert string into embeddings
    # --------------------------------------------------------------
    def get_query_embedding(self, query):
        inputs = tokenizer(query, return_tensors="pt", truncation=True, padding=True)
        with torch.no_grad():
            embeddings = model(**inputs).last_hidden_state.mean(dim=1)
        # Ensure we return a 1-D array (flatten if needed)
        return embeddings.numpy().flatten()


    # --------------------------------------------------------------
    # Function to retrieve relevant documents
    # --------------------------------------------------------------
    def retrieve_documents(self, query, top_k=3):
        query_embedding = self.get_query_embedding(query)
        cursor = self.connection.cursor()
        # Perform similarity search in PostgreSQL using pgvector
        cursor.execute(f"""
            SELECT id, content, source_file, chunk_index, embedding FROM {RAG_TABLE}
            ORDER BY embedding <-> %s::vector
            LIMIT %s;
        """, (query_embedding.tolist(), top_k))

        results = cursor.fetchall()

        retrieved_docs = []
        
        for result in results:
            doc_id, content, source_file, chunk_index, _ = result
            retrieved_docs.append({
                "id": doc_id,
                "content": content,
                "source_file": source_file,
                "chunk_index": chunk_index
            })

        cursor.close()
        return retrieved_docs


    # --------------------------------------------------------------
    # process each message
    # --------------------------------------------------------------
    def process(self, message:OuterWrapper) -> OuterWrapper:
        try:
            logger.info("RAG Processing: " + message.content)
            retrieved_docs = self.retrieve_documents(message.content)
            context = "\n\n".join([doc["content"] for doc in retrieved_docs])
            truncated_context = context[:MAX_CONTEXT_LENGTH] if len(context) > MAX_CONTEXT_LENGTH else context        
    
            print("-" * 50)
            print(f"truncated_context: {truncated_context}")
            print("-" * 50)
            
            # -------------------------------------------------------
            # LLM Magic Happens
            # -------------------------------------------------------
            prompt = f"""You are an AI that answers questions using the given context.
            If the context does not contain an answer, respond with \"I don't know\".
            Context:
            {truncated_context}

            Question: {message.content}
            Answer:"""
    
            response = llmclient.chat.completions.create(
                model=MODEL_NAME,  
                messages=[
                    {"role": "system", "content": "You are a helpful assistant answering questions based on the provided context."},
                    {"role": "user", "content": prompt}]
            )

            raggedanswer = response.choices[0].message.content.strip()
            logger.info(f"Ragged Response: {raggedanswer}")
            araggedresponse = SupportResponse(
                response = raggedanswer,
                source = None
            )
            message.support = araggedresponse
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
            register_vector(self.connection)
            
            for kafka_message in self.consumer:
                logger.info(f"Before Processing message: {type(kafka_message)}")                
                # Extract the JSON payload from the Kafka message
                message_data = kafka_message.value  # `value` contains the deserialized JSON payload
                logger.info(f"Message data type: {type(message_data)}")
                logger.info(f"Message data: {message_data}")

                # Convert JSON data into a Pydantic Message object
                try:                 
                    message = OuterWrapper(**message_data)
                    # Process the message
                    processed_message = self.process(message)
                    logger.info(f"After Processing message: {processed_message}")
                    self.producer.send(KAFKA_OUTPUT_TOPIC, processed_message.model_dump())
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
