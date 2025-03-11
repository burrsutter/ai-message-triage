import dotenv
from models import OuterWrapper
from kafka import KafkaProducer
import logging
import os
import sys
import json
import time
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Set up logging configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)
logging.getLogger("kafka").setLevel(logging.WARNING)
logging.getLogger("kafka.conn").setLevel(logging.WARNING)

# Load environment variables
dotenv.load_dotenv()

# Get configuration from environment variables
WATCH_DIRECTORY = os.getenv("WATCH_DIRECTORY")
KAFKA_BROKER = os.getenv("KAFKA_BROKER", "localhost:9092")
KAFKA_INTAKE_TOPIC = os.getenv("KAFKA_INTAKE_TOPIC")

# Validate required environment variables
if not WATCH_DIRECTORY:
    logger.error("WATCH_DIRECTORY environment variable is required")
    sys.exit(1)

# Ensure the watch directory exists
watch_dir = Path(WATCH_DIRECTORY)
if not watch_dir.exists():
    logger.error(f"Watch directory does not exist: {WATCH_DIRECTORY}")
    sys.exit(1)

logger.info(f"Watching directory: {WATCH_DIRECTORY}")
logger.info(f"Kafka bootstrap servers: {KAFKA_BROKER}")
logger.info(f"Kafka topic: {KAFKA_INTAKE_TOPIC}")


class KafkaHandler:
    """Handler for Kafka operations."""
    
    def __init__(self, bootstrap_servers: str, topic: str):
        """Initialize the Kafka handler."""
        self.topic = topic
        try:
            self.producer = KafkaProducer(
                bootstrap_servers=bootstrap_servers,
                value_serializer=lambda v: json.dumps(v, default=str).encode('utf-8')
            )
            logger.info("Kafka producer initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Kafka producer: {e}")
            raise


    def send_message(self, message: OuterWrapper):
        """Send a message to the Kafka topic."""
        try:
            self.producer.send(self.topic, message.model_dump())
            # Wait for the message to be delivered
            self.producer.flush()
            logger.info(f"Message sent to {self.topic}")
            return True
        except Exception as e:
            logger.error(f"Failed to send message to Kafka: {e}")
            return False

class FileProcessor:
    """Processor for handling files."""
    
    def __init__(self, kafka_handler: KafkaHandler):
        """Initialize the file processor."""
        self.kafka_handler = kafka_handler

    def process_file(self, file_path: Path) -> bool:
        """
        Process a file by reading its contents, wrapping it in a Pydantic model,
        and sending it to Kafka.
        
        Args:
            file_path: Path to the file to process
            
        Returns:
            bool: True if processing was successful, False otherwise
        """
        try:
            # Skip files that have already been processed
            if file_path.suffix == ".done":
                return False
                
            logger.info(f"Processing file: {file_path}")
            
            # Read file contents
            with open(file_path, 'r') as f:
                content = f.read()
            
            # Create Pydantic model with a unique ID
            file_content = OuterWrapper(
                id=str(file_path.stat().st_ino),  # Using inode number as unique ID
                filename=file_path.name,
                content=content,
                metadata={
                    "original_path": str(file_path),
                    "size_bytes": file_path.stat().st_size,
                    "created_timestamp": file_path.stat().st_ctime,
                    "modified_timestamp": file_path.stat().st_mtime
                }
            )
            
            # Serialize and send to Kafka
            success = self.kafka_handler.send_message(file_content)
            
            if success:
                # Create a "done" subdirectory if it doesn't exist
                done_dir = file_path.parent / "done"
                done_dir.mkdir(exist_ok=True)
                
                # Rename the file by changing its suffix to ".done" and move it to the "done" subdirectory
                new_filename = file_path.name + ".done"
                new_path = done_dir / new_filename
                file_path.rename(new_path)
                logger.info(f"Moved and renamed processed file to: {new_path}")
                return True
            else:
                logger.error(f"Failed to send file contents to Kafka: {file_path}")
                return False
                
        except Exception as e:
            logger.error(f"Error processing file {file_path}: {e}")
            return False


class FileEventHandler(FileSystemEventHandler):
    """Handler for file system events."""
    
    def __init__(self, file_processor: FileProcessor):
        """Initialize the file event handler."""
        self.file_processor = file_processor
        
    def on_created(self, event):
        """Handle file creation events."""
        if not event.is_directory:
            file_path = Path(event.src_path)
            # Skip files that have already been processed or are in the done directory
            if file_path.suffix != ".done" and "done" not in file_path.parts:
                self.file_processor.process_file(file_path)
    
    def process_existing_files(self, directory: Path):
        """Process existing files in the directory."""
        for file_path in directory.iterdir():
            # Skip files that have already been processed or are in the done directory
            if (file_path.is_file() and 
                file_path.suffix != ".done" and 
                file_path.name != "done" and  # Skip the done directory itself
                "done" not in file_path.parts):  # Skip files in the done directory
                self.file_processor.process_file(file_path)


def main():
    """Main function to run the application."""
    try:
        # Initialize Kafka handler
        kafka_handler = KafkaHandler(KAFKA_BROKER, KAFKA_INTAKE_TOPIC)
        
        # Initialize file processor
        file_processor = FileProcessor(kafka_handler)
        
        # Initialize event handler
        event_handler = FileEventHandler(file_processor)
        
        # Process existing files
        logger.info("Processing existing files in the watch directory")
        event_handler.process_existing_files(watch_dir)
        
        # Set up observer
        observer = Observer()
        observer.schedule(event_handler, str(watch_dir), recursive=False)
        observer.start()
        logger.info(f"Started watching directory: {WATCH_DIRECTORY}")
        
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            observer.stop()
            logger.info("Observer stopped")
        
        observer.join()
        
    except Exception as e:
        logger.error(f"Error in main function: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
