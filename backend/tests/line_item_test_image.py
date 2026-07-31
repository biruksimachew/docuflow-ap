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


def create_line_item_invoice_image(
    *,
    invoice_number: str = "INV-2001",
    purchase_order_number: str | None = None,
    marker: str | None = None,
):
    image = Image.new(
        "RGB",
        (
            1800,
            1450,
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

    marker_font = _load_font(
        24
    )

    lines: list[tuple[str, object]] = [
        (
            "INVOICE",
            title_font,
        ),
        (
            "Meridian Office Supplies",
            body_font,
        ),
        (
            f"Invoice Number: {invoice_number}",
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
    ]

    if purchase_order_number:
        lines.append(
            (
                (
                    "PO Number: "
                    f"{purchase_order_number}"
                ),
                body_font,
            )
        )

    lines.extend(
        [
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
        ]
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

    if marker:
        draw.text(
            (
                70,
                1360,
            ),
            marker,
            font=marker_font,
            fill="black",
        )

    return image