#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Amin Zoroufi <aminn.zoroufi@gmail.com>
# SPDX-License-Identifier: LicenseRef-Portfolio-Source-Available
"""Build the English, Persian, and hardware-review PDF documents."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas

ROOT = Path(__file__).parents[1]
REPORT_DIR = ROOT / "docs/report"
FONT_DIR = REPORT_DIR / "fonts"
REGULAR_FONT = FONT_DIR / "NotoSansArabic-Regular.ttf"
BOLD_FONT = FONT_DIR / "NotoSansArabic-Bold.ttf"
EN_SOURCE = REPORT_DIR / "src/report_en.md"
FA_SOURCE = REPORT_DIR / "src/report_fa.md"
EN_OUTPUT = REPORT_DIR / "Intelligent_Industrial_IoT_Monitoring_Platform_EN.pdf"
FA_OUTPUT = REPORT_DIR / "Intelligent_Industrial_IoT_Monitoring_Platform_FA.pdf"
HARDWARE_REVIEW_OUTPUT = ROOT / "hardware/fabrication/iiot-monitor-schematic-review.pdf"
CHECKSUM_MANIFEST = REPORT_DIR / "checksums.sha256"

PAGE_WIDTH, PAGE_HEIGHT = A4
MARGIN = 46
CONTENT_WIDTH = PAGE_WIDTH - 2 * MARGIN
INK = colors.HexColor("#102027")
MUTED = colors.HexColor("#52636B")
ACCENT = colors.HexColor("#087E8B")
ACCENT_DARK = colors.HexColor("#075866")
PALE = colors.HexColor("#E8F3F4")
WARNING = colors.HexColor("#B45309")
RED = colors.HexColor("#A73434")
GREEN = colors.HexColor("#18734B")


ARABIC_FORMS: dict[str, tuple[str, str | None, str | None, str | None]] = {
    "ء": ("\ufe80", None, None, None),
    "آ": ("\ufe81", "\ufe82", None, None),
    "أ": ("\ufe83", "\ufe84", None, None),
    "ؤ": ("\ufe85", "\ufe86", None, None),
    "إ": ("\ufe87", "\ufe88", None, None),
    "ئ": ("\ufe89", "\ufe8a", "\ufe8b", "\ufe8c"),
    "ا": ("\ufe8d", "\ufe8e", None, None),
    "ب": ("\ufe8f", "\ufe90", "\ufe91", "\ufe92"),
    "پ": ("\ufb56", "\ufb57", "\ufb58", "\ufb59"),
    "ت": ("\ufe95", "\ufe96", "\ufe97", "\ufe98"),
    "ث": ("\ufe99", "\ufe9a", "\ufe9b", "\ufe9c"),
    "ج": ("\ufe9d", "\ufe9e", "\ufe9f", "\ufea0"),
    "چ": ("\ufb7a", "\ufb7b", "\ufb7c", "\ufb7d"),
    "ح": ("\ufea1", "\ufea2", "\ufea3", "\ufea4"),
    "خ": ("\ufea5", "\ufea6", "\ufea7", "\ufea8"),
    "د": ("\ufea9", "\ufeaa", None, None),
    "ذ": ("\ufeab", "\ufeac", None, None),
    "ر": ("\ufead", "\ufeae", None, None),
    "ز": ("\ufeaf", "\ufeb0", None, None),
    "ژ": ("\ufb8a", "\ufb8b", None, None),
    "س": ("\ufeb1", "\ufeb2", "\ufeb3", "\ufeb4"),
    "ش": ("\ufeb5", "\ufeb6", "\ufeb7", "\ufeb8"),
    "ص": ("\ufeb9", "\ufeba", "\ufebb", "\ufebc"),
    "ض": ("\ufebd", "\ufebe", "\ufebf", "\ufec0"),
    "ط": ("\ufec1", "\ufec2", "\ufec3", "\ufec4"),
    "ظ": ("\ufec5", "\ufec6", "\ufec7", "\ufec8"),
    "ع": ("\ufec9", "\ufeca", "\ufecb", "\ufecc"),
    "غ": ("\ufecd", "\ufece", "\ufecf", "\ufed0"),
    "ف": ("\ufed1", "\ufed2", "\ufed3", "\ufed4"),
    "ق": ("\ufed5", "\ufed6", "\ufed7", "\ufed8"),
    "ك": ("\ufed9", "\ufeda", "\ufedb", "\ufedc"),
    "ک": ("\ufb8e", "\ufb8f", "\ufb90", "\ufb91"),
    "گ": ("\ufb92", "\ufb93", "\ufb94", "\ufb95"),
    "ل": ("\ufedd", "\ufede", "\ufedf", "\ufee0"),
    "م": ("\ufee1", "\ufee2", "\ufee3", "\ufee4"),
    "ن": ("\ufee5", "\ufee6", "\ufee7", "\ufee8"),
    "ه": ("\ufee9", "\ufeea", "\ufeeb", "\ufeec"),
    "و": ("\ufeed", "\ufeee", None, None),
    "ى": ("\ufeef", "\ufef0", None, None),
    "ي": ("\ufef1", "\ufef2", "\ufef3", "\ufef4"),
    "ی": ("\ufbfc", "\ufbfd", "\ufbfe", "\ufbff"),
}
LTR_RUN = re.compile(r"[A-Za-z0-9۰-۹٠-٩_.:/+@#=-]+(?: [A-Za-z0-9۰-۹٠-٩_.:/+@#=-]+)*")


def shape_arabic(text: str) -> str:
    output: list[str] = []
    for index, character in enumerate(text):
        forms = ARABIC_FORMS.get(character)
        if forms is None:
            output.append(character)
            continue
        previous = text[index - 1] if index > 0 else ""
        following = text[index + 1] if index + 1 < len(text) else ""
        previous_forms = ARABIC_FORMS.get(previous)
        following_forms = ARABIC_FORMS.get(following)
        joins_previous = bool(previous_forms and previous_forms[2] and forms[1])
        joins_following = bool(forms[2] and following_forms and following_forms[1])
        if joins_previous and joins_following and forms[3]:
            output.append(forms[3])
        elif joins_previous and forms[1]:
            output.append(forms[1])
        elif joins_following and forms[2]:
            output.append(forms[2])
        else:
            output.append(forms[0])
    return "".join(output)


def rtl_visual(text: str) -> str:
    shaped = shape_arabic(text)
    protected = LTR_RUN.sub(lambda match: match.group(0)[::-1], shaped)
    return protected[::-1].translate(str.maketrans("()[]{}<>", ")(][}{><"))


@dataclass(frozen=True)
class Block:
    kind: Literal["paragraph", "bullet", "directive"]
    value: str


@dataclass(frozen=True)
class Section:
    title: str
    blocks: list[Block]


@dataclass(frozen=True)
class DocumentSource:
    title: str
    metadata: list[str]
    sections: list[Section]


def parse_markdown(path: Path) -> DocumentSource:
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or not lines[0].startswith("# "):
        raise ValueError(f"missing report title: {path}")
    title = lines[0][2:].strip()
    metadata: list[str] = []
    sections: list[Section] = []
    current_title: str | None = None
    current_blocks: list[Block] = []
    paragraph: list[str] = []

    def flush_paragraph() -> None:
        if paragraph:
            current_blocks.append(Block("paragraph", " ".join(paragraph)))
            paragraph.clear()

    for line in lines[1:]:
        stripped = line.strip()
        if stripped.startswith("## "):
            flush_paragraph()
            if current_title is not None:
                sections.append(Section(current_title, list(current_blocks)))
            current_title = stripped[3:]
            current_blocks.clear()
        elif current_title is None:
            if stripped:
                metadata.append(stripped)
        elif not stripped:
            flush_paragraph()
        elif stripped.startswith("[[") and stripped.endswith("]]"):
            flush_paragraph()
            current_blocks.append(Block("directive", stripped[2:-2]))
        elif stripped.startswith("- "):
            flush_paragraph()
            current_blocks.append(Block("bullet", stripped[2:]))
        else:
            paragraph.append(stripped)
    flush_paragraph()
    if current_title is not None:
        sections.append(Section(current_title, list(current_blocks)))
    if len(sections) != 17:
        raise ValueError(f"expected 17 report sections, found {len(sections)} in {path}")
    return DocumentSource(title, metadata, sections)


class Report:
    def __init__(self, output: Path, source: DocumentSource, *, rtl: bool) -> None:
        self.output = output
        self.source = source
        self.rtl = rtl
        self.canvas = Canvas(str(output), pagesize=A4, pageCompression=1, invariant=1)
        self.canvas.setTitle(source.title)
        self.canvas.setAuthor("Amin Zoroufi <aminn.zoroufi@gmail.com>")
        self.canvas.setSubject("Industrial IoT portfolio engineering report; simulated evidence")
        self.canvas.setCreator("scripts/build_reports.py")
        self.page = 0
        self.y = PAGE_HEIGHT - MARGIN
        self.section_title = ""

    @property
    def regular(self) -> str:
        return "NotoArabic" if self.rtl else "Helvetica"

    @property
    def bold(self) -> str:
        return "NotoArabicBold" if self.rtl else "Helvetica-Bold"

    def rtl_segments(self, value: str, font: str) -> list[tuple[str, str]]:
        logical: list[tuple[str, Literal["rtl", "latin", "protected"]]] = []
        position = 0
        for match in LTR_RUN.finditer(value):
            if match.start() > position:
                logical.append((value[position : match.start()], "rtl"))
            kind: Literal["latin", "protected"] = (
                "protected" if re.search(r"[۰-۹٠-٩]", match.group(0)) else "latin"
            )
            logical.append((match.group(0), kind))
            position = match.end()
        if position < len(value):
            logical.append((value[position:], "rtl"))
        latin_font = "Helvetica-Bold" if "Bold" in font else "Helvetica"
        segments: list[tuple[str, str]] = []
        for text, kind in reversed(logical):
            if kind == "latin":
                segments.append((text, latin_font))
            elif kind == "protected":
                segments.append((text, font))
            else:
                segments.append((rtl_visual(text), font))
        return segments

    def text_width(self, value: str, font: str, size: float) -> float:
        if not self.rtl:
            return pdfmetrics.stringWidth(value, font, size)
        return sum(
            pdfmetrics.stringWidth(text, segment_font, size)
            for text, segment_font in self.rtl_segments(value, font)
        )

    def draw_text(
        self, value: str, x: float, y: float, *, font: str, size: float, right: bool = False
    ) -> None:
        if not self.rtl:
            self.canvas.setFont(font, size)
            if right:
                self.canvas.drawRightString(x, y, value)
            else:
                self.canvas.drawString(x, y, value)
            return
        segments = self.rtl_segments(value, font)
        cursor = x - self.text_width(value, font, size) if right else x
        for text, segment_font in segments:
            self.canvas.setFont(segment_font, size)
            self.canvas.drawString(cursor, y, text)
            cursor += pdfmetrics.stringWidth(text, segment_font, size)

    def finish_page(self) -> None:
        if self.page == 0:
            return
        self.canvas.setStrokeColor(colors.HexColor("#D5E1E4"))
        self.canvas.line(MARGIN, 31, PAGE_WIDTH - MARGIN, 31)
        footer = f"{self.page}" if not self.rtl else f"صفحه {self.page}"
        self.draw_text(footer, PAGE_WIDTH - MARGIN, 17, font=self.regular, size=8, right=True)
        level = (
            "SIMULATED - NOT FIELD VALIDATED"
            if not self.rtl
            else "شبیه سازی شده - فاقد اعتبار میدانی"
        )
        self.draw_text(level, MARGIN, 17, font=self.regular, size=7.5)
        self.canvas.showPage()

    def new_page(self, section_title: str = "") -> None:
        self.finish_page()
        self.page += 1
        self.section_title = section_title
        self.y = PAGE_HEIGHT - MARGIN
        self.canvas.setFillColor(ACCENT)
        self.canvas.rect(0, PAGE_HEIGHT - 12, PAGE_WIDTH, 12, fill=1, stroke=0)
        if section_title:
            self.canvas.setFillColor(MUTED)
            self.draw_text(
                self.source.title,
                PAGE_WIDTH - MARGIN if self.rtl else MARGIN,
                PAGE_HEIGHT - 31,
                font=self.regular,
                size=7.5,
                right=self.rtl,
            )
            self.y = PAGE_HEIGHT - 63

    def cover(self) -> None:
        self.new_page()
        self.canvas.setFillColor(ACCENT_DARK)
        self.canvas.rect(0, PAGE_HEIGHT * 0.56, PAGE_WIDTH, PAGE_HEIGHT * 0.44, fill=1, stroke=0)
        self.canvas.setFillColor(colors.white)
        title_lines = self.wrap(self.source.title, self.bold, 27, PAGE_WIDTH - 2 * MARGIN)
        y = PAGE_HEIGHT - 145
        for line in title_lines:
            self.draw_text(
                line,
                PAGE_WIDTH - MARGIN if self.rtl else MARGIN,
                y,
                font=self.bold,
                size=27,
                right=self.rtl,
            )
            y -= 38
        subtitle = "Engineering portfolio report" if not self.rtl else "گزارش مهندسی نمونه کار"
        self.draw_text(
            subtitle,
            PAGE_WIDTH - MARGIN if self.rtl else MARGIN,
            y - 8,
            font=self.regular,
            size=14,
            right=self.rtl,
        )
        self.canvas.setFillColor(INK)
        box_y = PAGE_HEIGHT * 0.46
        self.canvas.setFillColor(PALE)
        self.canvas.roundRect(MARGIN, 90, CONTENT_WIDTH, box_y - 62, 12, fill=1, stroke=0)
        self.canvas.setFillColor(INK)
        y = box_y - 20
        for item in self.source.metadata:
            for line in self.wrap(item, self.regular, 9.5, CONTENT_WIDTH - 36):
                self.draw_text(
                    line,
                    PAGE_WIDTH - MARGIN - 18 if self.rtl else MARGIN + 18,
                    y,
                    font=self.regular,
                    size=9.5,
                    right=self.rtl,
                )
                y -= 15
            y -= 2
        notice = (
            "Low-voltage demonstrator only. No safety, bench, or field certification."
            if not self.rtl
            else "فقط نمایش کم ولتاژ؛ فاقد گواهی ایمنی، کارگاهی یا میدانی"
        )
        self.canvas.setFillColor(RED)
        self.draw_text(
            notice,
            PAGE_WIDTH - MARGIN if self.rtl else MARGIN,
            61,
            font=self.bold,
            size=9,
            right=self.rtl,
        )

    def wrap(self, text: str, font: str, size: float, width: float) -> list[str]:
        words = text.split()
        if not words:
            return []
        lines: list[str] = []
        current = words[0]
        for word in words[1:]:
            candidate = f"{current} {word}"
            if self.text_width(candidate, font, size) <= width:
                current = candidate
            else:
                lines.append(current)
                current = word
        lines.append(current)
        return lines

    def ensure(self, required: float) -> None:
        if self.y - required < 48:
            continuation = (
                f"{self.section_title} (continued)"
                if not self.rtl
                else f"ادامه {self.section_title}"
            )
            self.new_page(continuation)
            self.section_heading(continuation, continuation=True)

    def section_heading(self, title: str, *, continuation: bool = False) -> None:
        self.canvas.setFillColor(INK)
        size = 18 if not continuation else 14
        lines = self.wrap(title, self.bold, size, CONTENT_WIDTH)
        for line in lines:
            self.draw_text(
                line,
                PAGE_WIDTH - MARGIN if self.rtl else MARGIN,
                self.y,
                font=self.bold,
                size=size,
                right=self.rtl,
            )
            self.y -= size + 6
        self.canvas.setFillColor(ACCENT)
        if self.rtl:
            self.canvas.rect(PAGE_WIDTH - MARGIN - 72, self.y - 2, 72, 3, fill=1, stroke=0)
        else:
            self.canvas.rect(MARGIN, self.y - 2, 72, 3, fill=1, stroke=0)
        self.y -= 20

    def paragraph(self, value: str, *, bullet: bool = False) -> None:
        size = 9.3
        leading = 14.3
        available = CONTENT_WIDTH - (18 if bullet else 0)
        lines = self.wrap(value, self.regular, size, available)
        self.ensure(len(lines) * leading + 14)
        self.canvas.setFillColor(INK)
        if bullet:
            bullet_x = PAGE_WIDTH - MARGIN if self.rtl else MARGIN
            self.canvas.setFillColor(ACCENT)
            self.canvas.circle(
                bullet_x - 4 if self.rtl else bullet_x + 4, self.y + 3, 2.2, fill=1, stroke=0
            )
        text_x = (
            PAGE_WIDTH - MARGIN - (14 if bullet else 0)
            if self.rtl
            else MARGIN + (14 if bullet else 0)
        )
        for line in lines:
            self.canvas.setFillColor(INK)
            self.draw_text(line, text_x, self.y, font=self.regular, size=size, right=self.rtl)
            self.y -= leading
        self.y -= 8

    def figure_caption(self, english: str, persian: str) -> None:
        self.y -= 5
        value = persian if self.rtl else english
        self.canvas.setFillColor(MUTED)
        self.draw_text(
            value,
            PAGE_WIDTH - MARGIN if self.rtl else MARGIN,
            self.y,
            font=self.regular,
            size=7.8,
            right=self.rtl,
        )
        self.y -= 18

    def label(self, text_en: str, text_fa: str, x: float, y: float, *, size: float = 7.5) -> None:
        text = text_fa if self.rtl else text_en
        self.draw_text(text, x, y, font=self.bold, size=size, right=False)

    def architecture(self) -> None:
        self.ensure(195)
        top = self.y
        box_width = 88
        box_height = 42
        gap = 16
        labels = [
            ("Sensors", "حسگرها"),
            ("ESP32 edge", "لبه ESP32"),
            ("MQTT broker", "کارگزار MQTT"),
            ("Ingest + DB", "دریافت و داده"),
            ("API + Web", "API و داشبورد"),
        ]
        for index, (english, persian) in enumerate(labels):
            x = MARGIN + index * (box_width + gap)
            self.canvas.setFillColor(PALE if index % 2 == 0 else colors.HexColor("#D9ECEE"))
            self.canvas.setStrokeColor(ACCENT)
            self.canvas.roundRect(x, top - box_height, box_width, box_height, 7, fill=1, stroke=1)
            self.canvas.setFillColor(INK)
            text = persian if self.rtl else english
            tw = self.text_width(text, self.bold, 7.5)
            self.draw_text(text, x + (box_width - tw) / 2, top - 25, font=self.bold, size=7.5)
            if index < len(labels) - 1:
                x1 = x + box_width + 2
                x2 = x + box_width + gap - 3
                self.canvas.setStrokeColor(ACCENT_DARK)
                self.canvas.line(x1, top - 21, x2, top - 21)
                self.canvas.line(x2 - 5, top - 17, x2, top - 21)
                self.canvas.line(x2 - 5, top - 25, x2, top - 21)
        self.canvas.setStrokeColor(WARNING)
        self.canvas.line(MARGIN + 110, top - 68, MARGIN + 110, top - 107)
        self.canvas.roundRect(MARGIN + 55, top - 147, 110, 40, 7, fill=0, stroke=1)
        self.label("STM32 / Modbus", "STM32 و Modbus", MARGIN + 67, top - 132)
        self.canvas.setFillColor(colors.HexColor("#FFF7E6"))
        self.canvas.roundRect(MARGIN, top - 185, CONTENT_WIDTH, 24, 6, fill=1, stroke=0)
        self.canvas.setFillColor(WARNING)
        warning = "Explicit boundaries: SPI / I2C / UART - MQTT - SQL - REST / WebSocket"
        warning_fa = "مرزهای صریح: SPI و I2C و UART - MQTT - SQL - REST و WebSocket"
        self.draw_text(
            warning_fa if self.rtl else warning,
            PAGE_WIDTH - MARGIN - 10 if self.rtl else MARGIN + 10,
            top - 177,
            font=self.regular,
            size=7.5,
            right=self.rtl,
        )
        self.y = top - 195
        self.figure_caption(
            "Figure 1. End-to-end architecture generated from the implemented repository boundaries.",
            "شکل ۱. معماری سراسری بر پایه مرزهای پیاده سازی شده مخزن.",
        )

    def detection_metrics(self) -> None:
        self.ensure(170)
        report = json.loads((ROOT / "data/demo/anomaly-evaluation.v1.json").read_text())
        top = self.y
        metrics = (
            ("Rules", "قواعد", report["deterministic_detector"]),
            ("Isolation Forest", "Isolation Forest", report["isolation_forest"]),
        )
        for index, (english, persian, values) in enumerate(metrics):
            y = top - index * 65
            self.canvas.setFillColor(INK)
            self.draw_text(persian if self.rtl else english, MARGIN, y, font=self.bold, size=9)
            for metric_index, key in enumerate(
                ("precision", "recall", "f1", "false_positive_rate")
            ):
                x = MARGIN + 98 + metric_index * 98
                value = float(values[key])
                self.canvas.setFillColor(colors.HexColor("#DDE7E9"))
                self.canvas.roundRect(x, y - 8, 74, 10, 4, fill=1, stroke=0)
                self.canvas.setFillColor(RED if key == "false_positive_rate" else ACCENT)
                self.canvas.roundRect(x, y - 8, max(2, 74 * value), 10, 4, fill=1, stroke=0)
                label = {"precision": "P", "recall": "R", "f1": "F1", "false_positive_rate": "FPR"}[
                    key
                ]
                self.canvas.setFillColor(MUTED)
                self.draw_text(f"{label} {value * 100:.1f}%", x, y - 23, font=self.regular, size=7)
        self.canvas.setFillColor(colors.HexColor("#FFF7E6"))
        self.canvas.roundRect(MARGIN, top - 144, CONTENT_WIDTH, 30, 6, fill=1, stroke=0)
        caveat = "Synthetic fixture metrics - not probability and not field performance"
        caveat_fa = "معیار داده مصنوعی - نه احتمال و نه کارایی میدانی"
        self.canvas.setFillColor(WARNING)
        self.draw_text(
            caveat_fa if self.rtl else caveat,
            PAGE_WIDTH - MARGIN - 10 if self.rtl else MARGIN + 10,
            top - 134,
            font=self.bold,
            size=8,
            right=self.rtl,
        )
        self.y = top - 162
        self.figure_caption(
            "Figure 2. Reproducible detector comparison from the versioned synthetic report.",
            "شکل ۲. مقایسه بازتولیدپذیر آشکارسازها در گزارش مصنوعی نسخه دار.",
        )

    def board(self) -> None:
        self.ensure(245)
        design = json.loads((ROOT / "hardware/design.json").read_text())
        board = design["board"]
        top = self.y
        scale = 4.35
        x0 = MARGIN + 30
        y0 = top - float(board["height"]) * scale
        self.canvas.setFillColor(colors.HexColor("#145B43"))
        self.canvas.setStrokeColor(colors.HexColor("#68C89E"))
        self.canvas.roundRect(
            x0,
            y0,
            float(board["width"]) * scale,
            float(board["height"]) * scale,
            6,
            fill=1,
            stroke=1,
        )
        for component in design["components"]:
            x = x0 + (float(component["x"]) - float(component["width"]) / 2) * scale
            y = (
                y0
                + (float(board["height"]) - float(component["y"]) - float(component["height"]) / 2)
                * scale
            )
            width = max(float(component["width"]) * scale, 5)
            height = max(float(component["height"]) * scale, 4)
            self.canvas.setFillColor(colors.HexColor("#D8E7DD"))
            self.canvas.setStrokeColor(INK)
            self.canvas.rect(x, y, width, height, fill=1, stroke=1)
            if width > 13 and height > 8:
                self.canvas.setFillColor(INK)
                self.draw_text(str(component["ref"]), x + 1.5, y + 2.5, font=self.bold, size=4.7)
        self.canvas.setFillColor(RED)
        self.draw_text(
            "A0-UNVERIFIED - UNROUTED - NO MAINS",
            x0,
            y0 - 17,
            font=self.bold,
            size=8,
        )
        self.y = y0 - 28
        self.figure_caption(
            "Figure 3. Source-derived component placement; this is not a fabrication release.",
            "شکل ۳. چیدمان قطعه از منبع پروژه؛ این تصویر مجوز ساخت نیست.",
        )

    def verification(self) -> None:
        self.ensure(198)
        rows = [
            ("Python", "پایتون", "47 tests", "۴۷ آزمون", "PASS"),
            ("Typed source", "منبع نوع دار", "49 files", "۴۹ فایل", "PASS"),
            ("Dashboard", "داشبورد", "lint/type/4 tests", "نگارش، نوع، ۴ آزمون", "PASS"),
            ("Live backend", "پشت زنده", "earlier Compose slice", "اجرای پیشین Compose", "PASS"),
            (
                "Changed Compose",
                "Compose تغییر یافته",
                "follow-up not run",
                "اجرای دوباره انجام نشد",
                "BLOCKED",
            ),
            ("Embedded targets", "هدف نهفته", "toolchains absent", "ابزار موجود نیست", "BLOCKED"),
            ("CAD ERC/DRC", "ERC و DRC", "not run", "اجرا نشده", "NOT RUN"),
            ("Bench / field", "کارگاه و میدان", "no evidence", "بدون شاهد", "NOT RUN"),
        ]
        top = self.y
        columns = (MARGIN, MARGIN + 165, MARGIN + 350)
        widths = (160, 180, 130)
        headers = ("Area", "Evidence", "Status") if not self.rtl else ("وضعیت", "شاهد", "بخش")
        self.canvas.setFillColor(ACCENT_DARK)
        self.canvas.rect(MARGIN, top - 25, sum(widths), 25, fill=1, stroke=0)
        self.canvas.setFillColor(colors.white)
        for x, header in zip(columns, headers, strict=True):
            self.draw_text(header, x + 6, top - 17, font=self.bold, size=8)
        y = top - 25
        for index, row in enumerate(rows):
            self.canvas.setFillColor(colors.HexColor("#F1F6F7") if index % 2 == 0 else colors.white)
            self.canvas.rect(MARGIN, y - 22, sum(widths), 22, fill=1, stroke=0)
            area = row[1] if self.rtl else row[0]
            evidence = row[3] if self.rtl else row[2]
            self.canvas.setFillColor(INK)
            area_column = columns[2] if self.rtl else columns[0]
            status_column = columns[0] if self.rtl else columns[2]
            self.draw_text(area, area_column + 6, y - 15, font=self.regular, size=7.4)
            self.draw_text(evidence, columns[1] + 6, y - 15, font=self.regular, size=7.4)
            status = row[4]
            self.canvas.setFillColor(
                GREEN if status == "PASS" else WARNING if status == "BLOCKED" else RED
            )
            self.draw_text(status, status_column + 6, y - 15, font=self.bold, size=7.4)
            y -= 22
        self.y = y - 4
        self.figure_caption(
            "Table 1. Verification is scoped to retained evidence; hardware skips are not passes.",
            "جدول ۱. صحه گذاری فقط بر شاهد نگهداری شده است و رد شدن آزمون سخت افزار موفقیت نیست.",
        )

    def directive(self, value: str) -> None:
        actions = {
            "ARCHITECTURE": self.architecture,
            "DETECTION_METRICS": self.detection_metrics,
            "BOARD": self.board,
            "VERIFICATION": self.verification,
        }
        action = actions.get(value)
        if action is None:
            raise ValueError(f"unsupported report directive: {value}")
        action()

    def build(self) -> None:
        self.cover()
        for section in self.source.sections:
            self.new_page(section.title)
            self.section_heading(section.title)
            for block in section.blocks:
                if block.kind == "paragraph":
                    self.paragraph(block.value)
                elif block.kind == "bullet":
                    self.paragraph(block.value, bullet=True)
                else:
                    self.directive(block.value)
        self.finish_page()
        self.canvas.save()


def build_hardware_review_pdf() -> None:
    design = json.loads((ROOT / "hardware/design.json").read_text())
    output = ROOT / "hardware/fabrication/iiot-monitor-schematic-review.pdf"
    width, height = landscape(A4)
    canvas = Canvas(str(output), pagesize=(width, height), pageCompression=1, invariant=1)
    canvas.setTitle("IIoT carrier connectivity review - NOT A KICAD EXPORT")
    canvas.setAuthor("Amin Zoroufi <aminn.zoroufi@gmail.com>")
    components = design["components"]
    per_page = 14
    for page_start in range(0, len(components), per_page):
        canvas.setFillColor(RED)
        canvas.rect(0, height - 34, width, 34, fill=1, stroke=0)
        canvas.setFillColor(colors.white)
        canvas.setFont("Helvetica-Bold", 13)
        canvas.drawString(
            28, height - 23, "CONNECTIVITY REVIEW - NOT KICAD SCHEMATIC PDF - NOT FOR FABRICATION"
        )
        canvas.setFillColor(INK)
        canvas.setFont("Helvetica", 7)
        canvas.drawRightString(width - 28, 20, f"A0-UNVERIFIED | page {page_start // per_page + 1}")
        y = height - 62
        for component in components[page_start : page_start + per_page]:
            canvas.setStrokeColor(ACCENT)
            canvas.setFillColor(PALE)
            canvas.roundRect(28, y - 28, 150, 30, 4, fill=1, stroke=1)
            canvas.setFillColor(INK)
            canvas.setFont("Helvetica-Bold", 8)
            canvas.drawString(34, y - 10, f"{component['ref']}  {component['value']}")
            canvas.setFont("Helvetica", 6.5)
            canvas.drawString(34, y - 22, str(component["mpn"])[:35])
            pin_text = " | ".join(f"{pin}:{net}" for pin, net in component["pins"].items())
            chunks = [pin_text[index : index + 95] for index in range(0, len(pin_text), 95)]
            canvas.setFont("Helvetica", 6.2)
            canvas.drawString(190, y - 10, chunks[0] if chunks else "")
            if len(chunks) > 1:
                canvas.drawString(190, y - 21, chunks[1])
            y -= 36
        canvas.showPage()
    canvas.save()


def register_fonts() -> None:
    if not REGULAR_FONT.is_file() or not BOLD_FONT.is_file():
        raise FileNotFoundError("bundled Noto Sans Arabic fonts are missing")
    pdfmetrics.registerFont(TTFont("NotoLatin", str(REGULAR_FONT)))
    pdfmetrics.registerFont(TTFont("NotoLatinBold", str(BOLD_FONT)))
    pdfmetrics.registerFont(TTFont("NotoArabic", str(REGULAR_FONT)))
    pdfmetrics.registerFont(TTFont("NotoArabicBold", str(BOLD_FONT)))


def write_checksum_manifest() -> None:
    lines = []
    for path in (EN_OUTPUT, FA_OUTPUT, HARDWARE_REVIEW_OUTPUT):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        lines.append(f"{digest}  {path.relative_to(ROOT)}")
    CHECKSUM_MANIFEST.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    register_fonts()
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    Report(EN_OUTPUT, parse_markdown(EN_SOURCE), rtl=False).build()
    Report(FA_OUTPUT, parse_markdown(FA_SOURCE), rtl=True).build()
    build_hardware_review_pdf()
    write_checksum_manifest()
    print(f"built {EN_OUTPUT.relative_to(ROOT)}")
    print(f"built {FA_OUTPUT.relative_to(ROOT)}")
    print("built hardware/fabrication/iiot-monitor-schematic-review.pdf (review only)")
    print(f"wrote {CHECKSUM_MANIFEST.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
