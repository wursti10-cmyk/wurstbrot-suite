import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "core"))

import wurstbrot_core


class ProjectMetadataTests(unittest.TestCase):
    def test_versions_match(self):
        self.assertEqual((ROOT / "VERSION").read_text(encoding="utf-8").strip(), "0.9.0-beta")
        self.assertEqual(wurstbrot_core.__version__, "0.9.0-beta")

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

    def test_component_labels_use_beta_version(self):
        expected = "0.9.0-beta"
        converter = (ROOT / "apps" / "datamine-manager" / "wurstbrot_converter.py").read_text(
            encoding="utf-8"
        )
        self.assertIn(f'APP_VERSION = "{expected}"', converter)
        gui = (ROOT / "apps" / "ge-calculator" / "ge_calculator_gui.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("0.9.0 Beta", gui)


if __name__ == "__main__":
    unittest.main()
