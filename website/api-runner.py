"""
Run script for the Password Reset API.
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
    host = os.getenv("WEBSITE_API_HOST")
    port = int(os.getenv("WEBSITE_API_PORT"))
    
    print(f"Starting Website API on {host}:{port}")
    
    # Start the API server
    uvicorn.run(
        "website-api:app",
        host=host,
        port=port,
        reload=True
    )

if __name__ == "__main__":
    main()
