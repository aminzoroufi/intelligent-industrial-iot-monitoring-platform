# SPDX-FileCopyrightText: 2026 Amin Zoroufi <aminn.zoroufi@gmail.com>
# SPDX-License-Identifier: LicenseRef-Portfolio-Source-Available
"""Build and validate the locked runtime dependency/license inventory."""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
from pathlib import Path
from typing import TypedDict

ROOT = Path(__file__).parents[1]
PYTHON_LOCK = ROOT / "requirements/runtime.lock"
CI_LOCK = ROOT / "requirements/ci.lock"
PYTHON_POLICY = ROOT / "requirements/python-license-policy.csv"
NODE_LOCK = ROOT / "web/package-lock.json"
INVENTORY = ROOT / "docs/dependency-license-inventory.csv"

PIN = re.compile(r"^(?P<name>[A-Za-z0-9_.-]+)==(?P<version>[^\s]+)$")
STRONG_COPYLEFT = re.compile(r"(?<!L)GPL-(?:2|3)\.0")
INVALID_LICENSE_MARKERS = ("UNKNOWN", "UNLICENSED", "SEE LICENSE IN")
POLICY_DISPOSITIONS = {"accepted", "reviewed"}
DOCUMENTATION_PACKAGES = {
    "charset-normalizer",
    "cryptography",
    "pdfminer-six",
    "pdfplumber",
    "pillow",
    "pypdf",
    "pypdfium2",
    "reportlab",
}


class PolicyRow(TypedDict):
    package: str
    license_expression: str
    disposition: str
    notes: str


def normalize_package(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def read_python_lock(
    path: Path, *, allow_runtime_include: bool = False
) -> dict[str, tuple[str, str]]:
    packages: dict[str, tuple[str, str]] = {}
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if allow_runtime_include and line == "-r runtime.lock":
            continue
        match = PIN.fullmatch(line)
        if match is None:
            raise ValueError(f"{path}:{line_number}: dependency must be exactly pinned")
        display_name = match.group("name")
        normalized = normalize_package(display_name)
        if normalized in packages:
            raise ValueError(f"duplicate Python dependency: {display_name}")
        packages[normalized] = (display_name, match.group("version"))
    return packages


def read_python_policy() -> dict[str, PolicyRow]:
    policy: dict[str, PolicyRow] = {}
    with PYTHON_POLICY.open(encoding="utf-8", newline="") as source:
        reader = csv.DictReader(source)
        expected = {"package", "license_expression", "disposition", "notes"}
        if set(reader.fieldnames or ()) != expected:
            raise ValueError(f"unexpected columns in {PYTHON_POLICY}")
        for row in reader:
            typed = PolicyRow(
                package=row["package"].strip(),
                license_expression=row["license_expression"].strip(),
                disposition=row["disposition"].strip(),
                notes=row["notes"].strip(),
            )
            normalized = normalize_package(typed["package"])
            if normalized in policy:
                raise ValueError(f"duplicate Python policy row: {typed['package']}")
            validate_license(typed["license_expression"], typed["package"])
            if typed["disposition"] not in POLICY_DISPOSITIONS:
                raise ValueError(f"unapproved disposition for {typed['package']}")
            policy[normalized] = typed
    return policy


def validate_license(expression: str, package: str) -> None:
    upper = expression.upper()
    if not expression or any(marker in upper for marker in INVALID_LICENSE_MARKERS):
        raise ValueError(f"missing or non-specific license for {package}: {expression!r}")
    if "AGPL" in upper or STRONG_COPYLEFT.search(upper):
        raise ValueError(
            f"strong-copyleft dependency requires an explicit policy change: {package}"
        )


def node_package_name(path: str) -> str:
    marker = "node_modules/"
    if marker not in path:
        raise ValueError(f"unexpected npm package path: {path}")
    return path.rsplit(marker, 1)[1]


def build_inventory() -> str:
    runtime_packages = read_python_lock(PYTHON_LOCK)
    ci_packages = read_python_lock(CI_LOCK, allow_runtime_include=True)
    overlap = sorted(set(runtime_packages) & set(ci_packages))
    if overlap:
        raise ValueError(f"CI-only lock duplicates runtime dependencies: {overlap}")
    python_packages = runtime_packages | ci_packages
    python_policy = read_python_policy()
    missing = sorted(set(python_packages) - set(python_policy))
    stale = sorted(set(python_policy) - set(python_packages))
    if missing or stale:
        raise ValueError(f"Python license policy mismatch; missing={missing}, stale={stale}")

    rows: list[tuple[str, str, str, str, str, str, str, str]] = []
    for normalized, (display_name, version) in sorted(python_packages.items()):
        policy = python_policy[normalized]
        if normalized in runtime_packages:
            locked_path = "requirements/runtime.lock"
            scope = "runtime"
        elif normalized in DOCUMENTATION_PACKAGES:
            locked_path = "requirements/ci.lock"
            scope = "documentation"
        else:
            locked_path = "requirements/ci.lock"
            scope = "development"
        rows.append(
            (
                "python",
                locked_path,
                display_name,
                version,
                policy["license_expression"],
                scope,
                policy["disposition"],
                policy["notes"],
            )
        )

    lock = json.loads(NODE_LOCK.read_text(encoding="utf-8"))
    if lock.get("lockfileVersion") != 3:
        raise ValueError("web/package-lock.json must use lockfileVersion 3")
    packages = lock.get("packages")
    if not isinstance(packages, dict):
        raise ValueError("web/package-lock.json has no packages object")
    for package_path, metadata in sorted(packages.items()):
        if not package_path:
            continue
        if not isinstance(metadata, dict):
            raise ValueError(f"invalid npm metadata for {package_path}")
        version = metadata.get("version")
        expression = metadata.get("license")
        if not isinstance(version, str) or not isinstance(expression, str):
            raise ValueError(f"npm package lacks version/license metadata: {package_path}")
        package_name = node_package_name(package_path)
        validate_license(expression, package_name)
        scope = "development" if metadata.get("dev") is True else "runtime"
        if metadata.get("optional") is True:
            scope += "+optional"
        disposition = "reviewed" if any(x in expression for x in ("LGPL", "MPL")) else "accepted"
        rows.append(
            (
                "javascript",
                package_path,
                package_name,
                version,
                expression,
                scope,
                disposition,
                "License metadata recorded in npm lockfile.",
            )
        )

    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(
        (
            "ecosystem",
            "locked_path",
            "package",
            "version",
            "license_expression",
            "scope",
            "disposition",
            "notes",
        )
    )
    writer.writerows(rows)
    return output.getvalue()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true", help="refresh the committed inventory")
    args = parser.parse_args()
    generated = build_inventory()
    if args.write:
        INVENTORY.write_text(generated, encoding="utf-8")
        print(f"wrote {INVENTORY.relative_to(ROOT)}")
        return
    if not INVENTORY.exists() or INVENTORY.read_text(encoding="utf-8") != generated:
        raise SystemExit("dependency/license inventory is absent or stale; run with --write")
    row_count = generated.count("\n") - 1
    print(f"dependency/license inventory passed: {row_count} locked package rows")


if __name__ == "__main__":
    main()
