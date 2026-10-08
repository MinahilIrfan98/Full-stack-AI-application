import asyncio
import logging
from pathlib import PurePath

from docx import Document
from fastapi import APIRouter, File, HTTPException, Request, UploadFile, status
from pypdf import PdfReader

from app.schemas import UploadResponse
from app.services.file_memory import get_file_memory

router = APIRouter(prefix="/upload", tags=["upload"])
logger = logging.getLogger(__name__)

MAX_TEXT_LENGTH = 8000
SMALL_FILE_THRESHOLD = 4 * 1024 * 1024
SUPPORTED_TEXT_EXTENSIONS = {
    "txt", "md", "csv", "json", "py", "js", "jsx", "ts", "tsx", "html", "css",
    "sql", "sh", "yaml", "yml", "toml", "xml", "java", "c", "h", "cpp", "go",
    "rs", "ipynb",
}
SUPPORTED_EXTENSIONS = SUPPORTED_TEXT_EXTENSIONS | {"pdf", "docx"}


def extract_text_from_file(file_obj, filename: str) -> str:
    extension = PurePath(filename).suffix.lower().lstrip(".")
    if extension == "pdf":
        reader = PdfReader(file_obj)
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    if extension == "docx":
        doc = Document(file_obj)
        return "\n".join(para.text for para in doc.paragraphs)
    try:
        return file_obj.read().decode("utf-8")
    except UnicodeDecodeError:
        file_obj.seek(0)
        return file_obj.read().decode("latin-1")


@router.post("", response_model=UploadResponse)
async def upload_file(
    request: Request, file: UploadFile = File(...)
) -> UploadResponse:
    filename = file.filename or ""
    extension = PurePath(filename).suffix.lower().lstrip(".")
    if extension not in SUPPORTED_EXTENSIONS:
        supported = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            f"Unsupported file type. Supported extensions: {supported}.",
        )

    max_upload_mb = request.app.state.settings.max_upload_mb
    max_file_size = max_upload_mb * 1024 * 1024
    size = 0
    try:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > max_file_size:
                raise HTTPException(
                    status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    f"File is too large, max {max_upload_mb} MB",
                )
        await file.seek(0)

        text = await asyncio.to_thread(extract_text_from_file, file.file, filename)
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("Text extraction failed for %s: %s", filename, exc, exc_info=True)
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Could not extract text from this {extension.upper()} file. Verify that it is valid and not corrupted.",
        ) from exc

    if size <= SMALL_FILE_THRESHOLD:
        truncated = len(text) > MAX_TEXT_LENGTH
        return UploadResponse(
            filename=filename,
            text=text[:MAX_TEXT_LENGTH],
            truncated=truncated,
        )

    try:
        ollama_host = request.app.state.settings.ollama_host
        session_id = await get_file_memory(ollama_host).index(filename, text)
    except Exception as exc:
        logger.warning("Could not index uploaded file %s: %s", filename, exc, exc_info=True)
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            f"Could not prepare this large file for search: {exc}",
        ) from exc

    return UploadResponse(
        filename=filename,
        text="",
        truncated=False,
        session_id=session_id,
        retrieval=True,
    )
