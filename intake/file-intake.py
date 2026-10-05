import logging
import os
import sys
import time
from pathlib import Path

import dotenv
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from intake.processor import FileProcessor, KafkaHandler

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
        kafka_handler.close()
        
    except Exception as e:
        logger.error(f"Error in main function: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
