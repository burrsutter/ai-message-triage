import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import dotenv
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from starlette.datastructures import UploadFile

from intake.processor import FileProcessor, KafkaHandler


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)
logging.getLogger("kafka").setLevel(logging.WARNING)
logging.getLogger("kafka.conn").setLevel(logging.WARNING)

dotenv.load_dotenv()


class JsonIntake(BaseModel):
    filename: str
    content: str


def _safe_filename(filename: str) -> str:
    if not filename or filename in {".", ".."}:
        raise HTTPException(status_code=400, detail="A filename is required")
    if Path(filename).name != filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="The filename must not contain a path")
    if "\x00" in filename or len(filename.encode("utf-8")) > 240:
        raise HTTPException(status_code=400, detail="The filename is invalid or too long")
    if filename.endswith(".done"):
        raise HTTPException(status_code=400, detail="The filename must not end in .done")
    return filename


def create_app(
    kafka_handler: Any | None = None,
    watch_directory: Path | None = None,
) -> FastAPI:
    directory = watch_directory or Path(os.getenv("WATCH_DIRECTORY", "/data/intake"))
    max_bytes = int(os.getenv("HTTP_INTAKE_MAX_BYTES", str(1024 * 1024)))

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "done").mkdir(exist_ok=True)
        handler = kafka_handler or KafkaHandler(
            os.getenv("KAFKA_BROKER", "localhost:9092"),
            os.getenv("KAFKA_INTAKE_TOPIC", "intake"),
        )
        app.state.kafka_handler = handler
        app.state.processor = FileProcessor(handler)
        logger.info("HTTP intake directory: %s", directory)
        try:
            yield
        finally:
            if kafka_handler is None:
                handler.close()

    app = FastAPI(title="Message Triage HTTP Intake", lifespan=lifespan)

    @app.get("/healthz")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readyz")
    async def ready(request: Request) -> dict[str, str]:
        if not hasattr(request.app.state, "processor"):
            raise HTTPException(status_code=503, detail="Intake processor is not ready")
        return {"status": "ready"}

    @app.post("/intake", status_code=201)
    async def intake(request: Request, filename: str | None = None) -> dict[str, Any]:
        content_type = request.headers.get("content-type", "").lower()
        supplied_filename = filename or request.headers.get("x-filename")

        if content_type.startswith("multipart/form-data"):
            form = await request.form()
            upload = form.get("file")
            if not isinstance(upload, UploadFile):
                raise HTTPException(status_code=400, detail="Multipart requests require a 'file' field")
            supplied_filename = supplied_filename or upload.filename
            body = await upload.read(max_bytes + 1)
        elif content_type.startswith("application/json"):
            try:
                payload = JsonIntake.model_validate(await request.json())
            except Exception as exc:
                raise HTTPException(status_code=400, detail="JSON requires string fields 'filename' and 'content'") from exc
            supplied_filename = supplied_filename or payload.filename
            body = payload.content.encode("utf-8")
        else:
            body = await request.body()

        if len(body) > max_bytes:
            raise HTTPException(status_code=413, detail=f"Message exceeds the {max_bytes}-byte limit")
        try:
            body.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise HTTPException(status_code=415, detail="Intake content must be UTF-8 text") from exc

        safe_filename = _safe_filename(supplied_filename or "")
        incoming_path = directory / safe_filename
        done_path = directory / "done" / f"{safe_filename}.done"
        if incoming_path.exists() or done_path.exists():
            raise HTTPException(status_code=409, detail=f"'{safe_filename}' already exists")

        try:
            with incoming_path.open("xb") as incoming:
                incoming.write(body)
        except FileExistsError as exc:
            raise HTTPException(status_code=409, detail=f"'{safe_filename}' already exists") from exc
        except OSError as exc:
            logger.exception("Could not persist HTTP intake file")
            raise HTTPException(status_code=500, detail="Could not persist intake file") from exc

        result = request.app.state.processor.process_file(incoming_path)
        if result is None:
            raise HTTPException(
                status_code=503,
                detail="The message was saved but intake did not complete; inspect the incoming file before retrying",
            )

        return {
            "status": "accepted",
            "id": result.message.id,
            "filename": result.message.filename,
            "topic": request.app.state.kafka_handler.topic,
            "done_file": str(result.done_path),
        }

    return app


app = create_app()
