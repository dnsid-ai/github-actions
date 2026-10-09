#!/usr/bin/env python3
"""Expand <area>/src/*.yml into .github/workflows/<area>-*.yml.

GitHub only loads workflows from .github/workflows/ itself, never from a
subdirectory, so each area (security/, and any added later) keeps its sources in
<area>/src/, and the callable files are generated with the area as a filename
prefix: security/src/go.yml becomes .github/workflows/security-go.yml.

GitHub also has no include mechanism for workflow files, so jobs an area's
workflows share live once under <area>/src/partials/ and are copied in. A line
of the form

    <indent># @include <partial>.yml

is replaced by the partial, with every line re-indented by <indent>. Partials may
include other partials. Includes resolve within the same area.

    python3 scripts/build.py          # regenerate
    python3 scripts/build.py --check  # exit 1 if .github/workflows is stale (CI)
"""
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / ".github" / "workflows"
INCLUDE = re.compile(r"^(?P<indent>[ ]*)# @include (?P<name>\S+)\s*$")


def expand(path: pathlib.Path, partials: pathlib.Path, seen: tuple = ()) -> list[str]:
    if path in seen:
        raise SystemExit(f"include cycle: {' -> '.join(p.name for p in (*seen, path))}")
    lines = []
    for line in path.read_text().splitlines():
        match = INCLUDE.match(line)
        if not match:
            lines.append(line)
            continue
        indent = match["indent"]
        for inner in expand(partials / match["name"], partials, (*seen, path)):
            lines.append(indent + inner if inner else "")
    return lines


def render(area: str, source: pathlib.Path) -> str:
    header = (
        f"# GENERATED from {area}/src/{source.name} by scripts/build.py. Do not edit here:\n"
        f"# edit {area}/src/ and run `python3 scripts/build.py`.\n"
    )
    return header + "\n".join(expand(source, source.parent / "partials")) + "\n"


def targets() -> dict[pathlib.Path, str]:
    """Every generated workflow path mapped to its rendered text."""
    out = {}
    for src in sorted(ROOT.glob("*/src")):
        area = src.parent.name
        for source in sorted(src.glob("*.yml")):
            out[OUT / f"{area}-{source.name}"] = render(area, source)
    return out


def main() -> int:
    check = "--check" in sys.argv[1:]
    stale = []
    for target, text in targets().items():
        if check:
            if not target.exists() or target.read_text() != text:
                stale.append(target.relative_to(ROOT))
        else:
            target.write_text(text)
            print(f"wrote {target.relative_to(ROOT)}")
    if stale:
        print("stale generated workflows (run `python3 scripts/build.py`):", *stale, sep="\n  ")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
