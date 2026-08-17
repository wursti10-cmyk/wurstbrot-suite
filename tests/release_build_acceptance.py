from __future__ import annotations

import argparse
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
VERSION = "1.0.0-rc.2"
PEP440_VERSION = "1.0.0rc2"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate built RC artifacts and clean install.")
    parser.add_argument("--dist", type=Path, default=ROOT / "dist")
    parser.add_argument("--output", type=Path, default=ROOT / "build" / "release")
    parser.add_argument("--node", default=shutil.which("node"))
    return parser.parse_args()


def require_members(names: set[str], suffixes: tuple[str, ...]) -> list[str]:
    return [suffix for suffix in suffixes if not any(name.endswith(suffix) for name in names)]


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
        if f"Version: {PEP440_VERSION}" not in metadata:
            missing.append("wheel metadata version")
        if "wurstbrot = wurstbrot_core.cli:main" not in entries:
            missing.append("wheel CLI entry point")
        if missing:
            blockers.append("wheel_content_invalid")
        details["wheelMissing"] = missing

    with tarfile.open(sdist, "r:gz") as archive:
        sdist_names = set(archive.getnames())
        missing = require_members(
            sdist_names,
            (
                "/VERSION",
                "/pyproject.toml",
                "/packages/core/wurstbrot_core/graph_pipeline.py",
                "/accuracy/acceptance/release_hardening_2.57.1.67.json",
                "/data/samples/WT_Database_2.57.1.67.json",
                "/docs/33_RELEASE_NOTES_1.0.0_RC2.md",
                "/specs/GE_CALCULATION_SPEC.md",
            ),
        )
        if missing:
            blockers.append("sdist_content_invalid")
        details["sdistMissing"] = missing

    with zipfile.ZipFile(browser) as archive:
        browser_names = set(archive.namelist())
        missing = [
            name
            for name in (
                "index.html",
                "app.js",
                "solver.mjs",
                "service-worker.js",
                "manifest.webmanifest",
                "data/samples/WT_Database_2.57.1.67.json",
            )
            if name not in browser_names
        ]
        index = archive.read("index.html").decode("utf-8")
        if VERSION not in index:
            missing.append("browser visible version")
        if missing:
            blockers.append("browser_artifact_invalid")
        details["browserMissing"] = missing

    with tempfile.TemporaryDirectory(prefix="wurstbrot-rc2-") as temporary:
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
        installed_report = output / "Installed_Wheel_Acceptance_1.0.0-rc.2.json"
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

    installed = json.loads((output / "Installed_Wheel_Acceptance_1.0.0-rc.2.json").read_text(encoding="utf-8")) if (output / "Installed_Wheel_Acceptance_1.0.0-rc.2.json").is_file() else {}
    payload = {
        "schemaVersion": 1,
        "version": VERSION,
        "artifacts": [wheel.name, sdist.name, browser.name, checksums.name],
        "release_build_passed": not any(item.endswith("_content_invalid") for item in blockers),
        "clean_install_passed": not any(item.startswith(("wheel_install", "installed_")) for item in blockers),
        "release_build_acceptance_passed": bool(installed.get("passed")) and not blockers,
        "version_consistent": details.get("versionOutput", "").endswith(VERSION),
        "acceptance": installed,
        "blockers": blockers,
        "details": details,
    }
    report_path = output / "Release_Build_Acceptance_1.0.0-rc.2.json"
    report_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if not blockers else 1


if __name__ == "__main__":
    raise SystemExit(main())
