from openai import OpenAI
import psycopg2
from pgvector.psycopg2 import register_vector
from transformers import AutoTokenizer, AutoModel
import logging
import torch
from dotenv import load_dotenv
import os

# Set up logging configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


load_dotenv()

API_KEY=os.getenv("SUPPORT_API_KEY")
INFERENCE_SERVER_URL=os.getenv("SUPPORT_SERVER_URL")
MODEL_NAME=os.getenv("SUPPORT_MODEL_NAME")
DBNAME=os.getenv("KBASE_DBNAME")
DBUSER=os.getenv("KBASE_DBUSER")
DBPASSWORD=os.getenv("KBASE_DBPASSWORD")
DBHOST=os.getenv("KBASE_DBHOST")
DBPORT=os.getenv("KBASE_DBPORT")
RAG_TABLE=os.getenv("KBASE_RAG_TABLE")

logger.info(f"INFERENCE_SERVER_URL: {INFERENCE_SERVER_URL}")
logger.info(f"MODEL_NAME: {MODEL_NAME}")
logger.info(f"DBNAME: {DBNAME}")
logger.info(f"DBHOST: {DBHOST}")
logger.info(f"DBPORT: {DBPORT}")


client = OpenAI(
    api_key=API_KEY,
    base_url=INFERENCE_SERVER_URL
    )


# User query
query = "Where are the Tweedles standing?"

# Connect to PostgreSQL
conn = psycopg2.connect(
    dbname=DBNAME,
    user=DBUSER,
    password=DBPASSWORD,
    host=DBHOST,
    port=DBPORT
)

register_vector(conn)
cursor = conn.cursor()

# Load Sentence Transformer model (all-mpnet-base-v2)
os.environ["TOKENIZERS_PARALLELISM"] = "false"
tokenizer = AutoTokenizer.from_pretrained("sentence-transformers/all-mpnet-base-v2")
model = AutoModel.from_pretrained("sentence-transformers/all-mpnet-base-v2")


# Function to generate query embedding
def get_query_embedding(query):
    inputs = tokenizer(query, return_tensors="pt", truncation=True, padding=True)
    with torch.no_grad():
        embeddings = model(**inputs).last_hidden_state.mean(dim=1)
    # Ensure we return a 1-D array (flatten if needed)
    return embeddings.numpy().flatten()


# Function to retrieve relevant documents
def retrieve_documents(query, top_k=3):
    query_embedding = get_query_embedding(query)
    
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
    conn.close()

    return retrieved_docs

# --------------------------------------------------------------
#
# --------------------------------------------------------------

retrieved_docs = retrieve_documents(query)


# # Display retrieved chunks
# print("\n🔍 Top Retrieved Chunks:\n")
# for idx, doc in enumerate(retrieved_docs, 1):
#     print(f"Doc: {idx} ID: {doc['id']}")
#     print(f"Content: {doc['content']}")
#     print(f"Source: {doc['source_file']} (Chunk {doc['chunk_index']})")
#     print("-" * 50)

context = "\n\n".join([doc["content"] for doc in retrieved_docs])

# model context size might be 6144 tokens
def generate_response(query, context, max_context_length=4000):
    truncated_context = context[:max_context_length] if len(context) > max_context_length else context
    print("-" * 50)
    print(f"truncated_context: {truncated_context}")
    print("-" * 50)
    prompt = f"""You are an AI that answers questions using the given context.
If the context does not contain an answer, respond with \"I don't know\".

Context:
{truncated_context}

Question: {query}
Answer:"""
    
    response = client.chat.completions.create(
        model=MODEL_NAME,  
        messages=[{"role": "system", "content": "You are a helpful assistant answering questions based on the provided context."},
                  {"role": "user", "content": prompt}]
    )
    
    return response.choices[0].message.content.strip()


# Get LLM-generated response
llm_response = generate_response(query, context)
print("\n💡 AI Response:\n", llm_response)

