import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "core"))

import wurstbrot_core


class ProjectMetadataTests(unittest.TestCase):
    def test_versions_match(self):
        self.assertEqual((ROOT / "VERSION").read_text(encoding="utf-8").strip(), "1.0.0-rc.2")
        self.assertEqual(wurstbrot_core.__version__, "1.0.0-rc.2")

    def test_browser_entrypoints_exist(self):
        for path in ("index.html", "app.js", "solver.mjs", "manifest.webmanifest", "service-worker.js", "icon.svg"):
            self.assertTrue((ROOT / "apps" / "web" / path).is_file(), path)

    def test_windows_launchers_start_with_echo_off(self):
        launchers = (
            ROOT / "Tests_starten.bat",
            ROOT / "apps" / "ge-calculator" / "Wurstbrot_GE_Calculator_CLI_starten.bat",
        )
        for launcher in launchers:
            first_line = launcher.read_text(encoding="utf-8").splitlines()[0]
            self.assertEqual(first_line.lower(), "@echo off", launcher)

    def test_component_labels_use_rc_version(self):
        expected = "1.0.0-rc.2"
        converter = (ROOT / "apps" / "datamine-manager" / "wurstbrot_converter.py").read_text(
            encoding="utf-8"
        )
        self.assertIn(f'APP_VERSION = "{expected}"', converter)
        gui = (ROOT / "apps" / "ge-calculator" / "ge_calculator_gui.py").read_text(
            encoding="utf-8"
        )
        self.assertIn(expected, gui)

        sample = json.loads(
            (ROOT / "data" / "samples" / "WT_Database_2.57.1.67.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(sample["converter"]["version"], expected)

    def test_browser_and_desktop_use_german_ui_labels(self):
        browser = (ROOT / "apps" / "web" / "app.js").read_text(encoding="utf-8")
        desktop = (ROOT / "apps" / "ge-calculator" / "ge_calculator_gui.py").read_text(
            encoding="utf-8"
        )
        converter = (ROOT / "apps" / "datamine-manager" / "wurstbrot_converter.py").read_text(
            encoding="utf-8"
        )

        for source in (browser, desktop):
            for label in (
                "Deutschland",
                "USA",
                "Schweden",
                "Japan",
                "Panzer",
                "Flugzeuge",
                "Hubschrauber",
                "Küstenschiffe",
                "Hochseeschiffe",
                "Forschungsbaum",
            ):
                self.assertIn(label, source)
            self.assertNotIn("Baumstart", source)

        self.assertIn('"ships": "Hochseeschiffe"', converter)
        self.assertIn('"boats": "Küstenschiffe"', converter)

        service_worker = (ROOT / "apps" / "web" / "service-worker.js").read_text(
            encoding="utf-8"
        )
        self.assertIn('wurstbrot-1.0.0-rc.2-ui-labels', service_worker)


if __name__ == "__main__":
    unittest.main()
