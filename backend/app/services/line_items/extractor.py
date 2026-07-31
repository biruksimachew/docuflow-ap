from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from statistics import mean
from typing import Any

from app.services.extraction.models import OCRPageInput
from app.services.line_items.models import (
    LineItemCandidate,
    LineItemExtractionResult,
)


@dataclass(frozen=True)
class ReconstructedLine:
    """One OCR line reconstructed from positioned tokens."""

    page_number: int
    text: str
    confidence: float

    tokens: tuple[dict[str, Any], ...]
    bounding_box: dict[str, int] | None


LINE_ITEM_PATTERN = re.compile(
    r"""
    ^\s*
    (?P<description>.+?)
    \s+
    (?P<quantity>
        -?\d+(?:\.\d+)?
    )
    \s+
    (?P<unit_price>
        [$€£]?
        \(?-?\d[\d,]*(?:\.\d+)?\)?
    )
    \s+
    (?P<line_total>
        [$€£]?
        \(?-?\d[\d,]*(?:\.\d+)?\)?
    )
    (?:\s+(?P<currency>[A-Z]{3}))?
    \s*$
    """,
    re.IGNORECASE | re.VERBOSE,
)

TABLE_HEADER_PATTERN = re.compile(
    r"\b(description|item|product)\b.*"
    r"\b(qty|quantity)\b.*"
    r"\b(unit\s*price|price)\b.*"
    r"\b(line\s*total|amount|total)\b",
    re.IGNORECASE,
)

STOP_LINE_PATTERN = re.compile(
    r"^\s*(subtotal|discount|shipping|freight|tax|"
    r"total|amount\s+due|balance\s+due)\b",
    re.IGNORECASE,
)

NON_ITEM_PATTERN = re.compile(
    r"^\s*(invoice|invoice\s+number|invoice\s+date|"
    r"due\s+date|currency|purchase\s+order|po\s+number|"
    r"bill\s+to|ship\s+to|vendor|supplier)\b",
    re.IGNORECASE,
)


def extract_line_items(
    *,
    pages: tuple[OCRPageInput, ...],
    header_currency: str | None,
) -> LineItemExtractionResult:
    """Extract canonical line rows from persisted OCR evidence."""

    lines = _reconstruct_lines(
        pages
    )

    candidates: list[LineItemCandidate] = []

    table_header_seen = False

    for line in lines:
        text = re.sub(
            r"\s+",
            " ",
            line.text,
        ).strip()

        if not text:
            continue

        if TABLE_HEADER_PATTERN.search(text):
            table_header_seen = True
            continue

        if STOP_LINE_PATTERN.search(text):
            if table_header_seen:
                break

            continue

        if NON_ITEM_PATTERN.search(text):
            continue

        match = LINE_ITEM_PATTERN.fullmatch(
            text
        )

        if match is None:
            continue

        description = _normalize_description(
            match.group("description")
        )

        if not _valid_description(description):
            continue

        raw_quantity = match.group(
            "quantity"
        )

        raw_unit_price = match.group(
            "unit_price"
        )

        raw_line_total = match.group(
            "line_total"
        )

        quantity = _normalize_decimal(
            raw_quantity
        )

        unit_price = _normalize_decimal(
            raw_unit_price
        )

        line_total = _normalize_decimal(
            raw_line_total
        )

        if (
            quantity is None
            or unit_price is None
            or line_total is None
        ):
            continue

        detected_currency = (
            _normalize_currency(
                match.group("currency")
            )
            or _currency_from_amount(
                raw_unit_price
            )
            or _currency_from_amount(
                raw_line_total
            )
            or _normalize_currency(
                header_currency
            )
        )

        confidence = round(
            max(
                0.0,
                min(
                    1.0,
                    line.confidence * 0.96,
                ),
            ),
            4,
        )

        normalized_values = {
            "description": description,
            "supplier_sku": None,
            "quantity": _decimal_plain(
                quantity
            ),
            "unit_of_measure": None,
            "unit_price": _money_text(
                unit_price
            ),
            "tax_rate": None,
            "line_total": _money_text(
                line_total
            ),
            "currency": detected_currency,
        }

        evidence_base = {
            "page_number": line.page_number,
            "line_text": text,
            "bounding_box": (
                line.bounding_box
            ),
            "tokens": [
                _token_evidence(token)
                for token in line.tokens
            ],
        }

        field_evidence = {
            "description": {
                **evidence_base,
                "raw_value": (
                    match.group("description")
                ),
                "normalized_value": (
                    description
                ),
                "confidence": confidence,
            },
            "quantity": {
                **evidence_base,
                "raw_value": raw_quantity,
                "normalized_value": (
                    _decimal_plain(quantity)
                ),
                "confidence": confidence,
            },
            "unit_price": {
                **evidence_base,
                "raw_value": raw_unit_price,
                "normalized_value": (
                    _money_text(unit_price)
                ),
                "confidence": confidence,
            },
            "line_total": {
                **evidence_base,
                "raw_value": raw_line_total,
                "normalized_value": (
                    _money_text(line_total)
                ),
                "confidence": confidence,
            },
        }

        candidates.append(
            LineItemCandidate(
                line_number=len(
                    candidates
                ) + 1,
                description=description,
                supplier_sku=None,
                quantity=quantity,
                unit_of_measure=None,
                unit_price=unit_price,
                tax_rate=None,
                line_total=line_total,
                currency=detected_currency,
                confidence=confidence,
                confidence_source=(
                    "derived_from_ocr_row_tokens"
                ),
                extraction_method=(
                    "tabular_numeric_tail_v1"
                ),
                page_number=line.page_number,
                raw_row_text=text,
                normalized_values=(
                    normalized_values
                ),
                field_evidence=(
                    field_evidence
                ),
                row_evidence=evidence_base,
            )
        )

    average_confidence = None

    if candidates:
        average_confidence = round(
            mean(
                candidate.confidence
                for candidate in candidates
            ),
            4,
        )

    return LineItemExtractionResult(
        items=tuple(candidates),
        average_confidence=(
            average_confidence
        ),
    )


def _reconstruct_lines(
    pages: tuple[OCRPageInput, ...],
) -> tuple[ReconstructedLine, ...]:
    lines: list[ReconstructedLine] = []

    for page in pages:
        grouped_tokens: dict[
            tuple[int, int, int],
            list[dict[str, Any]],
        ] = defaultdict(list)

        for token_index, token in enumerate(
            page.tokens
        ):
            token_text = str(
                token.get("text", "")
            ).strip()

            if not token_text:
                continue

            group_key = (
                int(
                    token.get(
                        "block_number",
                        0,
                    )
                ),
                int(
                    token.get(
                        "paragraph_number",
                        0,
                    )
                ),
                int(
                    token.get(
                        "line_number",
                        token_index + 1,
                    )
                ),
            )

            grouped_tokens[
                group_key
            ].append(token)

        if grouped_tokens:
            sorted_groups = sorted(
                grouped_tokens.values(),
                key=lambda group: (
                    min(
                        int(
                            token.get(
                                "top",
                                0,
                            )
                        )
                        for token in group
                    ),
                    min(
                        int(
                            token.get(
                                "left",
                                0,
                            )
                        )
                        for token in group
                    ),
                ),
            )

            for group in sorted_groups:
                ordered_tokens = tuple(
                    sorted(
                        group,
                        key=lambda token: (
                            int(
                                token.get(
                                    "left",
                                    0,
                                )
                            ),
                            int(
                                token.get(
                                    "word_number",
                                    0,
                                )
                            ),
                        ),
                    )
                )

                text = " ".join(
                    str(
                        token.get(
                            "text",
                            "",
                        )
                    ).strip()
                    for token in ordered_tokens
                    if str(
                        token.get(
                            "text",
                            "",
                        )
                    ).strip()
                )

                confidence_values = [
                    float(
                        token.get(
                            "confidence",
                            0,
                        )
                    )
                    for token in ordered_tokens
                    if token.get(
                        "confidence"
                    ) is not None
                ]

                confidence = (
                    mean(confidence_values)
                    if confidence_values
                    else (
                        page.average_confidence
                        if page.average_confidence
                        is not None
                        else 0.50
                    )
                )

                lines.append(
                    ReconstructedLine(
                        page_number=(
                            page.page_number
                        ),
                        text=text,
                        confidence=round(
                            max(
                                0.0,
                                min(
                                    1.0,
                                    confidence,
                                ),
                            ),
                            4,
                        ),
                        tokens=ordered_tokens,
                        bounding_box=(
                            _bounding_box(
                                ordered_tokens
                            )
                        ),
                    )
                )

            continue

        fallback_confidence = (
            page.average_confidence
            if page.average_confidence
            is not None
            else 0.50
        )

        for raw_line in (
            page.raw_text.splitlines()
        ):
            text = raw_line.strip()

            if text:
                lines.append(
                    ReconstructedLine(
                        page_number=(
                            page.page_number
                        ),
                        text=text,
                        confidence=round(
                            fallback_confidence,
                            4,
                        ),
                        tokens=(),
                        bounding_box=None,
                    )
                )

    return tuple(lines)


def _normalize_description(
    value: str,
) -> str:
    return re.sub(
        r"\s+",
        " ",
        value.strip(),
    )


def _valid_description(
    value: str,
) -> bool:
    if len(value) < 2:
        return False

    return any(
        character.isalpha()
        for character in value
    )


def _normalize_decimal(
    raw_value: str | None,
) -> Decimal | None:
    if raw_value is None:
        return None

    cleaned = raw_value.strip()

    negative_parentheses = (
        cleaned.startswith("(")
        and cleaned.endswith(")")
    )

    cleaned = (
        cleaned
        .replace("$", "")
        .replace("€", "")
        .replace("£", "")
        .replace(",", "")
        .replace("(", "")
        .replace(")", "")
        .strip()
    )

    try:
        value = Decimal(cleaned)
    except InvalidOperation:
        return None

    if negative_parentheses:
        value = -abs(value)

    return value


def _normalize_currency(
    value: str | None,
) -> str | None:
    if value is None:
        return None

    normalized = value.strip().upper()

    if re.fullmatch(
        r"[A-Z]{3}",
        normalized,
    ):
        return normalized

    symbol_map = {
        "$": "USD",
        "€": "EUR",
        "£": "GBP",
    }

    return symbol_map.get(
        normalized
    )


def _currency_from_amount(
    value: str,
) -> str | None:
    for symbol, currency in {
        "$": "USD",
        "€": "EUR",
        "£": "GBP",
    }.items():
        if symbol in value:
            return currency

    return None


def _decimal_plain(
    value: Decimal,
) -> str:
    text = format(
        value,
        "f",
    )

    if "." in text:
        text = text.rstrip("0").rstrip(
            "."
        )

    return text or "0"


def _money_text(
    value: Decimal,
) -> str:
    text = format(
        value,
        "f",
    )

    if "." not in text:
        return f"{text}.00"

    whole, fraction = text.split(
        ".",
        1,
    )

    fraction = fraction.rstrip(
        "0"
    )

    if len(fraction) < 2:
        fraction = fraction.ljust(
            2,
            "0",
        )

    return f"{whole}.{fraction}"


def _token_evidence(
    token: dict[str, Any],
) -> dict[str, Any]:
    return {
        "text": token.get("text"),
        "confidence": token.get(
            "confidence"
        ),
        "left": token.get("left"),
        "top": token.get("top"),
        "width": token.get("width"),
        "height": token.get(
            "height"
        ),
        "block_number": token.get(
            "block_number"
        ),
        "paragraph_number": token.get(
            "paragraph_number"
        ),
        "line_number": token.get(
            "line_number"
        ),
        "word_number": token.get(
            "word_number"
        ),
    }


def _bounding_box(
    tokens: tuple[dict[str, Any], ...],
) -> dict[str, int] | None:
    if not tokens:
        return None

    left = min(
        int(
            token.get(
                "left",
                0,
            )
        )
        for token in tokens
    )

    top = min(
        int(
            token.get(
                "top",
                0,
            )
        )
        for token in tokens
    )

    right = max(
        int(
            token.get(
                "left",
                0,
            )
        )
        + int(
            token.get(
                "width",
                0,
            )
        )
        for token in tokens
    )

    bottom = max(
        int(
            token.get(
                "top",
                0,
            )
        )
        + int(
            token.get(
                "height",
                0,
            )
        )
        for token in tokens
    )

    return {
        "left": left,
        "top": top,
        "right": right,
        "bottom": bottom,
        "width": max(
            0,
            right - left,
        ),
        "height": max(
            0,
            bottom - top,
        ),
    }