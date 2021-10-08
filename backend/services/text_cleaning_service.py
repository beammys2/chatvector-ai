"""
Text cleaning and normalization for extracted document content.
Applied between extraction and chunking to improve embedding quality
and downstream RAG retrieval accuracy.

Isolated line breaks (typical PDF reflow artifacts) are collapsed to spaces.
Runs of blank lines are preserved as canonical paragraph breaks (``\\n\\n``).
"""

import logging
import re
import unicodedata

logger = logging.getLogger(__name__)

# Temporary marker while collapsing single line breaks; must not contain ``\\n``.
_PARAGRAPH_PLACEHOLDER = "\uE000PARA\uE001"


def clean_text(text: str) -> str:
    if not text:
        return text

    original_len = len(text)

    # 1. Unicode normalization (ligatures, fullwidth chars, NBSP → space, etc.)
    text = unicodedata.normalize("NFKC", text)
    # 2. Remove non-printable control chars; keep \t (0x09), \n (0x0A), \r (0x0D)
    text = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", text)
    # 3. Remove bullet point characters
    text = re.sub(r"[●•▪▸▹◦‣⁃◆◇■□▶▷]", "", text)
    # 4. Remove soft hyphens; rejoin hyphenated line breaks (PDF word-wrap artifact)
    text = text.replace("\u00ad", "")
    text = re.sub(r"-\n(\S)", r"\1", text)
    # 5. Normalize line endings, preserve paragraph breaks, collapse isolated breaks
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\n{2,}", _PARAGRAPH_PLACEHOLDER, text)
    text = text.replace("\n", " ")
    text = text.replace(_PARAGRAPH_PLACEHOLDER, "\n\n")
    # 6. Normalize horizontal whitespace without merging across paragraph breaks
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n\n *", "\n\n", text)

    text = text.strip()

    logger.debug("Text cleaning: %d → %d characters", original_len, len(text))
    return text
