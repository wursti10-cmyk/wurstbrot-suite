from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LINK_PATTERN = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


def main() -> int:
    files = sorted(
        {
            ROOT / "README.md",
            *ROOT.glob("docs/*.md"),
            *ROOT.glob("specs/*.md"),
        }
    )
    failures: list[str] = []
    for source in files:
        text = source.read_text(encoding="utf-8")
        if not text.startswith("# "):
            failures.append(f"{source.relative_to(ROOT)}: missing level-one heading")
        for line_number, line in enumerate(text.splitlines(), 1):
            for raw_target in LINK_PATTERN.findall(line):
                target = raw_target.strip().strip("<>").split("#", 1)[0]
                if not target or "://" in target or target.startswith(("mailto:", "#")):
                    continue
                resolved = (source.parent / target).resolve()
                try:
                    resolved.relative_to(ROOT.resolve())
                except ValueError:
                    failures.append(
                        f"{source.relative_to(ROOT)}:{line_number}: link escapes repository: {target}"
                    )
                    continue
                if not resolved.exists():
                    failures.append(
                        f"{source.relative_to(ROOT)}:{line_number}: missing link target: {target}"
                    )
    if failures:
        print("\n".join(failures))
        return 1
    print(f"Markdown check passed: {len(files)} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
