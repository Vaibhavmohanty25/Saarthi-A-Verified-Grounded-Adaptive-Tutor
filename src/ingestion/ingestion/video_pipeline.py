from pathlib import Path

from src.ingestion.ingestion.keyframe_extractor import extract_keyframes

from src.ingestion.vision.image_captioner import describe_educational_image

from src.ingestion.schemas.content_unit import ContentUnit



def create_video_visual_units(
    video_path: str
) -> list[ContentUnit]:

    video_path = Path(
        video_path
    )

    source_name = (
        video_path.name
    )

    source_stem = (
        video_path.stem
    )

    # =====================================================
    # 1. EXTRACT KEYFRAMES
    # =====================================================

    frames = extract_keyframes(
        video_path=str(
            video_path
        ),
        max_frames=12,
        candidates_per_segment=3
    )


    print(
        f"[Video Pipeline] "
        f"Keyframes extracted: "
        f"{len(frames)}"
    )


    visual_units = []


    # =====================================================
    # 2. VISION ANALYSIS
    # =====================================================

    for index, frame in enumerate(
        frames,
        start=1
    ):

        timestamp = (
            frame[
                "timestamp"
            ]
        )

        image_path = (
            frame[
                "image_path"
            ]
        )


        print(
            f"[Video Vision] "
            f"{index}/{len(frames)} -> "
            f"{timestamp:.1f}s"
        )


        try:

            description = (
                describe_educational_image(
                    image_path
                )
            )


        except LLMUnavailableError as exc:

            print(
                f"[Video Vision] "
                f"Providers unavailable at "
                f"{timestamp:.1f}s: "
                f"{exc}"
            )

            continue


        except RateLimitError as exc:

            print(
                f"[Video Vision] "
                f"Rate limit at "
                f"{timestamp:.1f}s: "
                f"{exc}"
            )

            continue


        except Exception as exc:

            print(
                f"[Video Vision] "
                f"Failed at "
                f"{timestamp:.1f}s: "
                f"{type(exc).__name__}: "
                f"{exc}"
            )

            continue


        # =================================================
        # Ignore irrelevant frames
        # =================================================

        if not description:
            continue


        if (
            description
            .strip()
            .upper()
            ==
            "NOT_EDUCATIONAL"
        ):

            print(
                f"[Video Vision] "
                f"Skipped non-educational "
                f"frame @ "
                f"{timestamp:.1f}s"
            )

            continue


        timestamp_int = int(
            round(
                timestamp
            )
        )


        # =================================================
        # 3. CREATE VISUAL CONTENT UNIT
        # =================================================

        unit = ContentUnit(
            unit_id=(
                f"{source_stem}"
                f"_v{timestamp_int}"
            ),

            source_id=source_name,

            source_type="video",

            location={
                "timestamp": {
                    "start":
                        timestamp,

                    "end":
                        timestamp
                }
            },

            chunk_index=index,

            content_type="visual",

            text="",

            visual_description=(
                description
            ),

            image_path=image_path,

            topic=None,

            subtopic=None,

            concept_ids=[]
        )


        visual_units.append(
            unit
        )


        print(
            f"[Video Vision] "
            f"Educational visual saved @ "
            f"{timestamp:.1f}s"
        )


    print(
        f"[Video Pipeline] "
        f"Educational visual units: "
        f"{len(visual_units)}"
    )


    return visual_units


def process_video(
    file_path: str
) -> dict:
    from groq import RateLimitError

    from src.ingestion.ingestion.audio_extractor import extract_audio
    from src.ingestion.ingestion.video_transcriber import transcribe_audio
    from src.ingestion.knowledge.course_registry import course_concept_registry
    from src.ingestion.llm.text_llm import LLMUnavailableError
    from src.ingestion.processing.embedding_processor import embed_content_units
    from src.ingestion.processing.semantic_processor import enrich_content_units

    video_path = Path(
        file_path
    )


    print(
        f"[Video Pipeline] "
        f"Processing: "
        f"{video_path.name}"
    )


    # =====================================================
    # STEP 1 — AUDIO EXTRACTION
    # =====================================================

    audio_path = extract_audio(
        str(
            video_path
        )
    )


    print(
        f"[Video Pipeline] "
        f"Audio: "
        f"{audio_path}"
    )


    # =====================================================
    # STEP 2 — WHISPER TRANSCRIPTION
    # =====================================================

    text_units = transcribe_audio(
        audio_path=audio_path,

        original_video_name=(
            video_path.name
        )
    )


    print(
        f"[Video Pipeline] "
        f"Transcript units: "
        f"{len(text_units)}"
    )


    # =====================================================
    # STEP 3 — KEYFRAMES + VISION
    # =====================================================

    visual_units = (
        create_video_visual_units(
            str(
                video_path
            )
        )
    )


    # =====================================================
    # STEP 4 — COMBINE MODALITIES
    # =====================================================

    all_units = (
        text_units
        +
        visual_units
    )


    print(
        f"[Video Pipeline] "
        f"Combined multimodal units: "
        f"{len(all_units)}"
    )


    # =====================================================
    # STEP 5 — SEMANTIC ENRICHMENT
    #
    # IMPORTANT:
    # Do not destroy the upload if both LLM providers
    # temporarily become unavailable.
    # Existing checkpoints remain usable.
    # =====================================================

    semantic_status = (
        "completed"
    )

    semantic_error = None


    try:

        all_units = enrich_content_units(
            units=all_units,

            registry=(
                course_concept_registry
            )
        )


    except LLMUnavailableError as exc:

        semantic_status = (
            "deferred_llm_unavailable"
        )

        semantic_error = str(
            exc
        )


        print(
            "[Video Pipeline] "
            "Semantic enrichment deferred."
        )

        print(
            "[Video Pipeline] "
            "All completed semantic "
            "checkpoints were preserved."
        )


    except RateLimitError as exc:

        semantic_status = (
            "deferred_rate_limit"
        )

        semantic_error = str(
            exc
        )


        print(
            "[Video Pipeline] "
            "Semantic enrichment deferred "
            "because of provider rate limits."
        )

        print(
            "[Video Pipeline] "
            "All completed semantic "
            "checkpoints were preserved."
        )


    # =====================================================
    # STEP 6 — EMBEDDINGS
    #
    # Even partially semantically enriched units can
    # still be embedded and persisted.
    # =====================================================

    all_units = embed_content_units(
        all_units
    )


    print(
        "[Video Pipeline] "
        f"Semantic status: "
        f"{semantic_status}"
    )


    # =====================================================
    # RESULT
    # =====================================================

    return {
        "text_units": [
            unit
            for unit in all_units
            if (
                unit.content_type
                == "text"
            )
        ],

        "visual_units": [
            unit
            for unit in all_units
            if (
                unit.content_type
                == "visual"
            )
        ],

        "all_units":
            all_units,

        "semantic_status":
            semantic_status,

        "semantic_error":
            semantic_error
    }
