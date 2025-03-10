import psycopg2
import numpy as np
from openai import OpenAI
from dotenv import load_dotenv
import os
import logging
import textract
from langchain.text_splitter import RecursiveCharacterTextSplitter
from sentence_transformers import SentenceTransformer

load_dotenv()

# Set up logging configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

API_KEY=os.getenv("API_KEY")
INFERENCE_SERVER_URL=os.getenv("INFERENCE_SERVER_URL")
MODEL_NAME=os.getenv("MODEL_NAME")
DBNAME=os.getenv("KBASE_DBNAME")
DBUSER=os.getenv("KBASE_DBUSER")
DBPASSWORD=os.getenv("KBASE_DBPASSWORD")
DBHOST=os.getenv("KBASE_DBHOST")
DBPORT=os.getenv("KBASE_DBPORT")

logger.info(f"INFERENCE_SERVER_URL: {INFERENCE_SERVER_URL}")
logger.info(f"MODEL_NAME: {MODEL_NAME}")
logger.info(f"DBNAME: {DBNAME}")
logger.info(f"DBHOST: {DBHOST}")
logger.info(f"DBPORT: {DBPORT}")

client = OpenAI(
    api_key=API_KEY,
    base_url=INFERENCE_SERVER_URL
    )


# Connect to PostgreSQL
conn = psycopg2.connect(
    dbname=DBNAME,
    user=DBUSER,
    password=DBPASSWORD,
    host=DBHOST,
    port=DBPORT
)

cursor = conn.cursor()

# Load Sentence Transformer model (all-mpnet-base-v2)
os.environ["TOKENIZERS_PARALLELISM"] = "false"
model = SentenceTransformer("sentence-transformers/all-mpnet-base-v2")

# Create table to store documents and embeddings
cursor.execute("""
    CREATE TABLE IF NOT EXISTS techkbase (
        id SERIAL PRIMARY KEY,
        content TEXT,
        embedding VECTOR(768)
    );
""")
conn.commit()

# Function to generate embeddings
def get_embedding(text):
    return model.encode(text, convert_to_numpy=True).tolist()  # Get embedding as a list

# Directory containing the documents
directory_path = './ingestion'

# Iterate over all files in the directory
for filename in os.listdir(directory_path):
    file_path = os.path.join(directory_path, filename)
    if os.path.isfile(file_path):
        # Extract text from the document
        logger.info(file_path)
        text = textract.process(file_path).decode('utf-8')
        # text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        chunks = text_splitter.split_text(text)

        # Generate embedding for each text chunk and store in PostgreSQL
        for chunk in chunks:
            embedding = get_embedding(chunk)
            cursor.execute(
                "INSERT INTO techkbase (content, embedding) VALUES (%s, %s)",
                (chunk, embedding)
            )
    
conn.commit()

# Close the connection
cursor.close()
conn.close()