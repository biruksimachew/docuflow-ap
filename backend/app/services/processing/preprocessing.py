from __future__ import annotations

import io
from dataclasses import dataclass

import cv2
import fitz
import numpy as np
import pytesseract
from PIL import (
    Image,
    ImageFilter,
    ImageOps,
)
from pytesseract import Output, TesseractError


@dataclass(frozen=True)
class RenderedPage:
    page_number: int
    image: Image.Image


@dataclass(frozen=True)
class PreprocessedPage:
    image: Image.Image
    operations: tuple[dict[str, object], ...]


def image_to_png_bytes(image: Image.Image) -> bytes:
    buffer = io.BytesIO()

    image.save(
        buffer,
        format="PNG",
        optimize=True,
    )

    return buffer.getvalue()


def render_document_pages(
    *,
    content: bytes,
    media_type: str,
    pdf_render_dpi: int,
) -> tuple[RenderedPage, ...]:
    if media_type == "application/pdf":
        return _render_pdf_pages(
            content=content,
            dpi=pdf_render_dpi,
        )

    if media_type in {
        "image/jpeg",
        "image/png",
    }:
        with Image.open(io.BytesIO(content)) as source_image:
            loaded = source_image.copy()

        loaded = ImageOps.exif_transpose(loaded)
        loaded = loaded.convert("RGB")

        return (
            RenderedPage(
                page_number=1,
                image=loaded,
            ),
        )

    raise ValueError(
        f"Unsupported processing media type: {media_type}"
    )


def _render_pdf_pages(
    *,
    content: bytes,
    dpi: int,
) -> tuple[RenderedPage, ...]:
    document = fitz.open(
        stream=content,
        filetype="pdf",
    )

    pages: list[RenderedPage] = []

    try:
        scale = dpi / 72
        matrix = fitz.Matrix(scale, scale)

        for page_index in range(document.page_count):
            page = document.load_page(page_index)

            pixmap = page.get_pixmap(
                matrix=matrix,
                alpha=False,
            )

            image = Image.frombytes(
                "RGB",
                (pixmap.width, pixmap.height),
                pixmap.samples,
            )

            pages.append(
                RenderedPage(
                    page_number=page_index + 1,
                    image=image,
                )
            )
    finally:
        document.close()

    if not pages:
        raise ValueError(
            "The document did not produce any renderable pages."
        )

    return tuple(pages)


def preprocess_page(
    image: Image.Image,
) -> PreprocessedPage:
    operations: list[dict[str, object]] = []

    working = ImageOps.exif_transpose(
        image
    ).convert("RGB")

    rotation = _detect_quarter_turn_rotation(
        working
    )

    if rotation in {
        90,
        180,
        270,
    }:
        working = working.rotate(
            -rotation,
            expand=True,
            fillcolor="white",
        )

    operations.append(
        {
            "operation": "orientation_correction",
            "rotation_degrees_clockwise": rotation,
            "applied": rotation != 0,
        }
    )

    working = ImageOps.grayscale(working)

    operations.append(
        {
            "operation": "grayscale",
            "applied": True,
        }
    )

    working = ImageOps.autocontrast(
        working,
        cutoff=1,
    )

    operations.append(
        {
            "operation": "contrast_normalization",
            "cutoff_percent": 1,
            "applied": True,
        }
    )

    working = working.filter(
        ImageFilter.MedianFilter(size=3)
    )

    operations.append(
        {
            "operation": "median_denoise",
            "kernel_size": 3,
            "applied": True,
        }
    )

    working, correction_angle = _deskew(
        working
    )

    operations.append(
        {
            "operation": "deskew",
            "correction_degrees": round(
                correction_angle,
                4,
            ),
            "applied": abs(correction_angle) >= 0.15,
        }
    )

    return PreprocessedPage(
        image=working,
        operations=tuple(operations),
    )


def _detect_quarter_turn_rotation(
    image: Image.Image,
) -> int:
    try:
        result = pytesseract.image_to_osd(
            image,
            output_type=Output.DICT,
        )

        rotation = int(
            result.get("rotate", 0)
        )
    except (
        TesseractError,
        RuntimeError,
        TypeError,
        ValueError,
    ):
        return 0

    if rotation not in {
        0,
        90,
        180,
        270,
    }:
        return 0

    return rotation


def _deskew(
    image: Image.Image,
) -> tuple[Image.Image, float]:
    image_array = np.array(
        image,
        dtype=np.uint8,
    )

    thresholded = cv2.threshold(
        image_array,
        0,
        255,
        cv2.THRESH_BINARY_INV
        + cv2.THRESH_OTSU,
    )[1]

    coordinates = cv2.findNonZero(
        thresholded
    )

    if (
        coordinates is None
        or len(coordinates) < 20
    ):
        return image, 0.0

    raw_angle = float(
        cv2.minAreaRect(coordinates)[-1]
    )

    if raw_angle > 45:
        raw_angle -= 90

    correction_angle = -raw_angle

    if (
        abs(correction_angle) < 0.15
        or abs(correction_angle) > 10
    ):
        return image, 0.0

    height, width = image_array.shape[:2]

    center = (
        width / 2,
        height / 2,
    )

    rotation_matrix = cv2.getRotationMatrix2D(
        center,
        correction_angle,
        1.0,
    )

    rotated = cv2.warpAffine(
        image_array,
        rotation_matrix,
        (width, height),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=255,
    )

    return (
        Image.fromarray(rotated),
        correction_angle,
    )