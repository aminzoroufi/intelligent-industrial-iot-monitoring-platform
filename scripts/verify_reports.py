#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Amin Zoroufi <aminn.zoroufi@gmail.com>
# SPDX-License-Identifier: LicenseRef-Portfolio-Source-Available
"""Render and structurally verify every generated report page."""

from __future__ import annotations

import hashlib
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pdfplumber
from PIL import Image, ImageDraw
from pypdf import PdfReader

ROOT = Path(__file__).parents[1]
REPORT_DIR = ROOT / "docs/report"
TMP_DIR = ROOT / "tmp/pdfs"
REPORTS = {
    "en": REPORT_DIR / "Intelligent_Industrial_IoT_Monitoring_Platform_EN.pdf",
    "fa": REPORT_DIR / "Intelligent_Industrial_IoT_Monitoring_Platform_FA.pdf",
    "schematic-review": ROOT / "hardware/fabrication/iiot-monitor-schematic-review.pdf",
}
CHECKSUM_MANIFEST = REPORT_DIR / "checksums.sha256"


def dereference(value: Any) -> Any:
    return value.get_object() if hasattr(value, "get_object") else value


def embedded_fonts(reader: PdfReader) -> set[str]:
    embedded: set[str] = set()
    for page in reader.pages:
        resources = dereference(page.get("/Resources", {}))
        fonts = dereference(resources.get("/Font", {}))
        for font_reference in fonts.values():
            font = dereference(font_reference)
            descriptor = dereference(font.get("/FontDescriptor", {}))
            if any(key in descriptor for key in ("/FontFile", "/FontFile2", "/FontFile3")):
                embedded.add(str(font.get("/BaseFont", "unknown")))
    return embedded


def render(path: Path, name: str) -> list[Path]:
    pdftoppm = shutil.which("pdftoppm")
    if pdftoppm is None:
        raise RuntimeError("pdftoppm is required for report verification")
    prefix = TMP_DIR / name
    for old in TMP_DIR.glob(f"{name}-*.png"):
        old.unlink()
    subprocess.run(
        [pdftoppm, "-png", "-r", "110", str(path), str(prefix)],
        check=True,
        capture_output=True,
        text=True,
    )
    pages = sorted(TMP_DIR.glob(f"{name}-*.png"))
    if not pages:
        raise ValueError(f"no rendered pages produced for {path}")
    return pages


def non_white_fraction(image: Image.Image) -> float:
    reduced = image.convert("RGB").resize((120, 170))
    pixels = reduced.get_flattened_data()
    non_white = sum(1 for red, green, blue in pixels if min(red, green, blue) < 245)
    return non_white / (120 * 170)


def contact_sheet(paths: list[Path], output: Path) -> None:
    thumb_width = 190
    thumb_height = 269
    columns = 4
    rows = (len(paths) + columns - 1) // columns
    canvas = Image.new("RGB", (columns * thumb_width, rows * (thumb_height + 24)), "#dce5e8")
    draw = ImageDraw.Draw(canvas)
    for index, path in enumerate(paths):
        with Image.open(path) as source:
            page = source.convert("RGB")
            page.thumbnail((thumb_width - 12, thumb_height - 12))
            x = (index % columns) * thumb_width + (thumb_width - page.width) // 2
            y = (index // columns) * (thumb_height + 24) + 6
            canvas.paste(page, (x, y))
            draw.text((x, y + page.height + 2), f"page {index + 1}", fill="#102027")
    canvas.save(output)


def verify_primary(path: Path, language: str) -> list[Path]:
    reader = PdfReader(str(path))
    if not 18 <= len(reader.pages) <= 30:
        raise ValueError(f"unexpected {language} page count: {len(reader.pages)}")
    metadata = reader.metadata
    if metadata is None or "Amin Zoroufi" not in str(metadata.author):
        raise ValueError(f"missing {language} author metadata")
    fonts = embedded_fonts(reader)
    if language == "fa" and (not fonts or not any("NotoSansArabic" in name for name in fonts)):
        raise ValueError(f"Noto font is not embedded in {language} report: {sorted(fonts)}")

    with pdfplumber.open(path) as document:
        extracted = [page.extract_text() or "" for page in document.pages]
    if any(len(text.strip()) < 35 for text in extracted):
        raise ValueError(f"blank or nearly blank page detected in {language} report")
    joined = "\n".join(extracted)
    if language == "en":
        for required in ("Executive summary", "A0-UNVERIFIED", "47 Python tests"):
            if required not in joined:
                raise ValueError(f"English report is missing required text: {required}")
    else:
        source = (REPORT_DIR / "src/report_fa.md").read_text(encoding="utf-8")
        if len(source) < 10_000 or "هیچ ادعای آزمون کارگاهی یا میدانی" not in source:
            raise ValueError("Persian editable source is incomplete")

    pages = render(path, language)
    if len(pages) != len(reader.pages):
        raise ValueError(f"rendered page count differs for {language}")
    for index, rendered in enumerate(pages, start=1):
        with Image.open(rendered) as image:
            if image.width < 800 or image.height < 1100:
                raise ValueError(f"unexpected render size on {language} page {index}")
            if non_white_fraction(image) < 0.015:
                raise ValueError(f"visually blank {language} page {index}")
    contact_sheet(pages, TMP_DIR / f"{language}-contact-sheet.png")
    return pages


def verify_hardware_review(path: Path) -> None:
    reader = PdfReader(str(path))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    if "NOT KICAD SCHEMATIC PDF" not in text or "NOT FOR FABRICATION" not in text:
        raise ValueError("hardware connectivity review lacks its non-release warning")
    pages = render(path, "schematic-review")
    contact_sheet(pages, TMP_DIR / "schematic-review-contact-sheet.png")


def verify_checksum_manifest() -> None:
    lines = []
    for path in REPORTS.values():
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        lines.append(f"{digest}  {path.relative_to(ROOT)}")
    expected = "\n".join(lines) + "\n"
    if not CHECKSUM_MANIFEST.is_file() or CHECKSUM_MANIFEST.read_text() != expected:
        raise ValueError("report checksum manifest is absent or stale")


def main() -> None:
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    for path in REPORTS.values():
        if not path.is_file():
            raise FileNotFoundError(path)
    verify_primary(REPORTS["en"], "en")
    verify_primary(REPORTS["fa"], "fa")
    verify_hardware_review(REPORTS["schematic-review"])
    verify_checksum_manifest()
    print("report structure, embedded fonts, text, and every rendered page passed automated QA")
    print(f"visual contact sheets: {TMP_DIR.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
