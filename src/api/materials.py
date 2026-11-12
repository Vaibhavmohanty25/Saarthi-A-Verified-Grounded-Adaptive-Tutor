"""Stage and extract uploads for the tutor API."""

import logging
import os
from hashlib import sha256
from pathlib import Path, PureWindowsPath
from uuid import uuid4

from fastapi import HTTPException, UploadFile

from src.ingestion.processing.chunker import chunk_text
from src.ingestion.schemas.content_unit import ContentUnit as IngestedUnit
from src.retrieval.schemas import ConceptNode, ContentUnit, Location, Topic

log = logging.getLogger(__name__)

VIDEO_EXTENSIONS = {".mp4", ".mov", ".webm", ".avi", ".mkv"}
AUDIO_EXTENSIONS = {".mp3", ".wav"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
SUPPORTED_EXTENSIONS = (
    VIDEO_EXTENSIONS | AUDIO_EXTENSIONS | IMAGE_EXTENSIONS | {".pdf", ".pptx", ".txt", ".md"}
)
PRESENTATION_TOPIC = Topic(topic_id="t-uploaded-presentations", name="Uploaded presentations")
NON_CONCEPT_TITLES = {"agenda", "contents", "introduction", "overview", "questions", "summary", "thank you", "title"}


def stage_upload(upload: UploadFile, directory: Path) -> tuple[Path, str]:
    original = PureWindowsPath(upload.filename or "").name
    suffix = Path(original).suffix.lower()
    if suffix == ".ppt":
        raise HTTPException(415, "Save the legacy .ppt file as a PowerPoint Presentation (.pptx), then upload the new file.")
    if suffix not in SUPPORTED_EXTENSIONS:
        raise HTTPException(415, "Unsupported course material format.")

    limit = int(os.getenv("SAARTHI_MAX_UPLOAD_BYTES", str(50 * 1024 * 1024)))
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{uuid4().hex}{suffix}"
    size = 0
    try:
        with target.open("xb") as output:
            while chunk := upload.file.read(1024 * 1024):
                size += len(chunk)
                if size > limit:
                    raise HTTPException(413, "Course material exceeds the upload size limit.")
                output.write(chunk)
        if not size:
            raise HTTPException(422, "Course material is empty.")
        validate_format(target)
    except Exception:
        target.unlink(missing_ok=True)
        raise
    return target, original


def validate_format(path: Path) -> None:
    """Reject extension mismatches before handing bytes to a parser."""
    from zipfile import BadZipFile, ZipFile

    suffix = path.suffix
    with path.open("rb") as stream:
        head = stream.read(1024)
    if suffix == ".pdf" and b"%PDF-" not in head:
        raise HTTPException(415, "The file does not contain a PDF header.")
    if suffix == ".pptx":
        try:
            with ZipFile(path) as archive:
                if "ppt/presentation.xml" not in archive.namelist():
                    raise HTTPException(415, "The archive does not contain a PowerPoint presentation.")
                if sum(item.file_size for item in archive.infolist()) > 250 * 1024 * 1024:
                    raise HTTPException(413, "The expanded presentation exceeds 250 MiB.")
        except BadZipFile as exc:
            raise HTTPException(415, "The file is not a valid PowerPoint archive.") from exc
    if suffix in {".txt", ".md"} and b"\x00" in head:
        raise HTTPException(415, "The file does not contain plain text.")
    if suffix in IMAGE_EXTENSIONS:
        from PIL import Image, UnidentifiedImageError

        expected = {".png": "PNG", ".jpg": "JPEG", ".jpeg": "JPEG", ".webp": "WEBP"}
        try:
            with Image.open(path) as image:
                if image.format != expected[suffix]:
                    raise HTTPException(415, "Image content does not match its extension.")
                image.verify()
        except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
            raise HTTPException(415, "Invalid or oversized image.") from exc


def to_retrieval_unit(unit: IngestedUnit, title: str) -> ContentUnit:
    anchor = unit.location
    figure = unit.unit_id if unit.visual_description else None
    if "timestamp" in anchor:
        timestamp = anchor["timestamp"]
        if isinstance(timestamp, dict):
            location = Location(t_start=timestamp["start"], t_end=timestamp.get("end"), figure_id=figure)
        else:
            location = Location(t_start=timestamp, figure_id=figure)
    elif "slide" in anchor:
        location = Location(slide=anchor["slide"], figure_id=figure)
    else:
        location = Location(page=anchor.get("page", 1), figure_id=figure)

    body = (unit.text or unit.visual_description or "").strip()
    return ContentUnit(
        unit_id=unit.unit_id,
        source_id=unit.source_id,
        source_type=location.kind,
        location=location,
        text=f"{location.label()} ({Path(title).stem}): {body}",
        slide_title=unit.slide_title,
        image_caption=unit.visual_description,
    )


def presentation_concepts(units: list[ContentUnit]) -> list[ConceptNode]:
    """Use slide headings as evidence-backed concepts in the shared demo graph."""
    concepts: dict[tuple[str, str], ConceptNode] = {}
    for unit in units:
        if unit.source_type != "slides" or not unit.slide_title:
            continue
        title = " ".join(unit.slide_title.split())
        normalized = title.casefold().strip(" .:!?")
        if not normalized or normalized in NON_CONCEPT_TITLES or len(title) > 120:
            continue
        key = (unit.source_id, normalized)
        if key not in concepts:
            digest = sha256(f"{unit.source_id}\0{normalized}".encode()).hexdigest()[:16]
            concepts[key] = ConceptNode(
                concept_id=f"ppt-{digest}", name=title, topic=PRESENTATION_TOPIC.topic_id,
            )
        concepts[key].evidence_units.append(unit.unit_id)
    return list(concepts.values())


def _optional_visual_units(extract):
    try:
        return extract()
    except Exception:
        log.warning("Visual extraction failed", exc_info=True)
        return []


def extract_units(path: Path, title: str) -> list[ContentUnit]:
    suffix = path.suffix.lower()
    vision_configured = any(os.getenv(key) for key in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "REPLICATE_API_KEY"))
    if suffix == ".pdf":
        from src.ingestion.ingestion.pdf_parser import extract_pdf_content

        units = extract_pdf_content(str(path))
        if vision_configured:
            from src.ingestion.ingestion.pdf_image_extractor import extract_images_from_pdf
            from src.ingestion.processing.visual_processor import create_visual_units

            units += _optional_visual_units(lambda: create_visual_units(extract_images_from_pdf(str(path))))
    elif suffix == ".pptx":
        from src.ingestion.ingestion.ppt_parser import extract_ppt_content

        units = extract_ppt_content(str(path))
        if vision_configured:
            from src.ingestion.ingestion.ppt_image_extractor import extract_images_from_ppt
            from src.ingestion.processing.ppt_visual_processor import create_ppt_visual_units

            units += _optional_visual_units(lambda: create_ppt_visual_units(extract_images_from_ppt(str(path))))
    elif suffix in VIDEO_EXTENSIONS | AUDIO_EXTENSIONS:
        from src.ingestion.ingestion.audio_extractor import extract_audio

        units = []
        try:
            from src.ingestion.ingestion.video_transcriber import transcribe_audio

            units = transcribe_audio(extract_audio(str(path)), path.name)
        except Exception:
            if suffix in AUDIO_EXTENSIONS or not vision_configured:
                raise
            log.warning("Audio extraction failed, attempting video keyframes", exc_info=True)
        if suffix in VIDEO_EXTENSIONS and vision_configured:
            from src.ingestion.ingestion.video_pipeline import create_video_visual_units

            units += _optional_visual_units(lambda: create_video_visual_units(str(path)))
    elif suffix in IMAGE_EXTENSIONS:
        from src.ingestion.vision.image_captioner import describe_educational_image

        caption = describe_educational_image(str(path))
        units = []
        if caption and caption.strip() != "NOT_EDUCATIONAL":
            units.append(IngestedUnit(
                unit_id=f"{path.stem}_img", source_id=path.name, source_type="diagram",
                location={"page": 1}, content_type="visual", text="", visual_description=caption,
            ))
    else:
        chunks = chunk_text(path.read_text(encoding="utf-8"))
        units = [
            IngestedUnit(
                unit_id=f"{path.stem}_c{index}", source_id=path.name, source_type="document",
                location={"page": index}, chunk_index=index, text=chunk,
            )
            for index, chunk in enumerate(chunks, start=1)
        ]
    return [to_retrieval_unit(unit, title) for unit in units if (unit.text or unit.visual_description or "").strip()]
