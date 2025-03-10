import psycopg2
# import numpy as np
import torch
from openai import OpenAI
from dotenv import load_dotenv
import os
import logging
from transformers import AutoTokenizer, AutoModel
from langchain.text_splitter import RecursiveCharacterTextSplitter


load_dotenv()

# Set up logging configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

API_KEY=os.getenv("SUPPORT_API_KEY")
INFERENCE_SERVER_URL=os.getenv("SUPPORT_SERVER_URL")
MODEL_NAME=os.getenv("SUPPORT_MODEL_NAME")
DBNAME=os.getenv("KBASE_DBNAME")
DBUSER=os.getenv("KBASE_DBUSER")
DBPASSWORD=os.getenv("KBASE_DBPASSWORD")
DBHOST=os.getenv("KBASE_DBHOST")
DBPORT=os.getenv("KBASE_DBPORT")
RAG_TABLE=os.getenv("KBASE_RAG_TABLE")
INGESTION_DIRECTORY=os.getenv("INGESTION_DIRECTORY")

logger.info(f"INFERENCE_SERVER_URL: {INFERENCE_SERVER_URL}")
logger.info(f"MODEL_NAME: {MODEL_NAME}")
logger.info(f"DBNAME: {DBNAME}")
logger.info(f"DBHOST: {DBHOST}")
logger.info(f"DBPORT: {DBPORT}")

# client = OpenAI(
#     api_key=API_KEY,
#     base_url=INFERENCE_SERVER_URL
#     )


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
tokenizer = AutoTokenizer.from_pretrained("sentence-transformers/all-mpnet-base-v2")
model = AutoModel.from_pretrained("sentence-transformers/all-mpnet-base-v2")
# note the 768 in the create table statement

# drop table if exists
cursor.execute(f"DROP TABLE IF EXISTS {RAG_TABLE};")
conn.commit()


# Create table to store documents and embeddings
cursor.execute(f"""
    CREATE TABLE IF NOT EXISTS {RAG_TABLE} (
        id SERIAL PRIMARY KEY,
        content TEXT,
        source_file TEXT,
        chunk_index INTEGER,        
        embedding VECTOR(768)
    );
""")
conn.commit()

logger.info(f"table {RAG_TABLE} created")

# Function to generate embeddings
def get_embedding(text):
    inputs = tokenizer(text, return_tensors="pt", truncation=True, padding=True)
    with torch.no_grad():
        embeddings = model(**inputs).last_hidden_state.mean(dim=1)
    # Ensure we return a 1-D array (flatten if needed)
    return embeddings.numpy().flatten()

# Directory containing the documents
directory_path = INGESTION_DIRECTORY

# text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=100)
text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=500)

# Iterate over all files in the directory
for filename in os.listdir(directory_path):
    if filename.endswith(".txt"):
        file_path = os.path.join(directory_path, filename)
        with open(file_path, "r") as file:            
            logger.info(file_path)
            content = file.read() 
            chunks = text_splitter.split_text(content)

            # Generate embedding for each text chunk and store in PostgreSQL
            for i, chunk in enumerate(chunks):
                embedding = get_embedding(chunk)
                cursor.execute(
                    f"INSERT INTO {RAG_TABLE} (content, source_file, chunk_index, embedding) VALUES (%s, %s, %s, %s::vector)",
                    (chunk, file_path, i, embedding.tolist())
                )
    
conn.commit()

# Close the connection
cursor.close()
conn.close()