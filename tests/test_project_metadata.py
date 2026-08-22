import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "core"))

import wurstbrot_core


class ProjectMetadataTests(unittest.TestCase):
    def test_versions_match(self):
        expected = "1.1.0-rc.1"
        self.assertEqual((ROOT / "VERSION").read_text(encoding="utf-8").strip(), expected)
        self.assertEqual(wurstbrot_core.__version__, expected)
        self.assertIn(
            'version = "1.1.0rc1"',
            (ROOT / "pyproject.toml").read_text(encoding="utf-8"),
        )
        self.assertFalse((ROOT / "scripts" / "stable_readiness.py").exists())
        self.assertTrue((ROOT / "scripts" / "rc1_readiness.py").is_file())

        forbidden = (
            "1.0.0-rc.1",
            "1.0.0-rc.2",
            "1.0.0rc1",
            "1.0.0rc2",
            "1.0.0-RC.1",
            "1.0.0-RC.2",
            "Wurstbrot GE Calculator 1.0.0",
            "WURSTBROT SUITE · 1.0.0",
            '__version__ = "1.0.0"',
            'APP_VERSION = "1.0.0"',
            "Rechenquelle für 1.0.0.",
        )
        current_files = (
            ROOT / "README.md",
            ROOT / "SECURITY.md",
            ROOT / "apps" / "datamine-manager" / "wurstbrot_converter.py",
            ROOT / "apps" / "ge-calculator" / "ge_calculator_gui.py",
            ROOT / "apps" / "web" / "index.html",
            ROOT / "apps" / "web" / "service-worker.js",
            ROOT / "apps" / "web" / "visual-tree.mjs",
            ROOT / "apps" / "web" / "visual-tree-interaction.mjs",
            ROOT / "docs" / "00_PROJECT_CONTEXT.md",
            ROOT / "docs" / "14_RELEASE_PROCESS.md",
            ROOT / "docs" / "15_AI_CONTEXT.md",
            ROOT / "docs" / "18_FAQ.md",
            ROOT / "packages" / "core" / "wurstbrot_core" / "__init__.py",
            ROOT / "packages" / "core" / "wurstbrot_core" / "cli.py",
            ROOT / "scripts" / "build_release.py",
            ROOT / "scripts" / "rc1_readiness.py",
            ROOT / ".github" / "workflows" / "ci.yml",
        )
        for path in current_files:
            source = path.read_text(encoding="utf-8")
            for marker in forbidden:
                self.assertNotIn(marker, source, f"{path}: stale {marker}")

    def test_browser_entrypoints_exist(self):
        for path in (
            "index.html",
            "app.js",
            "solver.mjs",
            "visual-tree.mjs",
            "visual-tree-interaction.mjs",
            "manifest.webmanifest",
            "service-worker.js",
            "icon.svg",
        ):
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
        expected = "1.1.0-rc.1"
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
        browser_index = (ROOT / "apps" / "web" / "index.html").read_text(encoding="utf-8")
        self.assertIn("<title>Wurstbrot GE Calculator 1.1.0-rc.1</title>", browser_index)
        self.assertIn("WURSTBROT SUITE · 1.1.0-rc.1", browser_index)

    def test_browser_and_desktop_use_german_ui_labels(self):
        browser = "\n".join(
            (ROOT / "apps" / "web" / name).read_text(encoding="utf-8")
            for name in ("app.js", "visual-tree.mjs")
        )
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
        self.assertIn('wurstbrot-1.0.0-stable-vt7', service_worker)


if __name__ == "__main__":
    unittest.main()
