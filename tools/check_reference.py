#!/usr/bin/env python3
"""Type-check the Scoop code blocks embedded in the reference pages.

Every ``<pre><code class="language-scoop">`` block in src/pages/reference is
checked with ``scoop check`` as an independent single-file program:

* a block that declares ``fun main`` is checked as written;
* otherwise it is first checked as top-level declarations (with an empty
  ``main`` appended), then as statements wrapped in ``fun main() { ... }``.

The ``<pre>`` element may carry ``data-check``:

* ``data-check="error"`` — the block demonstrates a compile error and must
  fail in both forms;
* ``data-check="skip"`` — not checked (manifest snippets, multi-file Cones,
  native libraries, fragments that need surrounding context).

Requires `scoop` on PATH.
"""

from __future__ import annotations

import argparse
import html
import re
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REFERENCE = ROOT / "src" / "pages" / "reference"

BLOCK_RE = re.compile(
    r'<pre(?P<attrs>[^>]*)><code class="language-scoop">(?P<code>.*?)</code></pre>',
    re.DOTALL,
)
CHECK_RE = re.compile(r'data-check="(\w+)"')
MAIN_RE = re.compile(r"^\s*(?:suspend\s+)?fun\s+main\s*\(", re.MULTILINE)


def blocks(page: Path):
    text = page.read_text()
    for match in BLOCK_RE.finditer(text):
        mode = CHECK_RE.search(match.group("attrs"))
        line = text.count("\n", 0, match.start()) + 1
        yield line, mode.group(1) if mode else "auto", html.unescape(match.group("code"))


def check(scoop: str, workdir: Path, name: str, source: str) -> tuple[bool, str]:
    directory = workdir / name
    directory.mkdir()
    (directory / "main.scoop").write_text(source)
    result = subprocess.run(
        [scoop, "check", "main.scoop"],
        cwd=directory,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0, result.stderr


def candidates(code: str) -> list[str]:
    if MAIN_RE.search(code):
        return [code]
    indented = "\n".join(f"    {line}" if line else line for line in code.splitlines())
    return [f"{code}\n\nfun main() {{}}\n", f"fun main() {{\n{indented}\n}}\n"]


def run_block(scoop: str, workdir: Path, key: str, mode: str, code: str) -> str | None:
    errors = []
    for index, source in enumerate(candidates(code)):
        ok, stderr = check(scoop, workdir, f"{key}_{index}", source)
        if ok:
            return "unexpectedly compiled" if mode == "error" else None
        errors.append(stderr)
    return None if mode == "error" else errors[0]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("pages", nargs="*", help="page names to check (default: all)")
    parser.add_argument("-j", "--jobs", type=int, default=8)
    args = parser.parse_args()

    scoop = shutil.which("scoop")
    if scoop is None:
        print("error: `scoop` is not on PATH (try ~/.scoop/bin)", file=sys.stderr)
        return 2

    pages = sorted(REFERENCE.glob("*.html"))
    if args.pages:
        pages = [p for p in pages if p.stem in args.pages]

    jobs = []
    for page in pages:
        for line, mode, code in blocks(page):
            if mode != "skip":
                jobs.append((page.stem, line, mode, code))

    failures = 0
    with tempfile.TemporaryDirectory(prefix="scoop-reference-") as tmp:
        workdir = Path(tmp)
        with ThreadPoolExecutor(max_workers=args.jobs) as pool:
            futures = [
                pool.submit(run_block, scoop, workdir, f"{page}_{line}", mode, code)
                for page, line, mode, code in jobs
            ]
            for (page, line, mode, code), future in zip(jobs, futures):
                error = future.result()
                if error is None:
                    continue
                failures += 1
                print(f"FAIL {page}.html:{line} ({mode})\n{code}\n--- scoop check\n{error}")

    print(f"{len(jobs) - failures}/{len(jobs)} reference code blocks passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
