from __future__ import annotations

from pathlib import Path

from PIL import (
    Image,
    ImageDraw,
    ImageFont,
)


def _load_font(
    size: int,
):
    candidates = (
        (
            "/usr/share/fonts/truetype/"
            "dejavu/DejaVuSansMono.ttf"
        ),
        (
            "/usr/share/fonts/truetype/"
            "dejavu/DejaVuSans.ttf"
        ),
        "DejaVuSansMono.ttf",
        "DejaVuSans.ttf",
    )

    for candidate in candidates:
        try:
            return ImageFont.truetype(
                str(
                    Path(candidate)
                ),
                size=size,
            )
        except OSError:
            continue

    return ImageFont.load_default()


def create_line_item_invoice_image():
    image = Image.new(
        "RGB",
        (
            1800,
            1300,
        ),
        "white",
    )

    draw = ImageDraw.Draw(
        image
    )

    title_font = _load_font(
        56
    )

    body_font = _load_font(
        38
    )

    lines = (
        (
            "INVOICE",
            title_font,
        ),
        (
            "Meridian Office Supplies",
            body_font,
        ),
        (
            "Invoice Number: INV-2001",
            body_font,
        ),
        (
            "Invoice Date: 2026-07-30",
            body_font,
        ),
        (
            "Currency: USD",
            body_font,
        ),
        (
            (
                "Description             Qty  "
                "Unit Price  Line Total"
            ),
            body_font,
        ),
        (
            (
                "Printer Paper           2    "
                "50.00       100.00"
            ),
            body_font,
        ),
        (
            (
                "Blue Pens               1    "
                "20.00       20.00"
            ),
            body_font,
        ),
        (
            "Subtotal: 120.00",
            body_font,
        ),
        (
            "Tax: 18.00",
            body_font,
        ),
        (
            "Total: 138.00 USD",
            body_font,
        ),
    )

    y = 65

    for text, font in lines:
        draw.text(
            (
                70,
                y,
            ),
            text,
            font=font,
            fill="black",
        )

        y += 95

    return image