from PIL import (
    Image,
    ImageDraw,
    ImageFont,
)


FONT_PATH = (
    "/usr/share/fonts/truetype/dejavu/"
    "DejaVuSans.ttf"
)

BOLD_FONT_PATH = (
    "/usr/share/fonts/truetype/dejavu/"
    "DejaVuSans-Bold.ttf"
)


def create_test_invoice_image() -> Image.Image:
    image = Image.new(
        "RGB",
        (1600, 1000),
        "white",
    )

    draw = ImageDraw.Draw(image)

    title_font = ImageFont.truetype(
        BOLD_FONT_PATH,
        74,
    )

    heading_font = ImageFont.truetype(
        BOLD_FONT_PATH,
        38,
    )

    body_font = ImageFont.truetype(
        FONT_PATH,
        34,
    )

    draw.text(
        (100, 70),
        "INVOICE",
        font=title_font,
        fill="black",
    )

    draw.text(
        (100, 190),
        "Meridian Office Supplies",
        font=heading_font,
        fill="black",
    )

    draw.text(
        (100, 280),
        "Invoice Number: INV-1001",
        font=body_font,
        fill="black",
    )

    draw.text(
        (100, 345),
        "Invoice Date: 2026-07-30",
        font=body_font,
        fill="black",
    )

    draw.text(
        (100, 410),
        "Currency: USD",
        font=body_font,
        fill="black",
    )

    draw.text(
        (100, 525),
        "Laptop Stand    Quantity 2    Unit Price 45.00",
        font=body_font,
        fill="black",
    )

    draw.text(
        (100, 590),
        "USB Keyboard    Quantity 1    Unit Price 30.00",
        font=body_font,
        fill="black",
    )

    draw.text(
        (100, 720),
        "Subtotal: 120.00",
        font=body_font,
        fill="black",
    )

    draw.text(
        (100, 785),
        "Tax: 18.00",
        font=body_font,
        fill="black",
    )

    draw.text(
        (100, 850),
        "Total: 138.00 USD",
        font=heading_font,
        fill="black",
    )

    return image