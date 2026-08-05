from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
CONVERTER_PATH = ROOT / "apps" / "datamine-manager" / "wurstbrot_converter.py"


def load_converter():
    spec = importlib.util.spec_from_file_location("wurstbrot_converter", CONVERTER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("Converter module could not be loaded")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class ConverterHealthTests(unittest.TestCase):
    def test_existing_sample_database_generates_both_health_files(self):
        converter = load_converter()
        sample = ROOT / "data" / "samples" / "WT_Database_2.57.1.67.json"
        with tempfile.TemporaryDirectory() as directory:
            report = converter.validate_existing_database(sample, Path(directory))
            self.assertTrue(report.passed)
            self.assertTrue((Path(directory) / "WT_Health_2.57.1.67.json").is_file())
            self.assertTrue((Path(directory) / "WT_Health_2.57.1.67.txt").is_file())

    def test_validation_cli_returns_nonzero_for_error_findings(self):
        invalid = {
            "schemaVersion": 99,
            "gameVersion": "2.57.1.67",
            "economy": {"rpPerGE": 45},
            "vehicles": [],
            "predecessors": {},
            "groups": {},
            "rankUnlock": {},
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "invalid.json"
            source.write_text(json.dumps(invalid), encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    str(CONVERTER_PATH),
                    "--validate-database",
                    str(source),
                    "--output",
                    str(root / "health"),
                ],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 1)
            report = json.loads((root / "health" / "WT_Health_2.57.1.67.json").read_text())
            self.assertFalse(report["passed"])
            self.assertGreater(report["counts"]["error"], 0)

    def test_conversion_error_writes_diagnostics_but_not_database(self):
        converter = load_converter()
        invalid = {
            "schemaVersion": 99,
            "gameVersion": "2.57.1.67",
            "economy": {"rpPerGE": 45},
            "vehicles": [],
            "predecessors": {},
            "groups": {},
            "rankUnlock": {},
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "output"
            fake_files = {key: root / names[0] for key, names in converter.REQUIRED_FILES.items()}
            with (
                mock.patch.object(converter, "find_candidate_files", return_value=fake_files),
                mock.patch.object(
                    converter,
                    "build_database",
                    return_value=(invalid, {"cutReferences": []}),
                ),
            ):
                with self.assertRaises(converter.ConversionError):
                    converter.convert(root, output, log=lambda _message: None)
            self.assertFalse((output / "WT_Database_2.57.1.67.json").exists())
            self.assertTrue((output / "WT_Validation_2.57.1.67.json").exists())
            self.assertTrue((output / "WT_Health_2.57.1.67.json").exists())


if __name__ == "__main__":
    unittest.main()
