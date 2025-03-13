"""
Run script for the Finance API.
This script loads environment variables from .env file and starts the API server.
"""
import os
import uvicorn
from dotenv import load_dotenv

def main():
    """
    Load environment variables and start the API server.
    """
    # Load environment variables from .env file
    load_dotenv()
    
    # Get configuration from environment variables with defaults
    host = os.getenv("FINANCE_API_HOST")
    port = int(os.getenv("FINANCE_API_PORT"))
    
    print(f"Starting Finance API on {host}:{port}")
    
    # Start the API server
    uvicorn.run(
        "finance-api:app",
        host=host,
        port=port,
        reload=True
    )

if __name__ == "__main__":
    main()
