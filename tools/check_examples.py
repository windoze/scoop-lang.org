#!/usr/bin/env python3
"""Compile and run site and guide examples and compare stdout with NAME.out.

Examples without a recorded .out file are only built (for example the HTTP
server, which runs until interrupted). Requires `scoop` on PATH.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = ROOT / "examples"
GUIDE_EXAMPLES = ROOT / "guides" / "examples"

# Arguments forwarded to examples that need them.
ARGS = {
    "cli": ["Ada", "--count", "2", "--excited"],
    "word-stats": ["Scoop", "中文", ""],
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--update",
        action="store_true",
        help="rewrite .out files with the actual output",
    )
    parser.add_argument(
        "names", nargs="*", help="example names to check (default: all)"
    )
    args = parser.parse_args()

    scoop = shutil.which("scoop")
    if scoop is None:
        print("error: `scoop` is not on PATH (try ~/.scoop/bin)", file=sys.stderr)
        return 2

    sources = sorted([*EXAMPLES.glob("*.scoop"), *GUIDE_EXAMPLES.glob("*.scoop")])
    if args.names:
        sources = [s for s in sources if s.stem in args.names]

    failures = 0
    with tempfile.TemporaryDirectory(prefix="scoop-site-") as target:
        for source in sources:
            expected = source.with_suffix(".out")
            if expected.is_file():
                cmd = [
                    scoop,
                    "run",
                    "--release",
                    "--target-dir",
                    target,
                    str(source),
                    "--",
                    *ARGS.get(source.stem, []),
                ]
            else:
                cmd = [scoop, "build", "--release", "--target-dir", target, str(source)]
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if result.returncode != 0:
                print(f"FAIL {source.name}: exit {result.returncode}\n{result.stderr}")
                failures += 1
                continue
            if cmd[1] == "run":
                if args.update:
                    expected.write_text(result.stdout)
                elif result.stdout != expected.read_text():
                    print(
                        f"FAIL {source.name}: output differs\n--- expected\n{expected.read_text()}--- actual\n{result.stdout}"
                    )
                    failures += 1
                    continue
            print(f"ok   {source.name}")

    print(f"{len(sources) - failures}/{len(sources)} examples passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
