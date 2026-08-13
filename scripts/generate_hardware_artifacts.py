#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Amin Zoroufi <aminn.zoroufi@gmail.com>
# SPDX-License-Identifier: LicenseRef-Portfolio-Source-Available
"""Generate review artifacts from the canonical unverified hardware design."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parents[1]
DESIGN_PATH = ROOT / "hardware/design.json"


def load_design() -> dict[str, Any]:
    value = json.loads(DESIGN_PATH.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("hardware design root must be an object")
    return value


def write(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]+", "_", value).strip("_")


def all_nets(design: dict[str, Any]) -> list[str]:
    names = set(str(item) for item in design["nets"])
    for component in design["components"]:
        for name in component["pins"].values():
            if name not in {"NC", "ALERT_NC"}:
                names.add(str(name))
    return sorted(names)


def generate_bom(design: dict[str, Any]) -> None:
    grouped: dict[tuple[str, ...], list[str]] = defaultdict(list)
    fields = ("manufacturer", "mpn", "value", "package", "rating", "role")
    for item in design["components"]:
        grouped[tuple(str(item[field]) for field in fields)].append(str(item["ref"]))
    path = ROOT / "hardware/bom/bom.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        output = csv.writer(stream, lineterminator="\n")
        output.writerow(
            [
                "references",
                "quantity",
                "manufacturer",
                "manufacturer_part_number",
                "value",
                "package",
                "rating",
                "role",
                "sourcing_note",
            ]
        )
        for key, refs in sorted(grouped.items(), key=lambda row: row[1][0]):
            manufacturer, mpn, value, package, rating, role = key
            output.writerow(
                [
                    " ".join(sorted(refs)),
                    len(refs),
                    manufacturer,
                    mpn,
                    value,
                    package,
                    rating,
                    role,
                    "Verify lifecycle, authorized source, stock, and current datasheet before build",
                ]
            )


def generate_positions(design: dict[str, Any]) -> None:
    path = ROOT / "hardware/fabrication/iiot-monitor-all-pos.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        output = csv.writer(stream, lineterminator="\n")
        output.writerow(["Ref", "Val", "Package", "PosX(mm)", "PosY(mm)", "Rot(deg)", "Side"])
        for item in design["components"]:
            output.writerow(
                [
                    item["ref"],
                    item["value"],
                    item["package"],
                    item["x"],
                    item["y"],
                    item["rotation"],
                    "top",
                ]
            )


def symbol_definition(component: dict[str, Any]) -> str:
    name = safe_name(str(component["value"]))
    pins = list(component["pins"].items())
    half = math.ceil(len(pins) / 2)
    body_half_height = max(300, half * 60)
    lines = [
        f"# {name}",
        "#",
        f"DEF {name} {component['ref'][0]} 0 40 Y Y 1 F N",
        f'F0 "{component["ref"]}" 0 {body_half_height + 150} 50 H V C CNN',
        f'F1 "{component["value"]}" 0 {-body_half_height - 150} 50 H V C CNN',
        "DRAW",
        f"S -300 {body_half_height} 300 {-body_half_height} 0 1 10 f",
    ]
    for index, (number, net) in enumerate(pins):
        side_index = index if index < half else index - half
        y = body_half_height - 100 - side_index * 120
        if index < half:
            lines.append(f"X {safe_name(str(net))} {number} -500 {y} 200 R 40 40 1 1 B")
        else:
            lines.append(f"X {safe_name(str(net))} {number} 500 {y} 200 L 40 40 1 1 B")
    lines.extend(["ENDDRAW", "ENDDEF", "#"])
    return "\n".join(lines)


def generate_legacy_schematic(design: dict[str, Any]) -> None:
    unique: dict[str, dict[str, Any]] = {}
    for component in design["components"]:
        unique.setdefault(safe_name(str(component["value"])), component)
    library = ["EESchema-LIBRARY Version 2.4", "#encoding utf-8", "#"]
    library.extend(symbol_definition(component) for component in unique.values())
    library.append("#End Library")
    write(ROOT / "hardware/kicad/iiot-monitor-cache.lib", "\n".join(library) + "\n")

    schematic = [
        "EESchema Schematic File Version 4",
        "LIBS:iiot-monitor-cache",
        "EELAYER 29 0",
        "EELAYER END",
        "$Descr A3 16535 11693",
        "encoding utf-8",
        "Sheet 1 1",
        f'Title "{design["title"]}"',
        'Date "2026-08-11"',
        f'Rev "{design["revision"]}"',
        f'Comp "{design["author"]} <{design["email"]}>"',
        'Comment1 "EXTRA-LOW-VOLTAGE DEMONSTRATOR ONLY - NO MAINS"',
        'Comment2 "UNVERIFIED: import into KiCad 10, run ERC, and review before layout use"',
        "$EndDescr",
        "Text Notes 700 450 0    100  ~ 20",
        str(design["safety_note"]),
    ]
    for index, component in enumerate(design["components"]):
        column = index % 5
        row = index // 5
        x = 1600 + column * 3100
        y = 1300 + row * 1200
        name = safe_name(str(component["value"]))
        identifier = f"6{index + 1:07d}"
        schematic.extend(
            [
                "$Comp",
                f"L iiot-monitor-cache:{name} {component['ref']}",
                f"U 1 1 {identifier}",
                f"P {x} {y}",
                f'F 0 "{component["ref"]}" H {x} {y - 120} 50  0000 C CNN',
                f'F 1 "{component["value"]}" H {x} {y + 120} 50  0000 C CNN',
                f'F 2 "Custom:{component["package"]}" H {x} {y} 50  0001 C CNN',
                f'F 3 "{component["mpn"]}" H {x} {y} 50  0001 C CNN',
                f"\t1    {x} {y}",
                "\t1    0    0    -1",
                "$EndComp",
            ]
        )
        pins = list(component["pins"].items())
        half = math.ceil(len(pins) / 2)
        body_half_height = max(300, half * 60)
        for pin_index, (_, net) in enumerate(pins):
            side_index = pin_index if pin_index < half else pin_index - half
            pin_y = y + body_half_height - 100 - side_index * 120
            pin_x = x - 500 if pin_index < half else x + 500
            schematic.extend([f"Text Label {pin_x} {pin_y} 0    40   ~ 0", str(net)])
    schematic.extend(
        [
            "Text Notes 700 11100 0    60   ~ 12",
            "Labels define electrical nets. Component pin numbering and ratings require KiCad ERC and datasheet review.",
            "$EndSCHEMATC",
        ]
    )
    write(ROOT / "hardware/kicad/iiot-monitor.sch", "\n".join(schematic) + "\n")


def pad_lines(component: dict[str, Any], net_numbers: dict[str, int]) -> list[str]:
    pins = list(component["pins"].items())
    pitch = min(2.0, max(0.7, float(component["height"]) / max(len(pins) // 2, 1)))
    half = math.ceil(len(pins) / 2)
    lines: list[str] = []
    through_hole = any(
        key in str(component["package"])
        for key in ("TerminalBlock", "PinHeader", "Relay_THT", "TestPoint")
    )
    for index, (number, net) in enumerate(pins):
        side_index = index if index < half else index - half
        x = -float(component["width"]) / 2 if index < half else float(component["width"]) / 2
        y = (side_index - (half - 1) / 2) * pitch
        if through_hole:
            lines.append(
                f'    (pad "{number}" thru_hole circle (at {x:.3f} {y:.3f}) '
                f'(size 1.8 1.8) (drill 1.0) (layers "*.Cu" "*.Mask") '
                f'(net {net_numbers.get(str(net), 0)} "{net}"))'
            )
        else:
            lines.append(
                f'    (pad "{number}" smd rect (at {x:.3f} {y:.3f}) '
                f'(size 1.2 0.7) (layers "F.Cu" "F.Paste" "F.Mask") '
                f'(net {net_numbers.get(str(net), 0)} "{net}"))'
            )
    return lines


def generate_pcb(design: dict[str, Any]) -> None:
    nets = all_nets(design)
    net_numbers = {name: index + 1 for index, name in enumerate(nets)}
    board = design["board"]
    lines = [
        "(kicad_pcb (version 20240108) (generator pcbnew)",
        "  (general (thickness 1.6))",
        '  (paper "A4")',
        "  (layers",
        '    (0 "F.Cu" signal)',
        '    (31 "B.Cu" signal)',
        '    (36 "B.SilkS" user "b.silkscreen")',
        '    (37 "F.SilkS" user "f.silkscreen")',
        '    (44 "Edge.Cuts" user)',
        "  )",
        "  (setup (pad_to_mask_clearance 0))",
        '  (net 0 "")',
    ]
    lines.extend(f'  (net {number} "{name}")' for name, number in net_numbers.items())
    for component in design["components"]:
        x = 20 + float(component["x"])
        y = 20 + float(component["y"])
        width = float(component["width"])
        height = float(component["height"])
        lines.extend(
            [
                f'  (footprint "Custom:{component["package"]}" (layer "F.Cu")',
                f"    (at {x:.3f} {y:.3f} {component['rotation']})",
                f'    (property "Reference" "{component["ref"]}" (at 0 {-height / 2 - 1:.3f} 0) (layer "F.SilkS"))',
                f'    (property "Value" "{component["value"]}" (at 0 {height / 2 + 1:.3f} 0) (layer "F.Fab"))',
                f'    (fp_rect (start {-width / 2:.3f} {-height / 2:.3f}) (end {width / 2:.3f} {height / 2:.3f}) (stroke (width 0.25) (type default)) (fill none) (layer "F.SilkS"))',
            ]
        )
        lines.extend(pad_lines(component, net_numbers))
        lines.append("  )")
    for index, (x, y) in enumerate(board["mounting_holes"], start=1):
        lines.extend(
            [
                '  (footprint "MountingHole:MountingHole_3.2mm_M3" (layer "F.Cu")',
                f"    (at {20 + x:.3f} {20 + y:.3f})",
                f'    (property "Reference" "H{index}" (at 0 -4 0) (layer "F.SilkS"))',
                '    (fp_circle (center 0 0) (end 3 0) (stroke (width 0.3) (type default)) (fill none) (layer "F.SilkS"))',
                '    (pad "" np_thru_hole circle (at 0 0) (size 3.2 3.2) (drill 3.2) (layers "*.Cu" "*.Mask"))',
                "  )",
            ]
        )
    lines.extend(
        [
            f'  (gr_rect (start 20 20) (end {20 + board["width"]} {20 + board["height"]}) (stroke (width 0.1) (type default)) (fill none) (layer "Edge.Cuts"))',
            f'  (gr_text "{design["title"]} {design["revision"]}" (at 70 23) (layer "F.SilkS"))',
            '  (gr_text "SELV/PELV ONLY - NO MAINS - UNVERIFIED" (at 70 87) (layer "F.SilkS"))',
            ")",
        ]
    )
    write(ROOT / "hardware/kicad/iiot-monitor.kicad_pcb", "\n".join(lines) + "\n")
    project = {
        "board": {"design_settings": {"defaults": {"board_outline_line_width": 0.1}}},
        "cvpcb": {},
        "erc": {},
        "libraries": {},
        "meta": {"filename": "iiot-monitor.kicad_pro", "version": 1},
        "net_settings": {},
        "pcbnew": {},
        "schematic": {},
        "text_variables": {
            "AUTHOR": f"{design['author']} <{design['email']}>",
            "SAFETY": design["safety_note"],
        },
    }
    write(
        ROOT / "hardware/kicad/iiot-monitor.kicad_pro",
        json.dumps(project, indent=2, sort_keys=True) + "\n",
    )


class StepBuilder:
    def __init__(self) -> None:
        self.entities: list[str] = []

    def add(self, expression: str) -> int:
        self.entities.append(expression)
        return len(self.entities)

    def box(self, name: str, x: float, y: float, z: float, dx: float, dy: float, dz: float) -> None:
        coordinates = (
            (x, y, z),
            (x + dx, y, z),
            (x + dx, y + dy, z),
            (x, y + dy, z),
            (x, y, z + dz),
            (x + dx, y, z + dz),
            (x + dx, y + dy, z + dz),
            (x, y + dy, z + dz),
        )
        points = [
            self.add(f"CARTESIAN_POINT('',({px:.4f},{py:.4f},{pz:.4f}))")
            for px, py, pz in coordinates
        ]
        faces: list[int] = []
        for indices in (
            (0, 3, 2, 1),
            (4, 5, 6, 7),
            (0, 1, 5, 4),
            (1, 2, 6, 5),
            (2, 3, 7, 6),
            (3, 0, 4, 7),
        ):
            loop = self.add("POLY_LOOP('',(" + ",".join(f"#{points[i]}" for i in indices) + "))")
            bound = self.add(f"FACE_OUTER_BOUND('',#{loop},.T.)")
            faces.append(self.add(f"FACE('',(#{bound}))"))
        shell = self.add("CLOSED_SHELL('',(" + ",".join(f"#{face}" for face in faces) + "))")
        self.add(f"FACETED_BREP('{name}',#{shell})")

    def content(self, filename: str) -> str:
        data = "\n".join(f"#{index}={value};" for index, value in enumerate(self.entities, start=1))
        return (
            "ISO-10303-21;\nHEADER;\nFILE_DESCRIPTION(('Project-authored engineering envelope'),'2;1');\n"
            f"FILE_NAME('{filename}','2026-08-11T00:00:00Z',('Amin Zoroufi'),(''),'', '', '');\n"
            "FILE_SCHEMA(('CONFIG_CONTROL_DESIGN'));\nENDSEC;\nDATA;\n"
            f"{data}\nENDSEC;\nEND-ISO-10303-21;\n"
        )


def box_triangles(
    x: float, y: float, z: float, dx: float, dy: float, dz: float
) -> list[tuple[tuple[float, float, float], ...]]:
    p = (
        (x, y, z),
        (x + dx, y, z),
        (x + dx, y + dy, z),
        (x, y + dy, z),
        (x, y, z + dz),
        (x + dx, y, z + dz),
        (x + dx, y + dy, z + dz),
        (x, y + dy, z + dz),
    )
    quads = ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7))
    return [(p[a], p[b], p[c]) for a, b, c, d in quads for (a, b, c) in ((a, b, c), (a, c, d))]


def stl(name: str, boxes: list[tuple[float, float, float, float, float, float]]) -> str:
    lines = [f"solid {name}"]
    for box in boxes:
        for triangle in box_triangles(*box):
            lines.append("  facet normal 0 0 0\n    outer loop")
            lines.extend(f"      vertex {x:.4f} {y:.4f} {z:.4f}" for x, y, z in triangle)
            lines.append("    endloop\n  endfacet")
    lines.append(f"endsolid {name}")
    return "\n".join(lines) + "\n"


def generate_models_and_enclosure(design: dict[str, Any]) -> None:
    model_paths: dict[str, Path] = {}
    for model in design["engineering_models"]:
        width, height, depth = (float(value) for value in model["dimensions"])
        builder = StepBuilder()
        builder.box(str(model["name"]), 0, 0, 0, width, height, depth)
        path = ROOT / "hardware/3d-models" / f"{model['name']}.step"
        write(path, builder.content(path.name))
        model_paths[str(model["name"])] = path

    board = design["board"]
    assembly = StepBuilder()
    assembly.box("PCB", 0, 0, 0, board["width"], board["height"], board["thickness"])
    for component in design["components"]:
        assembly.box(
            f"{component['ref']}-{safe_name(str(component['value']))}",
            float(component["x"]) - float(component["width"]) / 2,
            float(component["y"]) - float(component["height"]) / 2,
            float(board["thickness"]),
            float(component["width"]),
            float(component["height"]),
            3.0 if component.get("model") is None else 6.0,
        )
    board_step = ROOT / "hardware/fabrication/iiot-monitor-board-engineering-envelope.step"
    write(board_step, assembly.content(board_step.name))

    enclosure_width = float(board["width"]) + 8
    enclosure_depth = float(board["height"]) + 8
    wall = 2.4
    floor = 3.0
    height = 28.0
    base_boxes = [
        (0, 0, 0, enclosure_width, enclosure_depth, floor),
        (0, 0, floor, wall, enclosure_depth, height),
        (enclosure_width - wall, 0, floor, wall, enclosure_depth, height),
        (wall, 0, floor, enclosure_width - 2 * wall, wall, height),
        (wall, enclosure_depth - wall, floor, enclosure_width - 2 * wall, wall, height),
    ]
    lid_boxes = [(0, 0, 0, enclosure_width, enclosure_depth, 2.4)]
    write(ROOT / "hardware/enclosure/iiot-enclosure-base.stl", stl("iiot_base", base_boxes))
    write(ROOT / "hardware/enclosure/iiot-enclosure-lid.stl", stl("iiot_lid", lid_boxes))
    enclosure_step = StepBuilder()
    for index, box in enumerate(base_boxes):
        enclosure_step.box(f"base-{index}", *box)
    enclosure_step.box("lid-exploded", 0, 0, height + 12, enclosure_width, enclosure_depth, 2.4)
    enclosure_step_path = ROOT / "hardware/enclosure/iiot-enclosure-assembly.step"
    write(enclosure_step_path, enclosure_step.content(enclosure_step_path.name))

    macro = f"""# FreeCAD 1.x parametric rebuild script; generated from hardware/design.json
import FreeCAD as App
import Part

doc = App.newDocument("IIoT_Enclosure")
width = {enclosure_width}
depth = {enclosure_depth}
wall = {wall}
floor = {floor}
height = {height}
outer = Part.makeBox(width, depth, height + floor)
inner = Part.makeBox(width - 2 * wall, depth - 2 * wall, height + 1, App.Vector(wall, wall, floor))
base_shape = outer.cut(inner)
base = doc.addObject("PartDesign::Feature", "Base")
base.Label = "Parametric enclosure base"
base.Shape = base_shape
lid = doc.addObject("PartDesign::Feature", "Lid")
lid.Label = "Exploded lid"
lid.Shape = Part.makeBox(width, depth, 2.4, App.Vector(0, 0, height + 12))
doc.recompute()
doc.saveAs(App.getUserAppDataDir() + "iiot-enclosure.FCStd")
Part.export([base, lid], App.getUserAppDataDir() + "iiot-enclosure-assembly.step")
"""
    write(ROOT / "hardware/enclosure/iiot-enclosure.FCMacro", macro)

    provenance = ROOT / "hardware/model-provenance.csv"
    with provenance.open("w", newline="", encoding="utf-8") as stream:
        output = csv.writer(stream, lineterminator="\n")
        output.writerow(
            [
                "file",
                "applies_to",
                "kind",
                "source",
                "source_url",
                "license",
                "retrieval_date",
                "sha256",
            ]
        )
        for model in design["engineering_models"]:
            path = model_paths[str(model["name"])]
            output.writerow(
                [
                    path.relative_to(ROOT),
                    model["applies_to"],
                    model["kind"],
                    model["source"],
                    model["source_url"],
                    model["license"],
                    model["retrieved"],
                    sha256(path),
                ]
            )


def gerber_header(file_function: str) -> list[str]:
    return [
        "G04 Generated review artifact; NOT RELEASED FOR FABRICATION*",
        "%FSLAX46Y46*%",
        "%MOMM*%",
        f"%TF.FileFunction,{file_function}*%",
        "%TF.Part,Single*%",
        "%ADD10C,0.200000*%",
        "D10*",
    ]


def generate_fabrication_review(design: dict[str, Any]) -> None:
    board = design["board"]
    width = int(float(board["width"]) * 1_000_000)
    height = int(float(board["height"]) * 1_000_000)
    outline = gerber_header("Profile,NP")
    outline.extend(
        [
            "X0Y0D02*",
            f"X{width}Y0D01*",
            f"X{width}Y{height}D01*",
            f"X0Y{height}D01*",
            "X0Y0D01*",
            "M02*",
        ]
    )
    write(ROOT / "hardware/fabrication/iiot-monitor-Edge_Cuts.gm1", "\n".join(outline) + "\n")
    for filename, function in (
        ("iiot-monitor-F_Cu.gtl", "Copper,L1,Top"),
        ("iiot-monitor-B_Cu.gbl", "Copper,L2,Bot"),
        ("iiot-monitor-F_Mask.gts", "Soldermask,Top"),
        ("iiot-monitor-B_Mask.gbs", "Soldermask,Bot"),
        ("iiot-monitor-F_Silkscreen.gto", "Legend,Top"),
    ):
        content = gerber_header(function)
        content.extend(
            ["G04 Layer intentionally contains no approved production geometry*", "M02*"]
        )
        write(ROOT / "hardware/fabrication" / filename, "\n".join(content) + "\n")
    drills = ["M48", "; DRILL file - review only; NOT RELEASED", "METRIC,TZ", "T1C3.200", "%", "T1"]
    for x, y in board["mounting_holes"]:
        drills.append(f"X{float(x):.3f}Y{float(y):.3f}")
    drills.extend(["M30", ""])
    write(ROOT / "hardware/fabrication/iiot-monitor-PTH.drl", "\n".join(drills))
    status = {
        "schema_version": 1,
        "revision": design["revision"],
        "fabrication_release_approved": False,
        "kicad_erc": "NOT_RUN_TOOL_UNAVAILABLE",
        "kicad_drc": "NOT_RUN_TOOL_UNAVAILABLE",
        "routing_status": "UNROUTED_REVIEW_PLACEMENT",
        "generated_outputs": "review-only geometry generated from hardware/design.json",
        "required_before_fabrication": [
            "import and save the legacy schematic in KiCad 10",
            "review symbols, footprints, pin numbers, ratings, and net labels against current datasheets",
            "route power, signals, differential bus, and planes",
            "run ERC and DRC with zero unexplained violations",
            "regenerate all fabrication and 3D outputs using kicad-cli",
            "independent electrical and safety review",
        ],
    }
    write(
        ROOT / "hardware/fabrication/fabrication-status.json",
        json.dumps(status, indent=2, sort_keys=True) + "\n",
    )
    report = (
        "Status: NOT RUN\nTool: kicad-cli 10.0.4\nReason: tool is unavailable in the execution environment.\n"
        "This file is not a passing report and must be replaced by actual tool output.\n"
    )
    write(ROOT / "hardware/fabrication/erc-report.txt", report)
    write(ROOT / "hardware/fabrication/drc-report.txt", report)


def generate_svgs(design: dict[str, Any]) -> None:
    board = design["board"]
    scale = 8
    margin = 50
    width = float(board["width"]) * scale
    height = float(board["height"]) * scale
    items = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width + 2 * margin}" height="{height + 120}" viewBox="0 0 {width + 2 * margin} {height + 120}">',
        '<rect width="100%" height="100%" fill="#0b1116"/>',
        f'<rect x="{margin}" y="{margin}" width="{width}" height="{height}" rx="8" fill="#164d3a" stroke="#7ee0b0" stroke-width="3"/>',
        f'<text x="{margin}" y="28" fill="#eef7f1" font-family="sans-serif" font-size="18">{design["title"]} · {design["revision"]} · review placement</text>',
    ]
    for component in design["components"]:
        x = margin + (float(component["x"]) - float(component["width"]) / 2) * scale
        y = margin + (float(component["y"]) - float(component["height"]) / 2) * scale
        w = max(float(component["width"]) * scale, 12)
        h = max(float(component["height"]) * scale, 10)
        items.extend(
            [
                f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" fill="#d7e5dc" stroke="#16231c"/>',
                f'<text x="{x + 2:.1f}" y="{y + min(h - 2, 12):.1f}" fill="#101915" font-family="monospace" font-size="9">{component["ref"]}</text>',
            ]
        )
    items.extend(
        [
            f'<text x="{margin}" y="{height + 78}" fill="#ffcf70" font-family="sans-serif" font-size="16">100 × 70 × 1.6 mm · UNROUTED · NOT RELEASED FOR FABRICATION</text>',
            f'<text x="{margin}" y="{height + 102}" fill="#ff8f8f" font-family="sans-serif" font-size="15">{design["safety_note"]}</text>',
            "</svg>",
        ]
    )
    write(ROOT / "hardware/fabrication/board-placement-review.svg", "\n".join(items) + "\n")

    enclosure_width = float(board["width"]) + 8
    enclosure_depth = float(board["height"]) + 8
    assembly = f"""<svg xmlns="http://www.w3.org/2000/svg" width="960" height="600" viewBox="0 0 960 600">
<rect width="960" height="600" fill="#0b1116"/>
<text x="50" y="42" fill="#eef7f1" font-family="sans-serif" font-size="24">Parametric enclosure assembly · engineering render</text>
<path d="M180 330 L600 330 L760 430 L340 430 Z" fill="#284b63" stroke="#86c5da" stroke-width="3"/>
<path d="M180 330 L180 490 L340 575 L340 430 Z" fill="#183447" stroke="#86c5da" stroke-width="3"/>
<path d="M340 430 L760 430 L760 520 L340 575 Z" fill="#1d3f54" stroke="#86c5da" stroke-width="3"/>
<path d="M250 245 L570 245 L695 320 L375 320 Z" fill="#19624a" stroke="#7ee0b0" stroke-width="3"/>
<text x="390" y="290" fill="#eef7f1" font-family="sans-serif" font-size="18">PCB 100 × 70 mm</text>
<path d="M150 90 L630 90 L800 190 L320 190 Z" fill="#b9c9d2" fill-opacity="0.72" stroke="#eef7f1" stroke-width="3"/>
<text x="350" y="145" fill="#14212a" font-family="sans-serif" font-size="18">Exploded lid</text>
<line x1="700" y1="200" x2="700" y2="310" stroke="#ffcf70" stroke-width="3" stroke-dasharray="8 8"/>
<text x="720" y="260" fill="#ffcf70" font-family="sans-serif" font-size="16">assembly axis</text>
<text x="50" y="555" fill="#eef7f1" font-family="sans-serif" font-size="17">Internal envelope {enclosure_width:.1f} × {enclosure_depth:.1f} mm; base wall 2.4 mm; no thermal/IP rating claimed.</text>
</svg>"""
    write(ROOT / "hardware/enclosure/enclosure-assembly-review.svg", assembly + "\n")


def validate(design: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    refs = [str(item["ref"]) for item in design["components"]]
    if len(refs) != len(set(refs)):
        errors.append("component references must be unique")
    required_roles = (
        "relay coil driver",
        "flyback",
        "RS-485 transient",
        "termination",
        "decoupling",
        "current shunt",
    )
    roles = " ".join(str(item["role"]) for item in design["components"])
    errors.extend(f"missing required role: {role}" for role in required_roles if role not in roles)
    for item in design["components"]:
        if not all(
            str(item.get(field, "")).strip()
            for field in ("mpn", "manufacturer", "package", "rating", "role")
        ):
            errors.append(f"{item.get('ref', '?')} has incomplete procurement metadata")
    if design.get("fabrication_release_approved") is not False:
        errors.append("unverified A0 hardware must not be fabrication-approved")
    status_path = ROOT / "hardware/fabrication/fabrication-status.json"
    if not status_path.exists():
        errors.append("fabrication status is missing")
    else:
        status = json.loads(status_path.read_text(encoding="utf-8"))
        if status.get("fabrication_release_approved") is not False:
            errors.append("fabrication status incorrectly approves release")
    provenance_path = ROOT / "hardware/model-provenance.csv"
    if not provenance_path.exists():
        errors.append("3D model provenance is missing")
    else:
        with provenance_path.open(encoding="utf-8") as stream:
            for row in csv.DictReader(stream):
                model_path = ROOT / row["file"]
                if not model_path.is_file() or sha256(model_path) != row["sha256"]:
                    errors.append(f"model checksum mismatch: {row['file']}")
                if "engineering envelope" not in row["kind"]:
                    errors.append(f"model kind is not explicit: {row['file']}")
    return errors


def generate() -> None:
    design = load_design()
    generate_bom(design)
    generate_positions(design)
    generate_legacy_schematic(design)
    generate_pcb(design)
    generate_models_and_enclosure(design)
    generate_fabrication_review(design)
    generate_svgs(design)
    errors = validate(design)
    if errors:
        raise SystemExit("\n".join(errors))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="validate existing generated files")
    args = parser.parse_args()
    design = load_design()
    if args.check:
        errors = validate(design)
        if errors:
            raise SystemExit("\n".join(errors))
        print("hardware static/provenance checks passed; ERC/DRC remain NOT_RUN")
    else:
        generate()
        print("generated unverified hardware review artifacts from hardware/design.json")


if __name__ == "__main__":
    main()
