from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VERSION = "1.0.0-rc.1"
BROWSER_NAME = f"wurstbrot-suite-{VERSION}-browser.zip"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Wurstbrot Suite RC artifacts.")
    parser.add_argument("--dist", type=Path, default=ROOT / "dist")
    parser.add_argument("--clean", action="store_true")
    return parser.parse_args()


def add_file(archive: zipfile.ZipFile, source: Path, target: str) -> None:
    info = zipfile.ZipInfo(target, date_time=(2026, 8, 10, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o644 << 16
    archive.writestr(info, source.read_bytes())


def build_browser(dist: Path) -> Path:
    output = dist / BROWSER_NAME
    with zipfile.ZipFile(output, "w") as archive:
        for source in sorted((ROOT / "apps" / "web").iterdir()):
            if source.is_file():
                add_file(archive, source, source.name)
        sample = ROOT / "data" / "samples" / "WT_Database_2.57.1.67.json"
        add_file(archive, sample, f"data/samples/{sample.name}")
    return output


def write_checksums(dist: Path) -> Path:
    output = dist / "SHA256SUMS.txt"
    lines = []
    for path in sorted(item for item in dist.iterdir() if item.is_file() and item != output):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        lines.append(f"{digest}  {path.name}")
    output.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return output


def main() -> int:
    args = parse_args()
    dist = args.dist.resolve()
    if args.clean and dist.exists():
        shutil.rmtree(dist)
    dist.mkdir(parents=True, exist_ok=True)
    if (ROOT / "VERSION").read_text(encoding="utf-8").strip() != VERSION:
        raise SystemExit("VERSION is not the RC version")
    subprocess.run(
        (sys.executable, "-m", "build", "--outdir", str(dist)),
        cwd=ROOT,
        check=True,
    )
    browser = build_browser(dist)
    checksums = write_checksums(dist)
    artifacts = sorted(path.name for path in dist.iterdir() if path.is_file())
    print(json.dumps({"version": VERSION, "browser": browser.name, "checksums": checksums.name, "artifacts": artifacts}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
