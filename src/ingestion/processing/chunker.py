def chunk_text(
    text: str,
    chunk_size: int = 1200,
    overlap: int = 200
) -> list[str]:

    if not text or not text.strip():
        return []

    text = " ".join(text.split())

    chunks = []

    start = 0
    text_length = len(text)

    while start < text_length:
        end = start + chunk_size

        chunk = text[start:end]

        if end < text_length:
            last_period = chunk.rfind(".")
            last_newline = chunk.rfind("\n")

            split_position = max(last_period, last_newline)

            if split_position > chunk_size * 0.6:
                end = start + split_position + 1
                chunk = text[start:end]

        chunks.append(chunk.strip())
        if end >= text_length:
            break

        start = max(end - overlap, start + 1)

    return chunks
