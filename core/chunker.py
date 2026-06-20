"""Troceado de texto en fragmentos con solapamiento para la base vectorial."""
import re


def chunk_text(text: str, chunk_size: int = 900, overlap: int = 150) -> list[str]:
    text = (text or "").strip()
    if not text:
        return []

    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: list[str] = []
    current = ""

    for para in paragraphs:
        if len(para) > chunk_size:
            # Párrafo demasiado grande: lo cerramos y lo partimos en duro.
            if current:
                chunks.append(current)
                current = ""
            step = max(1, chunk_size - overlap)
            for i in range(0, len(para), step):
                chunks.append(para[i:i + chunk_size])
            continue

        if not current:
            current = para
        elif len(current) + len(para) + 1 <= chunk_size:
            current = current + "\n" + para
        else:
            chunks.append(current)
            tail = current[-overlap:] if overlap else ""
            current = (tail + "\n" + para).strip()

    if current:
        chunks.append(current)
    return chunks
