import re
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from pptx import Presentation

from src.ingestion.schemas.content_unit import ContentUnit
from src.ingestion.processing.chunker import chunk_text


def _extract_ppt_fallback_zip(file_path: str) -> list[tuple[int, str, str | None]]:
    """Extract slides text using zipfile XML parsing when python-pptx fails."""
    slides = []
    try:
        with zipfile.ZipFile(file_path, "r") as z:
            slide_names = [n for n in z.namelist() if re.match(r"ppt/slides/slide\d+\.xml", n)]
            slide_names.sort(key=lambda s: int(re.search(r"\d+", s.split("/")[-1]).group()))
            for idx, name in enumerate(slide_names):
                xml_data = z.read(name)
                root = ET.fromstring(xml_data)
                texts = [elem.text for elem in root.iter() if elem.tag.endswith("}t") and elem.text and elem.text.strip()]
                full_text = " ".join(texts).strip()
                title = None
                for shape in root.findall(".//{*}sp"):
                    placeholder = shape.find("./{*}nvSpPr/{*}nvPr/{*}ph")
                    if placeholder is not None and placeholder.get("type") in {"title", "ctrTitle"}:
                        title = " ".join(element.text for element in shape.findall(".//{*}t") if element.text)
                        break
                if full_text:
                    slides.append((idx + 1, full_text, title))
    except Exception as e:
        print(f"[PPT Parser] Zip XML extraction failed: {e}")
    return slides


def extract_ppt_content(file_path: str) -> list[ContentUnit]:
    source_name = Path(file_path).name
    source_stem = Path(source_name).stem
    content_units = []
    slide_data: list[tuple[int, str, str | None]] = []

    try:
        presentation = Presentation(file_path)
        for slide_index, slide in enumerate(presentation.slides, start=1):
            text_shapes = [shape for shape in slide.shapes if shape.has_text_frame and shape.text.strip()]
            title_shape = slide.shapes.title
            title = title_shape.text.strip() if title_shape is not None else None
            if not title and len(text_shapes) > 1:
                first = min(text_shapes, key=lambda shape: (shape.top, shape.left)).text.strip()
                if "\n" not in first and len(first.split()) <= 12 and not first.endswith((".", "!", "?")):
                    title = first
            slide_text = "\n".join(shape.text.strip() for shape in text_shapes)
            if slide_text:
                slide_data.append((slide_index, slide_text, title))
    except Exception as exc:
        print(f"[PPT Parser] python-pptx raised '{exc}', falling back to direct XML extraction...")
        slide_data = _extract_ppt_fallback_zip(file_path)

    if not slide_data:
        slide_data = _extract_ppt_fallback_zip(file_path)

    for slide_index, slide_text, title in slide_data:
        chunks = chunk_text(slide_text)
        for chunk_index, chunk in enumerate(chunks, start=1):
            unit = ContentUnit(
                unit_id=f"{source_stem}_s{slide_index}_c{chunk_index}",
                source_id=source_name,
                source_type="slides",
                location={"slide": slide_index},
                chunk_index=chunk_index,
                content_type="text",
                text=chunk,
                slide_title=title,
                visual_description=None,
                image_path=None,
                topic=None,
                subtopic=None,
                concept_ids=[],
            )
            content_units.append(unit)

    return content_units
