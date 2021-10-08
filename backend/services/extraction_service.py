import asyncio
import io
import logging
from dataclasses import dataclass

from fastapi import UploadFile
from pypdf import PdfReader

from services.text_cleaning_service import clean_text

logger = logging.getLogger(__name__)

# Separator between cleaned PDF pages in the assembled chunking string.
_PAGE_SEPARATOR = " "


def prepare_extracted_document_for_chunking(
    raw_text: str,
    page_boundaries: list["PageBoundary"],
) -> tuple[str, list["PageBoundary"]]:
    """
    Return cleaned document text and page boundaries in the same coordinate space.

    TXT inputs have no page boundaries and are cleaned as one string. PDF inputs
    are cleaned page-by-page, then joined so chunk offsets and page boundaries
    refer to the identical assembled normalized text.
    """
    if not page_boundaries:
        return clean_text(raw_text), []

    cleaned_parts: list[str] = []
    new_boundaries: list[PageBoundary] = []
    cursor = 0

    for boundary in page_boundaries:
        page_raw = raw_text[boundary.start_offset : boundary.end_offset]
        page_clean = clean_text(page_raw)
        if not page_clean:
            continue

        if cleaned_parts:
            cursor += len(_PAGE_SEPARATOR)

        start = cursor
        cleaned_parts.append(page_clean)
        cursor += len(page_clean)
        new_boundaries.append(
            PageBoundary(
                page_number=boundary.page_number,
                start_offset=start,
                end_offset=cursor,
            )
        )

    return _PAGE_SEPARATOR.join(cleaned_parts), new_boundaries


@dataclass
class PageBoundary:
    """Character offset range for a single PDF page within the cleaned document text."""

    page_number: int
    start_offset: int
    end_offset: int


def _extract_text_with_metadata_sync(
    content_type: str | None,
    filename: str,
    contents: bytes,
) -> tuple[str, list[PageBoundary]]:
    """
    Synchronous PDF/TXT parsing body.

    Raises ValueError for unsupported file types or unreadable payloads.
    """
    if content_type == "application/pdf":
        try:
            parts: list[str] = []
            page_boundaries: list[PageBoundary] = []
            cursor = 0
            reader = PdfReader(io.BytesIO(contents))

            for page_num, page in enumerate(reader.pages, start=1):
                text = page.extract_text() or ""
                page_text = text + "\n"
                start = cursor
                end = cursor + len(page_text)
                page_boundaries.append(
                    PageBoundary(page_number=page_num, start_offset=start, end_offset=end)
                )
                parts.append(page_text)
                cursor = end
                logger.debug(f"Extracted {len(text)} characters from page {page_num}")

            full_text = "".join(parts)
            logger.info(f"Total extracted text length: {len(full_text)}")
            return full_text, page_boundaries
        except Exception as e:
            logger.error(f"Failed to parse PDF file {filename}: {e}")
            raise ValueError("Failed to parse PDF content.")

    if content_type == "text/plain":
        try:
            file_text = contents.decode("utf-8")
        except UnicodeDecodeError:
            file_text = contents.decode("cp1254")  # Turkish Windows fallback
        logger.info(f"Extracted {len(file_text)} characters from TXT file")
        return file_text, []

    logger.error(f"Unsupported file type: {content_type}")
    raise ValueError(f"Unsupported file type: {content_type}")


async def extract_text_from_file(file: UploadFile, contents: bytes | None = None) -> str:
    """
    Extract text from a PDF or TXT UploadFile.
    Raises ValueError for unsupported file types or unreadable payloads.
    """
    text, _ = await extract_text_with_metadata(file, contents)
    return text


async def extract_text_with_metadata(
    file: UploadFile,
    contents: bytes | None = None,
) -> tuple[str, list[PageBoundary]]:
    """
    Extract text and per-page boundary information from a PDF or TXT UploadFile.

    Returns:
        (full_text, page_boundaries) where page_boundaries is populated for PDFs
        and empty for plain-text files.
    Raises ValueError for unsupported file types or unreadable payloads.
    """
    if contents is None:
        contents = await file.read()

    return await asyncio.to_thread(
        _extract_text_with_metadata_sync,
        file.content_type,
        file.filename or "",
        contents,
    )
