"""Multimodal ingestion exports, loaded only when requested."""

from importlib import import_module

_MODULES = {
    "process_pdf": "ingestion.pdf_pipeline",
    "process_ppt": "ingestion.ppt_pipeline",
    "process_video": "ingestion.video_pipeline",
    "extract_pdf_content": "ingestion.pdf_parser",
    "extract_ppt_content": "ingestion.ppt_parser",
    "extract_images_from_pdf": "ingestion.pdf_image_extractor",
    "extract_images_from_ppt": "ingestion.ppt_image_extractor",
    "chunk_text": "processing.chunker",
}
__all__ = list(_MODULES)


def __getattr__(name):
    if name not in _MODULES:
        raise AttributeError(name)
    return getattr(import_module(f".{_MODULES[name]}", __name__), name)
