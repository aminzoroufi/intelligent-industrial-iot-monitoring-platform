# SPDX-FileCopyrightText: 2026 Amin Zoroufi <aminn.zoroufi@gmail.com>
# SPDX-License-Identifier: LicenseRef-Portfolio-Source-Available

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).parents[1]
HARDWARE = ROOT / "hardware"


def test_hardware_design_and_bom_references_are_consistent() -> None:
    design = json.loads((HARDWARE / "design.json").read_text(encoding="utf-8"))
    design_refs = {item["ref"] for item in design["components"]}
    with (HARDWARE / "bom/bom.csv").open(encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    bom_refs = {reference for row in rows for reference in row["references"].split()}
    assert design_refs == bom_refs
    assert design["fabrication_release_approved"] is False
    assert "MAINS" in design["safety_note"]
    assert all(row["manufacturer_part_number"] and row["rating"] for row in rows)


def test_required_protection_and_interface_roles_are_present() -> None:
    design = json.loads((HARDWARE / "design.json").read_text(encoding="utf-8"))
    roles = " ".join(item["role"] for item in design["components"])
    for required in (
        "relay coil driver",
        "flyback diode",
        "RS-485 transient protection",
        "termination",
        "current shunt",
        "decoupling",
    ):
        assert required in roles
    assert {"RS485_A", "RS485_B", "RS485_DE", "RELAY_GATE"}.issubset(design["nets"])


def test_model_provenance_names_engineering_envelopes_and_matches_checksums() -> None:
    with (HARDWARE / "model-provenance.csv").open(encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    assert rows
    for row in rows:
        path = ROOT / row["file"]
        assert path.is_file()
        assert "engineering envelope" in row["kind"]
        assert "not a manufacturer 3D model" in row["license"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == row["sha256"]


def test_fabrication_outputs_cannot_be_mistaken_for_a_release() -> None:
    status = json.loads(
        (HARDWARE / "fabrication/fabrication-status.json").read_text(encoding="utf-8")
    )
    assert status["fabrication_release_approved"] is False
    assert status["kicad_erc"].startswith("NOT_RUN")
    assert status["kicad_drc"].startswith("NOT_RUN")
    assert status["routing_status"] == "UNROUTED_REVIEW_PLACEMENT"
    for report in ("erc-report.txt", "drc-report.txt"):
        contents = (HARDWARE / "fabrication" / report).read_text(encoding="utf-8")
        assert "Status: NOT RUN" in contents
        assert "not a passing report" in contents


def test_editable_sources_and_review_renders_are_present() -> None:
    required = (
        "kicad/iiot-monitor.kicad_pro",
        "kicad/iiot-monitor.kicad_pcb",
        "kicad/iiot-monitor.sch",
        "enclosure/iiot-enclosure.FCMacro",
        "enclosure/iiot-enclosure-base.stl",
        "enclosure/iiot-enclosure-lid.stl",
        "fabrication/board-placement-review.svg",
        "enclosure/enclosure-assembly-review.svg",
    )
    assert all((HARDWARE / relative).is_file() for relative in required)
    pcb = (HARDWARE / "kicad/iiot-monitor.kicad_pcb").read_text(encoding="utf-8")
    schematic = (HARDWARE / "kicad/iiot-monitor.sch").read_text(encoding="utf-8")
    assert "Amin Zoroufi" in pcb or "Amin Zoroufi" in (
        HARDWARE / "kicad/iiot-monitor.kicad_pro"
    ).read_text(encoding="utf-8")
    assert "NO MAINS" in pcb
    assert "Amin Zoroufi" in schematic
