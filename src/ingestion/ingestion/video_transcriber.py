import os
from pathlib import Path

from dotenv import load_dotenv
from groq import Groq

from src.ingestion.schemas.content_unit import ContentUnit
from src.ingestion.processing.transcript_chunker import merge_transcript_segments


load_dotenv()

def transcribe_audio(
    audio_path: str,
    original_video_name: str
) -> list[ContentUnit]:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY was not found.")
    client = Groq(api_key=api_key, timeout=120, max_retries=1)

    source_name = original_video_name
    source_stem = Path(source_name).stem

    with open(audio_path, "rb") as file:
        transcription = client.audio.transcriptions.create(
            file=file,
            model="whisper-large-v3-turbo",
            response_format="verbose_json",
            timestamp_granularities=["segment"],
            temperature=0.0
        )

    raw_segments = transcription.segments or []

    merged_segments = merge_transcript_segments(
        raw_segments,
        target_duration=45.0
    )

    content_units = []

    for index, segment in enumerate(
        merged_segments,
        start=1
    ):
        start = segment["start"]
        end = segment["end"]
        text = segment["text"]

        unit = ContentUnit(
            unit_id=f"{source_stem}_t{int(start)}_{int(end)}",

            source_id=source_name,
            source_type="video",

            location={
                "timestamp": {
                    "start": start,
                    "end": end
                }
            },

            chunk_index=index,
            content_type="text",

            text=text,

            visual_description=None,
            image_path=None,

            topic=None,
            subtopic=None,
            concept_ids=[]
        )

        content_units.append(unit)

    return content_units
