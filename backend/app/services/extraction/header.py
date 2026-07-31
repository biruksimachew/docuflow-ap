from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime
from decimal import Decimal, InvalidOperation
from statistics import mean
from typing import Any

from app.services.extraction.models import (
    ExtractedFieldCandidate,
    HeaderExtractionResult,
    OCRLine,
    OCRPageInput,
)


REQUIRED_HEADER_FIELDS = (
    "vendor_name",
    "invoice_number",
    "invoice_date",
    "currency",
    "total_amount",
)

CANONICAL_HEADER_FIELDS = (
    "vendor_name",
    "invoice_number",
    "invoice_date",
    "due_date",
    "purchase_order_number",
    "currency",
    "subtotal",
    "discount_amount",
    "shipping_amount",
    "tax_amount",
    "total_amount",
)

CONFIDENCE_WEIGHTS = {
    "vendor_name": 0.18,
    "invoice_number": 0.18,
    "invoice_date": 0.14,
    "currency": 0.12,
    "total_amount": 0.18,
    "subtotal": 0.10,
    "tax_amount": 0.04,
    "due_date": 0.02,
    "purchase_order_number": 0.02,
    "discount_amount": 0.01,
    "shipping_amount": 0.01,
}

FIELD_LABEL_PATTERN = re.compile(
    r"""(?ix)
    \b(
        invoice\s*(number|no\.?|\#|date)
        |
        due\s*date
        |
        purchase\s*order
        |
        po\s*(number|no\.?|\#)?
        |
        currency
        |
        subtotal
        |
        discount
        |
        shipping
        |
        freight
        |
        tax
        |
        total
        |
        amount\s*due
        |
        balance\s*due
    )\b
    """
)

INVOICE_TITLE_PATTERN = re.compile(
    r"(?i)^\s*(?:tax\s+)?invoice\s*$"
)

DATE_PATTERNS = (
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%Y.%m.%d",
    "%m/%d/%Y",
    "%m-%d-%Y",
    "%d-%b-%Y",
    "%d %b %Y",
    "%b %d, %Y",
    "%B %d, %Y",
    "%d %B %Y",
)


def extract_header_fields(
    pages: tuple[OCRPageInput, ...],
) -> HeaderExtractionResult:
    """Extract canonical invoice header values from OCR evidence."""

    lines = _reconstruct_lines(pages)

    candidates: dict[str, ExtractedFieldCandidate] = {}

    for line in lines:
        _extract_invoice_number(
            line,
            candidates,
        )

        _extract_invoice_date(
            line,
            candidates,
        )

        _extract_due_date(
            line,
            candidates,
        )

        _extract_purchase_order_number(
            line,
            candidates,
        )

        _extract_currency(
            line,
            candidates,
        )

        _extract_amounts(
            line,
            candidates,
        )

    vendor_candidate = _extract_vendor_name(lines)

    if vendor_candidate is not None:
        _store_best_candidate(
            candidates,
            vendor_candidate,
        )

    if "currency" not in candidates:
        currency_candidate = _infer_currency_from_amount_lines(
            lines
        )

        if currency_candidate is not None:
            _store_best_candidate(
                candidates,
                currency_candidate,
            )

    canonical_header: dict[str, str | None] = {
        field_name: None
        for field_name in CANONICAL_HEADER_FIELDS
    }

    for field_name, candidate in candidates.items():
        canonical_header[field_name] = (
            candidate.normalized_value
        )

    missing_required_fields = tuple(
        field_name
        for field_name in REQUIRED_HEADER_FIELDS
        if not canonical_header[field_name]
    )

    header_confidence = _calculate_header_confidence(
        candidates
    )

    ordered_fields = tuple(
        candidates[field_name]
        for field_name in CANONICAL_HEADER_FIELDS
        if field_name in candidates
    )

    return HeaderExtractionResult(
        fields=ordered_fields,
        canonical_header=canonical_header,
        header_confidence=header_confidence,
        missing_required_fields=missing_required_fields,
    )


def _reconstruct_lines(
    pages: tuple[OCRPageInput, ...],
) -> tuple[OCRLine, ...]:
    lines: list[OCRLine] = []

    for page in pages:
        grouped_tokens: dict[
            tuple[int, int, int],
            list[dict[str, Any]],
        ] = defaultdict(list)

        for token_index, token in enumerate(page.tokens):
            token_text = str(
                token.get("text", "")
            ).strip()

            if not token_text:
                continue

            key = (
                int(token.get("block_number", 0)),
                int(token.get("paragraph_number", 0)),
                int(
                    token.get(
                        "line_number",
                        token_index + 1,
                    )
                ),
            )

            grouped_tokens[key].append(token)

        if grouped_tokens:
            sorted_groups = sorted(
                grouped_tokens.items(),
                key=lambda item: (
                    min(
                        int(token.get("top", 0))
                        for token in item[1]
                    ),
                    min(
                        int(token.get("left", 0))
                        for token in item[1]
                    ),
                ),
            )

            for _, group_tokens in sorted_groups:
                ordered_tokens = tuple(
                    sorted(
                        group_tokens,
                        key=lambda token: (
                            int(token.get("left", 0)),
                            int(
                                token.get(
                                    "word_number",
                                    0,
                                )
                            ),
                        ),
                    )
                )

                line_text = " ".join(
                    str(token.get("text", "")).strip()
                    for token in ordered_tokens
                    if str(
                        token.get("text", "")
                    ).strip()
                )

                if not line_text:
                    continue

                confidence_values = [
                    float(token.get("confidence", 0))
                    for token in ordered_tokens
                    if token.get("confidence") is not None
                ]

                line_confidence = (
                    mean(confidence_values)
                    if confidence_values
                    else (
                        page.average_confidence
                        if page.average_confidence is not None
                        else 0.50
                    )
                )

                lines.append(
                    OCRLine(
                        page_number=page.page_number,
                        text=line_text,
                        confidence=_clamp_confidence(
                            line_confidence
                        ),
                        tokens=ordered_tokens,
                        bounding_box=_bounding_box(
                            ordered_tokens
                        ),
                    )
                )

            continue

        fallback_confidence = (
            page.average_confidence
            if page.average_confidence is not None
            else 0.50
        )

        for raw_line in page.raw_text.splitlines():
            line_text = raw_line.strip()

            if not line_text:
                continue

            lines.append(
                OCRLine(
                    page_number=page.page_number,
                    text=line_text,
                    confidence=_clamp_confidence(
                        fallback_confidence
                    ),
                    tokens=(),
                    bounding_box=None,
                )
            )

    return tuple(lines)


def _extract_invoice_number(
    line: OCRLine,
    candidates: dict[str, ExtractedFieldCandidate],
) -> None:
    match = re.search(
        r"""(?ix)
        \binvoice\s*
        (?:number|no\.?|\#)
        \s*[:\-]?\s*
        (?P<value>
            [A-Z0-9]
            [A-Z0-9._/\-]*
        )
        """,
        line.text,
    )

    if match is None:
        return

    raw_value = match.group("value").strip()

    normalized = _normalize_identifier(
        raw_value
    )

    _store_best_candidate(
        candidates,
        _build_candidate(
            field_name="invoice_number",
            raw_value=raw_value,
            normalized_value=normalized,
            line=line,
            reliability=1.00,
            extraction_method="label_regex_v1",
        ),
    )


def _extract_invoice_date(
    line: OCRLine,
    candidates: dict[str, ExtractedFieldCandidate],
) -> None:
    match = re.search(
        r"""(?ix)
        \binvoice\s+date
        \s*[:\-]?\s*
        (?P<value>.+)
        $
        """,
        line.text,
    )

    if match is None:
        return

    raw_value = match.group("value").strip()

    normalized = _normalize_date(
        raw_value
    )

    if normalized is None:
        return

    _store_best_candidate(
        candidates,
        _build_candidate(
            field_name="invoice_date",
            raw_value=raw_value,
            normalized_value=normalized,
            line=line,
            reliability=0.98,
            extraction_method="label_date_parser_v1",
        ),
    )


def _extract_due_date(
    line: OCRLine,
    candidates: dict[str, ExtractedFieldCandidate],
) -> None:
    match = re.search(
        r"""(?ix)
        \bdue\s+date
        \s*[:\-]?\s*
        (?P<value>.+)
        $
        """,
        line.text,
    )

    if match is None:
        return

    raw_value = match.group("value").strip()

    normalized = _normalize_date(
        raw_value
    )

    if normalized is None:
        return

    _store_best_candidate(
        candidates,
        _build_candidate(
            field_name="due_date",
            raw_value=raw_value,
            normalized_value=normalized,
            line=line,
            reliability=0.96,
            extraction_method="label_date_parser_v1",
        ),
    )


def _extract_purchase_order_number(
    line: OCRLine,
    candidates: dict[str, ExtractedFieldCandidate],
) -> None:
    match = re.search(
        r"""(?ix)
        \b(?:purchase\s+order|po)
        \s*(?:number|no\.?|\#)?
        \s*[:\-]?\s*
        (?P<value>
            [A-Z0-9]
            [A-Z0-9._/\-]*
        )
        """,
        line.text,
    )

    if match is None:
        return

    raw_value = match.group("value").strip()

    normalized = _normalize_identifier(
        raw_value
    )

    _store_best_candidate(
        candidates,
        _build_candidate(
            field_name="purchase_order_number",
            raw_value=raw_value,
            normalized_value=normalized,
            line=line,
            reliability=0.96,
            extraction_method="label_regex_v1",
        ),
    )


def _extract_currency(
    line: OCRLine,
    candidates: dict[str, ExtractedFieldCandidate],
) -> None:
    match = re.search(
        r"""(?ix)
        \bcurrency
        \s*[:\-]?\s*
        (?P<value>
            [A-Z]{3}
            |
            [$€£]
        )
        """,
        line.text,
    )

    if match is None:
        return

    raw_value = match.group("value").strip()

    normalized = _normalize_currency(
        raw_value
    )

    if normalized is None:
        return

    _store_best_candidate(
        candidates,
        _build_candidate(
            field_name="currency",
            raw_value=raw_value,
            normalized_value=normalized,
            line=line,
            reliability=1.00,
            extraction_method="currency_label_v1",
        ),
    )


def _extract_amounts(
    line: OCRLine,
    candidates: dict[str, ExtractedFieldCandidate],
) -> None:
    amount_patterns = (
        (
            "subtotal",
            re.compile(
                r"(?i)^\s*subtotal\s*[:\-]?\s*(?P<value>.+?)\s*$"
            ),
            0.98,
        ),
        (
            "discount_amount",
            re.compile(
                r"(?i)^\s*(?:discount|less)\s*[:\-]?\s*(?P<value>.+?)\s*$"
            ),
            0.94,
        ),
        (
            "shipping_amount",
            re.compile(
                r"(?i)^\s*(?:shipping|freight)\s*[:\-]?\s*(?P<value>.+?)\s*$"
            ),
            0.94,
        ),
        (
            "tax_amount",
            re.compile(
                r"(?i)^\s*(?:sales\s+)?tax\s*[:\-]?\s*(?P<value>.+?)\s*$"
            ),
            0.98,
        ),
        (
            "total_amount",
            re.compile(
                r"""(?ix)
                ^\s*
                (?:
                    total(?:\s+amount)?
                    |
                    amount\s+due
                    |
                    balance\s+due
                )
                \s*[:\-]?\s*
                (?P<value>.+?)
                \s*$
                """
            ),
            1.00,
        ),
    )

    for field_name, pattern, reliability in amount_patterns:
        match = pattern.search(line.text)

        if match is None:
            continue

        raw_value = match.group("value").strip()

        normalized = _normalize_decimal(
            raw_value
        )

        if normalized is None:
            continue

        _store_best_candidate(
            candidates,
            _build_candidate(
                field_name=field_name,
                raw_value=raw_value,
                normalized_value=normalized,
                line=line,
                reliability=reliability,
                extraction_method="amount_label_parser_v1",
            ),
        )


def _extract_vendor_name(
    lines: tuple[OCRLine, ...],
) -> ExtractedFieldCandidate | None:
    invoice_title_index: int | None = None

    for index, line in enumerate(lines[:15]):
        if INVOICE_TITLE_PATTERN.fullmatch(
            line.text.strip()
        ):
            invoice_title_index = index
            break

    candidate_lines: list[
        tuple[OCRLine, float]
    ] = []

    if invoice_title_index is not None:
        for offset, line in enumerate(
            lines[
                invoice_title_index + 1:
                invoice_title_index + 6
            ],
            start=1,
        ):
            candidate_lines.append(
                (
                    line,
                    max(
                        0.84,
                        0.94 - ((offset - 1) * 0.025),
                    ),
                )
            )

    for line in lines[:8]:
        candidate_lines.append(
            (
                line,
                0.82,
            )
        )

    seen: set[tuple[int, str]] = set()

    for line, reliability in candidate_lines:
        identity = (
            line.page_number,
            line.text,
        )

        if identity in seen:
            continue

        seen.add(identity)

        value = line.text.strip()

        if not _looks_like_vendor_name(value):
            continue

        normalized = re.sub(
            r"\s+",
            " ",
            value,
        ).strip()

        return _build_candidate(
            field_name="vendor_name",
            raw_value=value,
            normalized_value=normalized,
            line=line,
            reliability=reliability,
            extraction_method="invoice_heading_layout_v1",
        )

    return None


def _looks_like_vendor_name(
    value: str,
) -> bool:
    if not value:
        return False

    if INVOICE_TITLE_PATTERN.fullmatch(value):
        return False

    if FIELD_LABEL_PATTERN.search(value):
        return False

    if len(value) < 3 or len(value) > 120:
        return False

    alphabetic_count = sum(
        character.isalpha()
        for character in value
    )

    digit_count = sum(
        character.isdigit()
        for character in value
    )

    if alphabetic_count < 3:
        return False

    if digit_count > alphabetic_count:
        return False

    if re.fullmatch(
        r"[$€£\d\s,.\-()/]+",
        value,
    ):
        return False

    return True


def _infer_currency_from_amount_lines(
    lines: tuple[OCRLine, ...],
) -> ExtractedFieldCandidate | None:
    for line in reversed(lines):
        if not re.search(
            r"(?i)\b(total|subtotal|tax|amount\s+due)\b",
            line.text,
        ):
            continue

        match = re.search(
            r"(?i)(?P<value>\b[A-Z]{3}\b|[$€£])",
            line.text,
        )

        if match is None:
            continue

        raw_value = match.group("value")

        normalized = _normalize_currency(
            raw_value
        )

        if normalized is None:
            continue

        return _build_candidate(
            field_name="currency",
            raw_value=raw_value,
            normalized_value=normalized,
            line=line,
            reliability=0.90,
            extraction_method="amount_currency_inference_v1",
        )

    return None


def _normalize_identifier(
    raw_value: str,
) -> str:
    return re.sub(
        r"\s+",
        " ",
        raw_value.strip(),
    ).upper()


def _normalize_currency(
    raw_value: str,
) -> str | None:
    normalized = raw_value.strip().upper()

    symbol_map = {
        "$": "USD",
        "€": "EUR",
        "£": "GBP",
    }

    if normalized in symbol_map:
        return symbol_map[normalized]

    if re.fullmatch(
        r"[A-Z]{3}",
        normalized,
    ):
        return normalized

    return None


def _normalize_decimal(
    raw_value: str,
) -> str | None:
    cleaned = raw_value.strip()

    negative_parentheses = (
        cleaned.startswith("(")
        and cleaned.endswith(")")
    )

    number_match = re.search(
        r"[-+]?\d[\d,]*(?:\.\d+)?",
        cleaned,
    )

    if number_match is None:
        return None

    number_text = number_match.group(0).replace(
        ",",
        "",
    )

    try:
        number = Decimal(number_text)
    except InvalidOperation:
        return None

    if negative_parentheses:
        number = -abs(number)

    return format(
        number,
        "f",
    )


def _normalize_date(
    raw_value: str,
) -> str | None:
    cleaned = re.sub(
        r"\s+",
        " ",
        raw_value.strip(),
    )

    candidate_patterns = (
        r"\d{4}[-/.]\d{1,2}[-/.]\d{1,2}",
        r"\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4}",
        r"[A-Za-z]{3,9}\s+\d{1,2},?\s+\d{4}",
        r"\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4}",
    )

    candidate = cleaned

    for candidate_pattern in candidate_patterns:
        match = re.search(
            candidate_pattern,
            cleaned,
        )

        if match is not None:
            candidate = match.group(0)
            break

    candidate = candidate.strip()

    for date_pattern in DATE_PATTERNS:
        try:
            parsed = datetime.strptime(
                candidate,
                date_pattern,
            ).date()

            return parsed.isoformat()
        except ValueError:
            continue

    return None


def _build_candidate(
    *,
    field_name: str,
    raw_value: str,
    normalized_value: str,
    line: OCRLine,
    reliability: float,
    extraction_method: str,
) -> ExtractedFieldCandidate:
    confidence = _clamp_confidence(
        line.confidence * reliability
    )

    evidence = {
        "page_number": line.page_number,
        "line_text": line.text,
        "bounding_box": line.bounding_box,
        "tokens": [
            {
                "text": token.get("text"),
                "confidence": token.get("confidence"),
                "left": token.get("left"),
                "top": token.get("top"),
                "width": token.get("width"),
                "height": token.get("height"),
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
            for token in line.tokens
        ],
    }

    return ExtractedFieldCandidate(
        field_name=field_name,
        raw_value=raw_value,
        normalized_value=normalized_value,
        confidence=confidence,
        confidence_source="derived_from_ocr_tokens",
        extraction_method=extraction_method,
        page_number=line.page_number,
        evidence=evidence,
    )


def _store_best_candidate(
    candidates: dict[str, ExtractedFieldCandidate],
    candidate: ExtractedFieldCandidate,
) -> None:
    current = candidates.get(
        candidate.field_name
    )

    if (
        current is None
        or candidate.confidence > current.confidence
    ):
        candidates[candidate.field_name] = candidate


def _calculate_header_confidence(
    candidates: dict[str, ExtractedFieldCandidate],
) -> float:
    weighted_confidence = 0.0
    total_weight = 0.0

    for field_name, weight in CONFIDENCE_WEIGHTS.items():
        candidate = candidates.get(field_name)

        if field_name in REQUIRED_HEADER_FIELDS:
            total_weight += weight

            if candidate is not None:
                weighted_confidence += (
                    candidate.confidence * weight
                )

            continue

        if candidate is not None:
            total_weight += weight
            weighted_confidence += (
                candidate.confidence * weight
            )

    if total_weight == 0:
        return 0.0

    return round(
        weighted_confidence / total_weight,
        4,
    )


def _bounding_box(
    tokens: tuple[dict[str, Any], ...],
) -> dict[str, int] | None:
    if not tokens:
        return None

    left = min(
        int(token.get("left", 0))
        for token in tokens
    )

    top = min(
        int(token.get("top", 0))
        for token in tokens
    )

    right = max(
        int(token.get("left", 0))
        + int(token.get("width", 0))
        for token in tokens
    )

    bottom = max(
        int(token.get("top", 0))
        + int(token.get("height", 0))
        for token in tokens
    )

    return {
        "left": left,
        "top": top,
        "right": right,
        "bottom": bottom,
        "width": max(0, right - left),
        "height": max(0, bottom - top),
    }


def _clamp_confidence(
    value: float,
) -> float:
    return round(
        max(
            0.0,
            min(1.0, float(value)),
        ),
        4,
    )