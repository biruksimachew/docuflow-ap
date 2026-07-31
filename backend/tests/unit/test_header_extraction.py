from app.services.extraction.header import (
    extract_header_fields,
)
from app.services.extraction.models import (
    OCRPageInput,
)


def create_line_tokens(
    *,
    text: str,
    line_number: int,
    top: int,
) -> list[dict]:
    tokens: list[dict] = []

    left = 100

    for word_number, word in enumerate(
        text.split(),
        start=1,
    ):
        width = max(
            25,
            len(word) * 14,
        )

        tokens.append(
            {
                "text": word,
                "confidence": 0.98,
                "left": left,
                "top": top,
                "width": width,
                "height": 38,
                "block_number": 1,
                "paragraph_number": 1,
                "line_number": line_number,
                "word_number": word_number,
            }
        )

        left += width + 14

    return tokens


def test_extracts_canonical_header_with_evidence() -> None:
    lines = (
        "INVOICE",
        "Meridian Office Supplies",
        "Invoice Number: INV-1001",
        "Invoice Date: 2026-07-30",
        "Currency: USD",
        "Subtotal: 120.00",
        "Tax: 18.00",
        "Total: 138.00 USD",
    )

    tokens: list[dict] = []

    for line_number, line in enumerate(
        lines,
        start=1,
    ):
        tokens.extend(
            create_line_tokens(
                text=line,
                line_number=line_number,
                top=70 + (line_number * 70),
            )
        )

    page = OCRPageInput(
        page_number=1,
        raw_text="\n".join(lines),
        average_confidence=0.98,
        tokens=tuple(tokens),
    )

    result = extract_header_fields(
        (page,)
    )

    assert (
        result.canonical_header["vendor_name"]
        == "Meridian Office Supplies"
    )

    assert (
        result.canonical_header["invoice_number"]
        == "INV-1001"
    )

    assert (
        result.canonical_header["invoice_date"]
        == "2026-07-30"
    )

    assert (
        result.canonical_header["currency"]
        == "USD"
    )

    assert (
        result.canonical_header["subtotal"]
        == "120.00"
    )

    assert (
        result.canonical_header["tax_amount"]
        == "18.00"
    )

    assert (
        result.canonical_header["total_amount"]
        == "138.00"
    )

    assert result.missing_required_fields == ()
    assert result.header_confidence > 0.90

    fields = {
        field.field_name: field
        for field in result.fields
    }

    total = fields["total_amount"]

    assert total.raw_value == "138.00 USD"
    assert total.normalized_value == "138.00"
    assert total.page_number == 1
    assert total.confidence > 0.90

    bounding_box = total.evidence[
        "bounding_box"
    ]

    assert bounding_box is not None
    assert bounding_box["width"] > 0
    assert bounding_box["height"] > 0
    assert total.evidence["tokens"]