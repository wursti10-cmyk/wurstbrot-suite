from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import venv
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VERSION = "1.0.0"
PEP440_VERSION = "1.0.0"
FORBIDDEN_RC_MARKERS = (
    "1.0.0-rc.1",
    "1.0.0-rc.2",
    "1.0.0rc1",
    "1.0.0rc2",
    "1.0.0-RC.1",
    "1.0.0-RC.2",
    "RC.1",
    "RC.2",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate built Stable artifacts and clean install.")
    parser.add_argument("--dist", type=Path, default=ROOT / "dist")
    parser.add_argument("--output", type=Path, default=ROOT / "build" / "release")
    parser.add_argument("--node", default=shutil.which("node"))
    return parser.parse_args()


def require_members(names: set[str], suffixes: tuple[str, ...]) -> list[str]:
    return [suffix for suffix in suffixes if not any(name.endswith(suffix) for name in names)]


def stale_markers(text: str) -> list[str]:
    return [marker for marker in FORBIDDEN_RC_MARKERS if marker in text]


def archive_stale_members(
    archive: zipfile.ZipFile | tarfile.TarFile,
    members: list[str],
) -> dict[str, list[str]]:
    stale: dict[str, list[str]] = {}
    for name in members:
        try:
            if isinstance(archive, zipfile.ZipFile):
                content = archive.read(name)
            else:
                extracted = archive.extractfile(name)
                if extracted is None:
                    continue
                content = extracted.read()
            markers = stale_markers(content.decode("utf-8"))
        except (KeyError, UnicodeDecodeError):
            continue
        if markers:
            stale[name] = markers
    return stale


def run(command: tuple[str, ...], *, cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, env=env, check=False, capture_output=True, text=True)


def main() -> int:
    args = parse_args()
    dist = args.dist.resolve()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    wheel = next(iter(dist.glob(f"wurstbrot_suite-{PEP440_VERSION}-*.whl")), None)
    sdist = next(iter(dist.glob(f"wurstbrot_suite-{PEP440_VERSION}.tar.gz")), None)
    browser = dist / f"wurstbrot-suite-{VERSION}-browser.zip"
    checksums = dist / "SHA256SUMS.txt"
    blockers: list[str] = []
    details: dict[str, object] = {}
    if not wheel or not sdist or not browser.is_file() or not checksums.is_file():
        raise SystemExit("required release artifacts are missing")

    with zipfile.ZipFile(wheel) as archive:
        wheel_names = set(archive.namelist())
        missing = require_members(
            wheel_names,
            (
                "wurstbrot_core/__init__.py",
                "wurstbrot_core/cli.py",
                "wurstbrot_core/graph_pipeline.py",
                "wurstbrot_core/release_hardening.py",
                "wurstbrot_validator/validator.py",
                ".dist-info/METADATA",
                ".dist-info/entry_points.txt",
            ),
        )
        metadata_name = next(name for name in wheel_names if name.endswith(".dist-info/METADATA"))
        entry_name = next(name for name in wheel_names if name.endswith(".dist-info/entry_points.txt"))
        metadata = archive.read(metadata_name).decode("utf-8")
        entries = archive.read(entry_name).decode("utf-8")
        if f"Version: {PEP440_VERSION}" not in metadata.splitlines():
            missing.append("wheel metadata version")
        if "wurstbrot = wurstbrot_core.cli:main" not in entries:
            missing.append("wheel CLI entry point")
        if missing:
            blockers.append("wheel_content_invalid")
        details["wheelMissing"] = missing
        wheel_text_members = [
            name
            for name in wheel_names
            if name.endswith((".py", ".txt", "/METADATA", "/entry_points.txt"))
        ]
        wheel_stale = archive_stale_members(archive, wheel_text_members)
        if wheel_stale:
            blockers.append("wheel_stale_rc_version")
        details["wheelStaleVersionMembers"] = wheel_stale

    with tarfile.open(sdist, "r:gz") as archive:
        sdist_names = set(archive.getnames())
        missing = require_members(
            sdist_names,
            (
                "/VERSION",
                "/pyproject.toml",
                "/packages/core/wurstbrot_core/graph_pipeline.py",
                "/apps/web/visual-tree-interaction.mjs",
                "/accuracy/acceptance/release_hardening_2.57.1.67.json",
                "/data/samples/WT_Database_2.57.1.67.json",
                "/docs/34_RELEASE_NOTES_1.0.0.md",
                "/specs/GE_CALCULATION_SPEC.md",
            ),
        )
        if any(name.endswith("/scripts/rc2_readiness.py") for name in sdist_names):
            missing.append("obsolete RC.2 readiness script")
        version_name = next(name for name in sdist_names if name.endswith("/VERSION"))
        version_file = archive.extractfile(version_name)
        if version_file is None or version_file.read().decode("utf-8").strip() != VERSION:
            missing.append("sdist VERSION")
        if missing:
            blockers.append("sdist_content_invalid")
        details["sdistMissing"] = missing
        current_sdist_suffixes = (
            "/VERSION",
            "/pyproject.toml",
            "/README.md",
            "/SECURITY.md",
            "/apps/datamine-manager/wurstbrot_converter.py",
            "/apps/ge-calculator/ge_calculator_gui.py",
            "/apps/web/index.html",
            "/apps/web/service-worker.js",
            "/apps/web/visual-tree.mjs",
            "/apps/web/visual-tree-interaction.mjs",
            "/data/samples/WT_Database_2.57.1.67.json",
            "/docs/00_PROJECT_CONTEXT.md",
            "/docs/14_RELEASE_PROCESS.md",
            "/docs/15_AI_CONTEXT.md",
            "/docs/18_FAQ.md",
            "/packages/core/wurstbrot_core/__init__.py",
            "/packages/core/wurstbrot_core/cli.py",
            "/scripts/build_release.py",
            "/scripts/stable_readiness.py",
        )
        current_sdist_members = [
            name for name in sdist_names if name.endswith(current_sdist_suffixes)
        ]
        sdist_stale = archive_stale_members(archive, current_sdist_members)
        if sdist_stale:
            blockers.append("sdist_stale_rc_version")
        details["sdistStaleVersionMembers"] = sdist_stale

    with zipfile.ZipFile(browser) as archive:
        browser_names = set(archive.namelist())
        missing = [
            name
            for name in (
                "index.html",
                "app.js",
                "solver.mjs",
                "visual-tree.mjs",
                "visual-tree-interaction.mjs",
                "service-worker.js",
                "manifest.webmanifest",
                "data/samples/WT_Database_2.57.1.67.json",
            )
            if name not in browser_names
        ]
        index = archive.read("index.html").decode("utf-8")
        if (
            "<title>Wurstbrot GE Calculator 1.0.0</title>" not in index
            or '<p class="eyebrow">WURSTBROT SUITE · 1.0.0</p>' not in index
        ):
            missing.append("browser visible version")
        if missing:
            blockers.append("browser_artifact_invalid")
        details["browserMissing"] = missing
        browser_text_members = [
            name
            for name in browser_names
            if name.endswith((".html", ".js", ".json", ".mjs", ".webmanifest", ".css"))
        ]
        browser_stale = archive_stale_members(archive, browser_text_members)
        if browser_stale:
            blockers.append("browser_stale_rc_version")
        details["browserStaleVersionMembers"] = browser_stale

    expected_checksum_names = {wheel.name, sdist.name, browser.name}
    checksum_entries: dict[str, str] = {}
    checksum_parse_errors: list[str] = []
    for line in checksums.read_text(encoding="utf-8").splitlines():
        digest, separator, name = line.partition("  ")
        if not separator or len(digest) != 64 or name in checksum_entries:
            checksum_parse_errors.append(line)
            continue
        checksum_entries[name] = digest
    checksum_mismatches = {
        path.name: {
            "expected": checksum_entries.get(path.name),
            "actual": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
        for path in (wheel, sdist, browser)
        if checksum_entries.get(path.name) != hashlib.sha256(path.read_bytes()).hexdigest()
    }
    if (
        checksum_parse_errors
        or set(checksum_entries) != expected_checksum_names
        or checksum_mismatches
    ):
        blockers.append("checksums_invalid")
    details["checksumEntries"] = checksum_entries
    details["checksumParseErrors"] = checksum_parse_errors
    details["checksumMismatches"] = checksum_mismatches

    with tempfile.TemporaryDirectory(prefix="wurstbrot-stable-") as temporary:
        temporary_path = Path(temporary)
        environment = os.environ.copy()
        environment.pop("PYTHONPATH", None)
        environment["PYTHONNOUSERSITE"] = "1"
        venv_path = temporary_path / "venv"
        venv.EnvBuilder(with_pip=True, clear=True).create(venv_path)
        python = venv_path / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        executable = venv_path / ("Scripts/wurstbrot.exe" if os.name == "nt" else "bin/wurstbrot")
        install = run(
            (str(python), "-m", "pip", "install", "--no-index", "--no-deps", str(wheel)),
            cwd=temporary_path,
            env=environment,
        )
        if install.returncode:
            blockers.append("wheel_install_failed")
        version = run((str(executable), "--version"), cwd=temporary_path, env=environment)
        if version.returncode or VERSION not in version.stdout:
            blockers.append("installed_cli_version_failed")
        calculation = run(
            (
                str(executable),
                "--database",
                str(ROOT / "data" / "samples" / "WT_Database_2.57.1.67.json"),
                "--start",
                "germ_sdkfz_222",
                "--target",
                "germ_sdkfz_6_2_flak36",
                "--progress",
                "germ_sdkfz_6_2_flak36:1000",
                "--owned-ge",
                "10",
                "--convertible-rp",
                "1000",
                "--sl-discount",
                "30",
            ),
            cwd=temporary_path,
            env=environment,
        )
        if calculation.returncode or not all(token in calculation.stdout for token in ("RP", "GE", "SL")):
            blockers.append("installed_cli_calculation_failed")
        invalid = run(
            (
                str(executable),
                "--database",
                str(ROOT / "data" / "samples" / "WT_Database_2.57.1.67.json"),
                "--start",
                "germ_sdkfz_222",
                "--target",
                "germ_sdkfz_6_2_flak36",
                "--engine",
                "graph-experimental",
                "--progress",
                "germ_sdkfz_6_2_flak36:-1",
            ),
            cwd=temporary_path,
            env=environment,
        )
        if invalid.returncode != 2 or "Ergebnisquelle: keine" not in invalid.stdout:
            blockers.append("installed_cli_invalid_input_failed")
        installed_report = output / "Installed_Wheel_Acceptance_1.0.0.json"
        acceptance = run(
            (
                str(python),
                str(ROOT / "tests" / "installed_wheel_acceptance.py"),
                "--repository",
                str(ROOT),
                "--output",
                str(installed_report),
            ),
            cwd=temporary_path,
            env=environment,
        )
        if acceptance.returncode:
            blockers.append("installed_acceptance_failed")
        details.update(
            {
                "installReturnCode": install.returncode,
                "versionOutput": version.stdout.strip(),
                "calculationReturnCode": calculation.returncode,
                "invalidInputReturnCode": invalid.returncode,
                "installedAcceptanceReturnCode": acceptance.returncode,
            }
        )

        browser_root = temporary_path / "browser"
        with zipfile.ZipFile(browser) as archive:
            archive.extractall(browser_root)
        if not args.node:
            blockers.append("browser_artifact_runtime_unavailable")
        else:
            solver_url = (browser_root / "solver.mjs").resolve().as_uri()
            database_path = browser_root / "data" / "samples" / "WT_Database_2.57.1.67.json"
            browser_code = (
                "import {readFileSync} from 'node:fs';"
                f"import {{calculate,validateDatabase}} from {json.dumps(solver_url)};"
                f"const db=validateDatabase(JSON.parse(readFileSync({json.dumps(str(database_path))},'utf8')));"
                "const result=calculate(db,{startId:'germ_sdkfz_222',targetId:'germ_sdkfz_6_2_flak36',"
                "partialRp:1000,ownedGe:10,convertibleRp:1000,slDiscount:30});"
                "if(!(result.totalRp>=0&&result.totalGe>=0&&result.totalSl>=0))process.exit(1);"
            )
            browser_run = run(
                (str(args.node), "--input-type=module", "--eval", browser_code),
                cwd=browser_root,
                env=environment,
            )
            if browser_run.returncode:
                blockers.append("browser_artifact_runtime_failed")
            details["browserArtifactReturnCode"] = browser_run.returncode

    installed_path = output / "Installed_Wheel_Acceptance_1.0.0.json"
    installed = json.loads(installed_path.read_text(encoding="utf-8")) if installed_path.is_file() else {}
    payload = {
        "schemaVersion": 1,
        "version": VERSION,
        "artifacts": [wheel.name, sdist.name, browser.name, checksums.name],
        "release_build_passed": not any(
            item.endswith(("_content_invalid", "_stale_rc_version"))
            or item == "checksums_invalid"
            for item in blockers
        ),
        "clean_install_passed": not any(item.startswith(("wheel_install", "installed_")) for item in blockers),
        "release_build_acceptance_passed": bool(installed.get("passed")) and not blockers,
        "version_consistent": (
            details.get("versionOutput", "") == f"wurstbrot {VERSION}"
            and not any(item.endswith("_stale_rc_version") for item in blockers)
            and not any(item.endswith("_content_invalid") for item in blockers)
        ),
        "acceptance": installed,
        "blockers": blockers,
        "details": details,
    }
    report_path = output / "Release_Build_Acceptance_1.0.0.json"
    report_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if not blockers else 1


if __name__ == "__main__":
    raise SystemExit(main())
