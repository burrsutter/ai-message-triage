import json
import logging
from dataclasses import dataclass
from pathlib import Path

from kafka import KafkaProducer

from models import OuterWrapper


logger = logging.getLogger(__name__)


class KafkaHandler:
    """Publish intake envelopes to Kafka."""

    def __init__(self, bootstrap_servers: str, topic: str):
        if not topic:
            raise ValueError("KAFKA_INTAKE_TOPIC is required")

        self.topic = topic
        self.producer = KafkaProducer(
            bootstrap_servers=bootstrap_servers,
            value_serializer=lambda value: json.dumps(value, default=str).encode("utf-8"),
        )
        logger.info("Kafka producer initialized successfully")

    def send_message(self, message: OuterWrapper) -> bool:
        """Send a message and wait until Kafka acknowledges it."""
        try:
            self.producer.send(self.topic, message.model_dump()).get(timeout=10)
            logger.info("Message sent to %s", self.topic)
            return True
        except Exception:
            logger.exception("Failed to send message to Kafka")
            return False

    def close(self) -> None:
        self.producer.close(timeout=10)


@dataclass(frozen=True)
class ProcessedFile:
    message: OuterWrapper
    done_path: Path


class FileProcessor:
    """Turn a local file into an intake message and preserve it as a .done file."""

    def __init__(self, kafka_handler: KafkaHandler):
        self.kafka_handler = kafka_handler

    def process_file(self, file_path: Path) -> ProcessedFile | None:
        if file_path.suffix == ".done" or "done" in file_path.parts:
            return None

        try:
            logger.info("Processing file: %s", file_path)
            done_dir = file_path.parent / "done"
            done_path = done_dir / f"{file_path.name}.done"
            if done_path.exists():
                logger.error("Done file already exists: %s", done_path)
                return None

            content = file_path.read_text(encoding="utf-8")
            stat = file_path.stat()
            message = OuterWrapper(
                id=str(stat.st_ino),
                filename=file_path.name,
                content=content,
                metadata={
                    "original_path": str(file_path),
                    "size_bytes": stat.st_size,
                    "created_timestamp": stat.st_ctime,
                    "modified_timestamp": stat.st_mtime,
                },
            )

            if not self.kafka_handler.send_message(message):
                logger.error("Failed to send file contents to Kafka: %s", file_path)
                return None

            done_dir.mkdir(exist_ok=True)
            file_path.rename(done_path)
            logger.info("Moved and renamed processed file to: %s", done_path)
            return ProcessedFile(message=message, done_path=done_path)
        except Exception:
            logger.exception("Error processing file %s", file_path)
            return None
