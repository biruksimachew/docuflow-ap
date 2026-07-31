from app.services.extraction.models import (
    OCRPageInput,
)
from app.services.line_items.extractor import (
    extract_line_items,
)


def create_tokens(
    lines: tuple[str, ...],
) -> tuple[dict, ...]:
    tokens: list[dict] = []

    for line_number, line in enumerate(
        lines,
        start=1,
    ):
        left = 80

        for word_number, word in enumerate(
            line.split(),
            start=1,
        ):
            width = max(
                30,
                len(word) * 14,
            )

            tokens.append(
                {
                    "text": word,
                    "confidence": 0.98,
                    "left": left,
                    "top": (
                        60
                        + line_number * 70
                    ),
                    "width": width,
                    "height": 38,
                    "block_number": 1,
                    "paragraph_number": 1,
                    "line_number": (
                        line_number
                    ),
                    "word_number": (
                        word_number
                    ),
                }
            )

            left += width + 18

    return tuple(tokens)


def test_extracts_canonical_line_items() -> None:
    lines = (
        (
            "Description Qty "
            "Unit Price Line Total"
        ),
        "Printer Paper 2 50.00 100.00",
        "Blue Pens 1 20.00 20.00",
        "Subtotal: 120.00",
    )

    page = OCRPageInput(
        page_number=1,
        raw_text="\n".join(lines),
        average_confidence=0.98,
        tokens=create_tokens(lines),
    )

    result = extract_line_items(
        pages=(page,),
        header_currency="USD",
    )

    assert result.item_count == 2
    assert result.average_confidence is not None
    assert result.average_confidence > 0.90

    first = result.items[0]
    second = result.items[1]

    assert first.line_number == 1
    assert first.description == "Printer Paper"
    assert str(first.quantity) == "2"
    assert str(first.unit_price) == "50.00"
    assert str(first.line_total) == "100.00"
    assert first.currency == "USD"

    assert second.line_number == 2
    assert second.description == "Blue Pens"
    assert str(second.quantity) == "1"
    assert str(second.unit_price) == "20.00"
    assert str(second.line_total) == "20.00"

    assert first.row_evidence[
        "bounding_box"
    ]

    assert first.row_evidence[
        "tokens"
    ]

    assert (
        first.field_evidence[
            "quantity"
        ]["normalized_value"]
        == "2"
    )

    assert (
        first.field_evidence[
            "line_total"
        ]["normalized_value"]
        == "100.00"
    )