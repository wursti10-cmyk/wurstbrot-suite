#!/usr/bin/env python3
"""
Wurstbrot Datamine Converter

Konvertiert eine entpackte War-Thunder-Datamine in eine kompakte JSON-Datenbank.
Keine externen Python-Pakete erforderlich.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import queue
import re
import sys
import threading
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR_PACKAGE = REPOSITORY_ROOT / "packages" / "validator"
if str(VALIDATOR_PACKAGE) not in sys.path:
    sys.path.insert(0, str(VALIDATOR_PACKAGE))

from wurstbrot_validator import (  # noqa: E402
    HealthReport,
    discover_tested_rules,
    legacy_validation_report,
    validate_database as validate_database_health,
    write_health_reports,
)

RULE_MATRIX_PATH = REPOSITORY_ROOT / "tests" / "validator_rule_matrix.py"


def tested_validator_rules() -> tuple[str, ...]:
    return discover_tested_rules([RULE_MATRIX_PATH])


APP_NAME = "Wurstbrot Datamine Converter"
APP_VERSION = "1.0.0-rc.2"

REQUIRED_FILES = {
    "shop": ("shop.blkx",),
    "wpcost": ("wpcost.blkx",),
    "rank": ("rank.blkx",),
    "warpoints": ("warpoints.blkx",),
    "unlocks": ("unlocks.blkx",),
    "units": ("units.csv",),
}
OPTIONAL_FILES = {
    "unittags": ("unittags.blkx",),
    "units_modifications": ("units_modifications.csv",),
    "units_weaponry": ("units_weaponry.csv",),
    "version": ("version.txt",),
}

COUNTRY_NAMES = {
    "country_usa": "USA",
    "country_germany": "Deutschland",
    "country_ussr": "UdSSR",
    "country_britain": "Großbritannien",
    "country_japan": "Japan",
    "country_china": "China",
    "country_italy": "Italien",
    "country_france": "Frankreich",
    "country_sweden": "Schweden",
    "country_israel": "Israel",
}
BRANCH_NAMES = {
    "army": "Panzer",
    "aviation": "Flugzeuge",
    "helicopters": "Hubschrauber",
    "ships": "Hochseeschiffe",
    "boats": "Küstenschiffe",
}
RANK_KEY = {
    "army": "Tank",
    "aviation": "Aircraft",
    "helicopters": "Helicopter",
    "ships": "Ship",
    "boats": "Boat",
}


class ConversionError(RuntimeError):
    pass


@dataclass
class ConversionResult:
    database_path: Path
    validation_path: Path
    health_json_path: Path
    health_text_path: Path
    patch_path: Path | None
    vehicle_count: int
    version: str
    warnings: list[str] = field(default_factory=list)


def log_default(message: str) -> None:
    print(message, flush=True)


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except UnicodeDecodeError:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise ConversionError(
            f"{path.name} ist kein gültiges JSON/BLKX: Zeile {exc.lineno}, Spalte {exc.colno}"
        ) from exc


def find_candidate_files(root: Path, log: Callable[[str], None]) -> dict[str, Path]:
    if not root.exists() or not root.is_dir():
        raise ConversionError("Der gewählte Datamine-Ordner existiert nicht.")

    wanted = {
        filename.lower(): key
        for key, filenames in {**REQUIRED_FILES, **OPTIONAL_FILES}.items()
        for filename in filenames
    }
    candidates: dict[str, list[Path]] = {key: [] for key in {**REQUIRED_FILES, **OPTIONAL_FILES}}

    log("Durchsuche Datamine-Ordner …")
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        lower_name = path.name.lower()
        # Windows/Browser erzeugen bei Duplikaten oft Namen wie shop(3).blkx.
        normalized_name = re.sub(r"\s*\(\d+\)(?=\.[^.]+$)", "", lower_name)
        key = wanted.get(lower_name) or wanted.get(normalized_name)
        if key:
            candidates[key].append(path)

    chosen: dict[str, Path] = {}
    preferred_parts = ("char.vromfs.bin_u", "config", "lang.vromfs.bin_u", "lang")

    for key, paths in candidates.items():
        if not paths:
            continue

        def score(path: Path) -> tuple[int, int, int]:
            lower = str(path).lower()
            preferred = sum(part in lower for part in preferred_parts)
            # Prefer exact names without duplicate suffixes such as "(2)".
            clean_name = int("(" not in path.name and ")" not in path.name)
            # Prefer the shallowest matching path after applying content hints.
            return (preferred, clean_name, -len(path.parts))

        paths.sort(key=score, reverse=True)
        chosen[key] = paths[0]
        if len(paths) > 1:
            log(f"Mehrere Varianten für {key} gefunden; verwende: {paths[0]}")

    missing = [key for key in REQUIRED_FILES if key not in chosen]
    if missing:
        labels = ", ".join(REQUIRED_FILES[key][0] for key in missing)
        raise ConversionError(f"Pflichtdateien fehlen: {labels}")

    return chosen


def load_names(path: Path) -> dict[str, str]:
    names: dict[str, str] = {}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle, delimiter=";")
        try:
            header = next(reader)
        except StopIteration as exc:
            raise ConversionError("units.csv ist leer.") from exc

        de_index = 4 if len(header) > 4 else 1
        en_index = 1 if len(header) > 1 else 0

        for row in reader:
            if not row:
                continue
            key = row[0]
            if not key:
                continue
            de = row[de_index] if len(row) > de_index else ""
            en = row[en_index] if len(row) > en_index else ""
            display = de or en or key
            if key.endswith("_shop"):
                names[key[:-5]] = display
            elif key.endswith("_0") and key[:-2] not in names:
                names[key[:-2]] = display
    return names


def collect_unlock_definitions(obj: Any, output: dict[str, dict[str, Any]]) -> None:
    if isinstance(obj, dict):
        if isinstance(obj.get("id"), str):
            output[obj["id"]] = obj
        for value in obj.values():
            collect_unlock_definitions(value, output)
    elif isinstance(obj, list):
        for value in obj:
            collect_unlock_definitions(value, output)


def country_label(country_id: str) -> str:
    return COUNTRY_NAMES.get(country_id, country_id.replace("country_", "").title())


def describe_unlock(unlock_id: str, definitions: dict[str, dict[str, Any]]) -> str:
    if not unlock_id:
        return ""

    definition = definitions.get(unlock_id, {})
    mode = definition.get("mode", {}) if isinstance(definition, dict) else {}
    unlock_type = mode.get("type")

    if unlock_type == "char_unlocks":
        refs = mode.get("unlock", [])
        if isinstance(refs, str):
            refs = [refs]
        readable: list[str] = []
        for ref in refs:
            match = re.match(r"hidden_(tank|air)_(\d+)_rank_purchased_(.+)", str(ref))
            if match:
                cls, rank, country = match.groups()
                vehicle_type = "Panzer" if cls == "tank" else "Flugzeug"
                readable.append(
                    f"mindestens ein {vehicle_type} Rang {rank} "
                    f"in {country_label('country_' + country)} gekauft"
                )
            else:
                readable.append(str(ref))
        if readable:
            return "Freischaltung: " + " oder ".join(readable)

    if unlock_type == "char_player_era":
        cls = mode.get("unitClass", "Fahrzeug")
        cls_label = {
            "tank": "Panzer",
            "aircraft": "Flugzeuge",
            "boat": "Küstenflotte",
            "ship": "Bluewater",
        }.get(cls, str(cls))
        return (
            f"Freischaltung: Rang {mode.get('era')} bei {cls_label} "
            f"in {country_label(str(mode.get('country', '')))} erreicht"
        )

    if unlock_type == "char_aircrafts_in_era":
        cls = mode.get("unitClass", "Fahrzeug")
        if isinstance(cls, list):
            cls_label = "/".join(
                {"boat": "Küste", "ship": "Bluewater"}.get(str(item), str(item)) for item in cls
            )
        else:
            cls_label = {
                "boat": "Küste",
                "ship": "Bluewater",
                "tank": "Panzer",
            }.get(cls, str(cls))
        return (
            f"Freischaltung: mindestens {mode.get('num', 1)} {cls_label}-Fahrzeug "
            f"ab Rang {mode.get('era')} in "
            f"{country_label(str(mode.get('country', '')))}"
        )

    return f"Sonderfreischaltung erforderlich: {unlock_id}"


def build_database(
    files: dict[str, Path],
    source_root: Path,
    log: Callable[[str], None],
) -> tuple[dict[str, Any], dict[str, Any]]:
    log("Lese Wirtschaftsdaten …")
    shop = load_json(files["shop"])
    costs = load_json(files["wpcost"])
    rank_cfg = load_json(files["rank"])
    warpoints = load_json(files["warpoints"])
    unlocks = load_json(files["unlocks"])
    names = load_names(files["units"])

    version = (
        files["version"].read_text(encoding="utf-8").strip() if "version" in files else "unbekannt"
    )
    rp_per_ge = int(warpoints.get("playerExpToCountryFor1Gold", 45))

    unlock_definitions: dict[str, dict[str, Any]] = {}
    collect_unlock_definitions(unlocks, unlock_definitions)

    vehicles: dict[str, dict[str, Any]] = {}
    predecessors: dict[str, str | None] = {}
    groups: dict[str, list[str]] = {}

    log("Rekonstruiere Forschungsbäume …")
    for country_id, country_data in shop.items():
        if not isinstance(country_data, dict):
            continue

        for branch_id, branch_data in country_data.items():
            if branch_id not in BRANCH_NAMES or not isinstance(branch_data, dict):
                continue

            columns = branch_data.get("range", [])
            if not isinstance(columns, list):
                continue

            for column_index, column in enumerate(columns):
                if not isinstance(column, dict):
                    continue

                previous_anchor: str | None = None
                order = 0

                for node_id, node in column.items():
                    if not isinstance(node, dict):
                        continue

                    children = [
                        (key, value)
                        for key, value in node.items()
                        if isinstance(value, dict) and key in costs
                    ]
                    if children:
                        items = children
                    elif node_id in costs:
                        items = [(node_id, node)]
                    else:
                        continue

                    explicit_requirement = "reqAir" in node
                    incoming = node.get("reqAir") if explicit_requirement else previous_anchor
                    if explicit_requirement and not node.get("reqAir"):
                        incoming = None

                    unit_ids = [unit_id for unit_id, _ in items]
                    if children:
                        groups[node_id] = unit_ids

                    for child_index, (unit_id, meta) in enumerate(items):
                        cost = costs.get(unit_id, {})
                        rp = int(cost.get("reqExp", 0) or 0)
                        sl = int(cost.get("value", 0) or 0)
                        rank = int(meta.get("rank", cost.get("rank", 1) or 1))
                        premium = bool(cost.get("costGold", 0))
                        special = bool(
                            meta.get("gift")
                            or meta.get("event")
                            or meta.get("isClanVehicle")
                            or meta.get("showOnlyWhenBought")
                            or meta.get("showOnlyWhenAvailableForPurchase")
                        )
                        req_unlock = str(meta.get("reqUnlock") or "")
                        hidden_research = bool(meta.get("showOnlyWhenResearch"))
                        reserve = (
                            rp == 0
                            and sl == 0
                            and rank == 1
                            and not req_unlock
                            and not premium
                            and not special
                        )

                        rank_pos = meta.get("rankPosXY")
                        fake_pos = meta.get("fakeReqUnitPosXY")

                        vehicles[unit_id] = {
                            "id": unit_id,
                            "name": names.get(unit_id, unit_id),
                            "country": COUNTRY_NAMES.get(country_id, country_id),
                            "countryId": country_id,
                            "branch": BRANCH_NAMES[branch_id],
                            "branchId": branch_id,
                            "rank": rank,
                            "rp": rp,
                            "sl": sl,
                            "gePurchase": int(cost.get("costGold", 0) or 0),
                            "crewTrainSL": int(cost.get("trainCost", 0) or 0),
                            "expertCrewSL": int(cost.get("train2Cost", 0) or 0),
                            "aceCrewGE": int(cost.get("train3Cost_gold", 0) or 0),
                            "column": column_index,
                            "order": order + child_index / 10,
                            "premium": premium,
                            "special": special,
                            "reserve": reserve,
                            "zeroRP": rp == 0,
                            "hiddenResearch": hidden_research,
                            "reqUnlock": req_unlock,
                            "unlockDescription": describe_unlock(req_unlock, unlock_definitions),
                            "rankPosXY": rank_pos if isinstance(rank_pos, list) else None,
                            "fakeReqUnitPosXY": fake_pos if isinstance(fake_pos, list) else None,
                            "group": node_id if children else None,
                            "groupIndex": child_index,
                        }
                        predecessors[unit_id] = (
                            incoming if child_index == 0 else unit_ids[child_index - 1]
                        )

                    previous_anchor = unit_ids[0]
                    order += 1

    regular = {
        unit_id: vehicle
        for unit_id, vehicle in vehicles.items()
        if not vehicle["premium"]
        and not vehicle["special"]
        and (vehicle["rp"] > 0 or vehicle["zeroRP"])
    }
    regular_ids = set(regular)

    normalized_predecessors: dict[str, str | None] = {}
    cut_references: list[dict[str, str]] = []
    for unit_id in regular:
        predecessor = predecessors.get(unit_id)
        if predecessor and predecessor not in regular_ids:
            cut_references.append({"vehicle": unit_id, "predecessor": predecessor})
            predecessor = None
        normalized_predecessors[unit_id] = predecessor

    rank_unlock: dict[str, dict[str, dict[str, int]]] = {}
    raw_unlock = rank_cfg.get("needBuyToOpenNextInEra", {})
    for country_id, config in raw_unlock.items():
        rank_unlock[country_id] = {}
        for branch_id, suffix in RANK_KEY.items():
            rank_unlock[country_id][branch_id] = {
                str(rank): int(config.get(f"needBuyToOpenNextInEra{suffix}{rank}", 0) or 0)
                for rank in range(1, 10)
            }

    file_manifest = {
        key: {
            "relativePath": (
                str(path.relative_to(source_root))
                if path.is_relative_to(source_root)
                else str(path)
            ),
            "size": path.stat().st_size,
            "sha256": sha256_file(path),
        }
        for key, path in files.items()
    }

    database = {
        "schemaVersion": 1,
        "converter": {
            "name": APP_NAME,
            "version": APP_VERSION,
        },
        "gameVersion": version,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "economy": {
            "rpPerGE": rp_per_ge,
        },
        "vehicles": sorted(
            regular.values(),
            key=lambda item: (
                item["country"],
                item["branch"],
                item["rank"],
                item["column"],
                item["order"],
                item["id"],
            ),
        ),
        "predecessors": normalized_predecessors,
        "groups": groups,
        "rankUnlock": rank_unlock,
        "sourceFiles": file_manifest,
    }

    validation = validate_database(database)
    validation["cutReferences"] = cut_references
    return database, validation


def validate_database(database: dict[str, Any]) -> dict[str, Any]:
    vehicles = database["vehicles"]
    vehicle_map = {vehicle["id"]: vehicle for vehicle in vehicles}
    ids = set(vehicle_map)
    predecessors = database["predecessors"]

    duplicate_count = len(vehicles) - len(ids)
    invalid_predecessors = [
        {"vehicle": unit_id, "predecessor": predecessor}
        for unit_id, predecessor in predecessors.items()
        if predecessor and predecessor not in ids
    ]
    cross_tree: list[dict[str, str]] = []
    rank_backwards: list[dict[str, Any]] = []

    for unit_id, predecessor in predecessors.items():
        if not predecessor or predecessor not in vehicle_map:
            continue
        parent = vehicle_map[predecessor]
        child = vehicle_map[unit_id]
        if parent["countryId"] != child["countryId"] or parent["branchId"] != child["branchId"]:
            cross_tree.append({"predecessor": predecessor, "vehicle": unit_id})
        if parent["rank"] > child["rank"]:
            rank_backwards.append(
                {
                    "predecessor": predecessor,
                    "vehicle": unit_id,
                    "predecessorRank": parent["rank"],
                    "vehicleRank": child["rank"],
                }
            )

    cycles: list[list[str]] = []
    cycle_signatures: set[tuple[str, ...]] = set()
    for start in ids:
        trail: list[str] = []
        positions: dict[str, int] = {}
        current: str | None = start
        while current in ids and current not in positions:
            positions[current] = len(trail)
            trail.append(current)
            current = predecessors.get(current)
        if current in positions:
            cycle = trail[positions[current] :]
            signature = tuple(sorted(cycle))
            if signature not in cycle_signatures:
                cycle_signatures.add(signature)
                cycles.append(cycle)

    negative_costs = [
        vehicle["id"] for vehicle in vehicles if vehicle["rp"] < 0 or vehicle["sl"] < 0
    ]
    missing_names = [vehicle["id"] for vehicle in vehicles if vehicle["name"] == vehicle["id"]]

    stats = {
        "vehicles": len(vehicles),
        "countries": len({vehicle["countryId"] for vehicle in vehicles}),
        "branches": len({(vehicle["countryId"], vehicle["branchId"]) for vehicle in vehicles}),
        "reserves": sum(bool(vehicle["reserve"]) for vehicle in vehicles),
        "zeroRpNonReserves": sum(
            bool(vehicle["zeroRP"] and not vehicle["reserve"]) for vehicle in vehicles
        ),
        "legacyVehicles": sum(bool(vehicle["hiddenResearch"]) for vehicle in vehicles),
        "unlockVehicles": sum(bool(vehicle["reqUnlock"]) for vehicle in vehicles),
        "positionedVehicles": sum(bool(vehicle["rankPosXY"]) for vehicle in vehicles),
        "groups": len(database["groups"]),
    }

    errors = {
        "duplicates": duplicate_count,
        "invalidPredecessors": invalid_predecessors,
        "crossTreeLinks": cross_tree,
        "rankBackwards": rank_backwards,
        "cycles": cycles,
        "negativeCosts": negative_costs,
    }
    passed = (
        duplicate_count == 0
        and not invalid_predecessors
        and not cross_tree
        and not rank_backwards
        and not cycles
        and not negative_costs
    )

    return {
        "schemaVersion": 1,
        "gameVersion": database["gameVersion"],
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "passed": passed,
        "stats": stats,
        "errors": errors,
        "warnings": {
            "missingLocalizedNames": missing_names[:500],
            "missingLocalizedNameCount": len(missing_names),
        },
    }


def compare_databases(
    old_database: dict[str, Any],
    new_database: dict[str, Any],
) -> dict[str, Any]:
    old_map = {vehicle["id"]: vehicle for vehicle in old_database.get("vehicles", [])}
    new_map = {vehicle["id"]: vehicle for vehicle in new_database.get("vehicles", [])}

    added = sorted(set(new_map) - set(old_map))
    removed = sorted(set(old_map) - set(new_map))
    changed: list[dict[str, Any]] = []

    fields = (
        "name",
        "countryId",
        "branchId",
        "rank",
        "rp",
        "sl",
        "reserve",
        "hiddenResearch",
        "reqUnlock",
        "group",
        "column",
        "rankPosXY",
    )

    for unit_id in sorted(set(old_map) & set(new_map)):
        differences = {}
        for field in fields:
            old_value = old_map[unit_id].get(field)
            new_value = new_map[unit_id].get(field)
            if old_value != new_value:
                differences[field] = {"old": old_value, "new": new_value}

        old_pred = old_database.get("predecessors", {}).get(unit_id)
        new_pred = new_database.get("predecessors", {}).get(unit_id)
        if old_pred != new_pred:
            differences["predecessor"] = {"old": old_pred, "new": new_pred}

        if differences:
            changed.append({"id": unit_id, "changes": differences})

    return {
        "schemaVersion": 1,
        "oldGameVersion": old_database.get("gameVersion", "unbekannt"),
        "newGameVersion": new_database.get("gameVersion", "unbekannt"),
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "added": len(added),
            "removed": len(removed),
            "changed": len(changed),
        },
        "addedVehicles": added,
        "removedVehicles": removed,
        "changedVehicles": changed,
    }


def convert(
    source: Path,
    output: Path,
    previous_database: Path | None = None,
    log: Callable[[str], None] = log_default,
) -> ConversionResult:
    source = source.resolve()
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)

    files = find_candidate_files(source, log)
    for key in REQUIRED_FILES:
        log(f"✓ {key}: {files[key]}")

    database, previous_validation = build_database(files, source, log)
    version = str(database["gameVersion"]).replace("/", "-").replace("\\", "-")
    database_path = output / f"WT_Database_{version}.json"
    validation_path = output / f"WT_Validation_{version}.json"

    health = validate_database_health(database, tested_rules=tested_validator_rules())
    validation = legacy_validation_report(health)
    validation["cutReferences"] = previous_validation.get("cutReferences", [])
    health_json_path, health_text_path = write_health_reports(health, output)

    validation_path.write_text(
        json.dumps(validation, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    if not health.passed:
        raise ConversionError(
            f"Strukturierte Validierung fehlgeschlagen: {health.counts['error']} ERROR-Findings. "
            f"Details: {health_json_path}"
        )

    log("Schreibe kompakte Datenbank …")
    database_path.write_text(
        json.dumps(database, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )

    patch_path: Path | None = None
    if previous_database:
        log("Erstelle Patchvergleich …")
        old_database = load_json(previous_database)
        patch = compare_databases(old_database, database)
        patch_path = output / (
            f"WT_Patch_{patch['oldGameVersion']}_zu_{patch['newGameVersion']}.json"
        )
        patch_path.write_text(
            json.dumps(patch, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    log(
        f"Fertig: {validation['stats']['vehicles']} Fahrzeuge, "
        f"Validierung {'bestanden' if validation['passed'] else 'FEHLGESCHLAGEN'}."
    )
    return ConversionResult(
        database_path=database_path,
        validation_path=validation_path,
        health_json_path=health_json_path,
        health_text_path=health_text_path,
        patch_path=patch_path,
        vehicle_count=validation["stats"]["vehicles"],
        version=version,
    )


def run_cli(args: argparse.Namespace) -> int:
    try:
        result = convert(
            Path(args.source),
            Path(args.output),
            Path(args.previous) if args.previous else None,
        )
    except Exception as exc:
        print(f"FEHLER: {exc}", file=sys.stderr)
        if args.debug:
            traceback.print_exc()
        return 1

    print(f"Datenbank: {result.database_path}")
    print(f"Validierung: {result.validation_path}")
    print(f"Health Report: {result.health_json_path}")
    print(f"Health Summary: {result.health_text_path}")
    if result.patch_path:
        print(f"Patchvergleich: {result.patch_path}")
    return 0


def validate_existing_database(database_path: Path, output: Path) -> HealthReport:
    """Validate an existing normalized database without requiring raw datamine files."""
    database = load_json(database_path)
    if not isinstance(database, dict):
        raise ConversionError("Die Datenbankwurzel muss ein JSON-Objekt sein.")
    report = validate_database_health(database, tested_rules=tested_validator_rules())
    write_health_reports(report, output.resolve())
    return report


def run_validation_cli(args: argparse.Namespace) -> int:
    try:
        report = validate_existing_database(Path(args.validate_database), Path(args.output))
    except Exception as exc:
        print(f"FEHLER: {exc}", file=sys.stderr)
        if args.debug:
            traceback.print_exc()
        return 1
    print(report.to_text(), end="")
    return 0 if report.passed else 1


def run_gui() -> int:
    try:
        import tkinter as tk
        from tkinter import filedialog, messagebox, ttk
    except Exception as exc:
        print(
            "Die grafische Oberfläche konnte nicht gestartet werden. "
            "Verwende den Kommandozeilenmodus.",
            file=sys.stderr,
        )
        print(exc, file=sys.stderr)
        return 1

    class ConverterGUI:
        def __init__(self, root: tk.Tk) -> None:
            self.root = root
            self.root.title(f"{APP_NAME} {APP_VERSION}")
            self.root.geometry("840x650")
            self.root.minsize(720, 540)

            self.source_var = tk.StringVar()
            self.output_var = tk.StringVar(value=str(Path.home() / "Desktop" / "Wurstbrot_Output"))
            self.previous_var = tk.StringVar()
            self.status_var = tk.StringVar(value="Datamine-Ordner auswählen.")
            self.queue: queue.Queue[tuple[str, Any]] = queue.Queue()

            self.build_ui()
            self.root.after(100, self.poll_queue)

        def build_ui(self) -> None:
            outer = ttk.Frame(self.root, padding=18)
            outer.pack(fill="both", expand=True)

            title = ttk.Label(
                outer,
                text="🥪 Wurstbrot Datamine Converter",
                font=("Segoe UI", 18, "bold"),
            )
            title.pack(anchor="w")
            ttk.Label(
                outer,
                text=(
                    "Erstellt eine kompakte War-Thunder-Datenbank für den "
                    "Wurstbrot GE Calculator 2.0."
                ),
            ).pack(anchor="w", pady=(2, 16))

            self.add_path_row(
                outer,
                "Entpackte Datamine",
                self.source_var,
                self.choose_source,
                "Ordner auswählen",
            )
            self.add_path_row(
                outer,
                "Ausgabeordner",
                self.output_var,
                self.choose_output,
                "Ordner auswählen",
            )
            self.add_path_row(
                outer,
                "Vorherige Datenbank (optional)",
                self.previous_var,
                self.choose_previous,
                "JSON auswählen",
            )

            button_frame = ttk.Frame(outer)
            button_frame.pack(fill="x", pady=(14, 10))
            self.convert_button = ttk.Button(
                button_frame,
                text="Konvertierung starten",
                command=self.start_conversion,
            )
            self.convert_button.pack(side="left")
            ttk.Button(
                button_frame,
                text="Ausgabeordner öffnen",
                command=self.open_output,
            ).pack(side="left", padx=8)

            self.progress = ttk.Progressbar(outer, mode="indeterminate")
            self.progress.pack(fill="x", pady=(0, 8))
            ttk.Label(outer, textvariable=self.status_var).pack(anchor="w")

            log_frame = ttk.LabelFrame(outer, text="Protokoll", padding=8)
            log_frame.pack(fill="both", expand=True, pady=(12, 0))
            self.log_widget = tk.Text(
                log_frame,
                height=18,
                wrap="word",
                state="disabled",
                font=("Consolas", 10),
            )
            scrollbar = ttk.Scrollbar(
                log_frame,
                orient="vertical",
                command=self.log_widget.yview,
            )
            self.log_widget.configure(yscrollcommand=scrollbar.set)
            self.log_widget.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")

        def add_path_row(
            self,
            parent: Any,
            label: str,
            variable: tk.StringVar,
            command: Callable[[], None],
            button_text: str,
        ) -> None:
            frame = ttk.Frame(parent)
            frame.pack(fill="x", pady=6)
            ttk.Label(frame, text=label, width=28).pack(side="left")
            ttk.Entry(frame, textvariable=variable).pack(
                side="left", fill="x", expand=True, padx=(0, 8)
            )
            ttk.Button(frame, text=button_text, command=command).pack(side="right")

        def choose_source(self) -> None:
            path = filedialog.askdirectory(title="Entpackte Datamine auswählen")
            if path:
                self.source_var.set(path)

        def choose_output(self) -> None:
            path = filedialog.askdirectory(title="Ausgabeordner auswählen")
            if path:
                self.output_var.set(path)

        def choose_previous(self) -> None:
            path = filedialog.askopenfilename(
                title="Vorherige Wurstbrot-Datenbank auswählen",
                filetypes=[("JSON-Dateien", "*.json"), ("Alle Dateien", "*.*")],
            )
            if path:
                self.previous_var.set(path)

        def append_log(self, message: str) -> None:
            self.log_widget.configure(state="normal")
            self.log_widget.insert("end", message + "\n")
            self.log_widget.see("end")
            self.log_widget.configure(state="disabled")

        def start_conversion(self) -> None:
            source = self.source_var.get().strip()
            output = self.output_var.get().strip()
            previous = self.previous_var.get().strip()

            if not source:
                messagebox.showwarning(APP_NAME, "Bitte Datamine-Ordner auswählen.")
                return
            if not output:
                messagebox.showwarning(APP_NAME, "Bitte Ausgabeordner auswählen.")
                return

            self.convert_button.configure(state="disabled")
            self.progress.start(12)
            self.status_var.set("Konvertierung läuft …")
            self.append_log("=" * 60)

            thread = threading.Thread(
                target=self.worker,
                args=(source, output, previous),
                daemon=True,
            )
            thread.start()

        def worker(self, source: str, output: str, previous: str) -> None:
            try:
                result = convert(
                    Path(source),
                    Path(output),
                    Path(previous) if previous else None,
                    log=lambda message: self.queue.put(("log", message)),
                )
                self.queue.put(("success", result))
            except Exception as exc:
                self.queue.put(("error", (str(exc), traceback.format_exc())))

        def poll_queue(self) -> None:
            try:
                while True:
                    kind, payload = self.queue.get_nowait()
                    if kind == "log":
                        self.append_log(str(payload))
                    elif kind == "success":
                        self.on_success(payload)
                    elif kind == "error":
                        self.on_error(*payload)
            except queue.Empty:
                pass
            self.root.after(100, self.poll_queue)

        def on_success(self, result: ConversionResult) -> None:
            self.progress.stop()
            self.convert_button.configure(state="normal")
            self.status_var.set(
                f"Fertig: {result.vehicle_count} Fahrzeuge, Version {result.version}"
            )
            self.append_log(f"Datenbank: {result.database_path}")
            self.append_log(f"Validierung: {result.validation_path}")
            self.append_log(f"Health Report: {result.health_json_path}")
            self.append_log(f"Health Summary: {result.health_text_path}")
            if result.patch_path:
                self.append_log(f"Patchvergleich: {result.patch_path}")
            messagebox.showinfo(
                APP_NAME,
                (
                    f"Konvertierung abgeschlossen.\n\n"
                    f"Version: {result.version}\n"
                    f"Fahrzeuge: {result.vehicle_count}\n\n"
                    f"Ausgabe:\n{result.database_path.parent}"
                ),
            )

        def on_error(self, message: str, details: str) -> None:
            self.progress.stop()
            self.convert_button.configure(state="normal")
            self.status_var.set("Konvertierung fehlgeschlagen.")
            self.append_log("FEHLER: " + message)
            self.append_log(details)
            messagebox.showerror(APP_NAME, message)

        def open_output(self) -> None:
            output = Path(self.output_var.get().strip())
            output.mkdir(parents=True, exist_ok=True)
            try:
                if sys.platform.startswith("win"):
                    import os

                    os.startfile(output)  # type: ignore[attr-defined]
                elif sys.platform == "darwin":
                    import subprocess

                    subprocess.Popen(["open", str(output)])
                else:
                    import subprocess

                    subprocess.Popen(["xdg-open", str(output)])
            except Exception as exc:
                messagebox.showerror(APP_NAME, f"Ordner konnte nicht geöffnet werden:\n{exc}")

    root = tk.Tk()
    try:
        root.call("tk", "scaling", 1.15)
    except Exception:
        pass
    ConverterGUI(root)
    root.mainloop()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=APP_NAME)
    parser.add_argument("--source", help="Entpackter Datamine-Ordner")
    parser.add_argument("--output", help="Ausgabeordner")
    parser.add_argument("--previous", help="Vorherige WT_Database_*.json für Patchvergleich")
    parser.add_argument(
        "--validate-database",
        help="Bestehende WT_Database_*.json prüfen und Health Reports erzeugen",
    )
    parser.add_argument("--debug", action="store_true", help="Ausführliche Fehlerausgabe")
    parser.add_argument("--gui", action="store_true", help="Grafische Oberfläche starten")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.validate_database:
        if not args.output:
            parser.error("--validate-database benötigt --output.")
        return run_validation_cli(args)

    if args.gui or (not args.source and not args.output):
        return run_gui()

    if not args.source or not args.output:
        parser.error("--source und --output werden im Kommandozeilenmodus benötigt.")

    return run_cli(args)


if __name__ == "__main__":
    raise SystemExit(main())
