from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

REQUIRED_FILES = (
    ROOT / "README.md",
    ROOT / "CHANGELOG.md",
    ROOT / "docs" / "architecture" / "system-architecture.md",
    ROOT / "docs" / "setup" / "local-development.md",
    ROOT / "docs" / "release" / "portfolio-evidence-plan.md",
    ROOT / "docs" / "release" / "final-acceptance-checklist.md",
    ROOT / "docs" / "release" / "v1.0.0-release-notes.md",
    ROOT / "evidence" / "README.md",
    ROOT / "scripts" / "configure_local_supabase.ps1",
)

README_HEADINGS = (
    "## What the system demonstrates",
    "## Architecture",
    "## Core flow",
    "## Technical stack",
    "## Reliability and safety decisions",
    "## Run locally",
    "## Validation status",
    "## Evidence",
    "## What this portfolio project proves",
    "## Important limitation",
)


def _read(path: Path) -> str:
    return path.read_text(
        encoding="utf-8-sig",
    )


def _assert_required_files() -> None:
    missing = [
        str(path.relative_to(ROOT))
        for path in REQUIRED_FILES
        if not path.is_file()
    ]

    if missing:
        raise AssertionError(
            "Missing release files: "
            + ", ".join(missing)
        )


def _assert_readme_contract() -> None:
    readme = _read(
        ROOT / "README.md"
    )

    for heading in README_HEADINGS:
        if heading not in readme:
            raise AssertionError(
                f"README is missing: {heading}"
            )

    forbidden = (
        "Week 1",
        "CSV, XLSX",
        "paid client",
    )

    for value in forbidden:
        if value in readme:
            raise AssertionError(
                "README contains stale or unsupported "
                f"language: {value}"
            )

    required_terms = (
        "synthetic or sanitized",
        "AUTO_APPROVED",
        "REVIEW_REQUIRED",
        "REJECTED",
        "Tesseract",
        "MinIO",
        "Supabase",
        "JSON",
        "CSV",
    )

    for value in required_terms:
        if value not in readme:
            raise AssertionError(
                f"README is missing required term: {value}"
            )


def _assert_markdown_links() -> None:
    excluded_directories = {
        ".git",
        ".next",
        ".pytest_cache",
        ".venv",
        "__pycache__",
        "build",
        "coverage",
        "dist",
        "node_modules",
        "venv",
    }

    markdown_files = [
        path
        for path in ROOT.rglob("*.md")
        if not any(
            part in excluded_directories
            or part.startswith(
                ".docuflow-release-snapshot-"
            )
            for part in path.relative_to(
                ROOT
            ).parts[:-1]
        )
    ]

    link_pattern = re.compile(
        r"\[[^\]]+\]\(([^)]+)\)"
    )

    broken: list[str] = []

    for markdown_path in markdown_files:
        text = _read(
            markdown_path
        )

        for raw_target in link_pattern.findall(
            text
        ):
            target = raw_target.strip()

            if (
                not target
                or target.startswith(
                    (
                        "http://",
                        "https://",
                        "mailto:",
                        "#",
                    )
                )
            ):
                continue

            target_path = target.split(
                "#",
                1,
            )[0]

            resolved = (
                markdown_path.parent
                / target_path
            ).resolve()

            try:
                resolved.relative_to(
                    ROOT.resolve()
                )
            except ValueError:
                broken.append(
                    f"{markdown_path.relative_to(ROOT)} -> {target}"
                )
                continue

            if not resolved.exists():
                broken.append(
                    f"{markdown_path.relative_to(ROOT)} -> {target}"
                )

    if broken:
        raise AssertionError(
            "Broken local markdown links: "
            + "; ".join(broken)
        )


def _assert_unique_adr_numbers() -> None:
    adr_directory = (
        ROOT / "docs" / "adr"
    )

    numbers: dict[str, list[str]] = {}

    for path in adr_directory.glob(
        "[0-9][0-9][0-9][0-9]-*.md"
    ):
        number = path.name[:4]
        numbers.setdefault(
            number,
            [],
        ).append(
            path.name
        )

    duplicates = {
        number: names
        for number, names in numbers.items()
        if len(names) > 1
    }

    if duplicates:
        raise AssertionError(
            "Duplicate ADR numbers: "
            + repr(duplicates)
        )


def main() -> None:
    _assert_required_files()
    _assert_readme_contract()
    _assert_markdown_links()
    _assert_unique_adr_numbers()

    print(
        {
            "status": "passed",
            "required_files": len(
                REQUIRED_FILES
            ),
            "readme_headings": len(
                README_HEADINGS
            ),
            "markdown_links": "valid",
            "adr_numbers": "unique",
        }
    )


if __name__ == "__main__":
    main()
