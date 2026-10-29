"""Report-only mutation testing of the Python files a PR changes.

Runs mutmut against the changed modules under src/factory and writes a Markdown summary. It always
exits 0: a surviving mutant, a mutmut crash or a timeout is reported, never a failure.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys

SOURCE_ROOT = "src/"
SKIP_PREFIXES = ("src/factory/_vendor/",)
RESULT_LINE = re.compile(r"^\s*(\S+):\s+(\w[\w ]*?)\s*$")
RUN_TIMEOUT_SECONDS = 15 * 60


def changed_modules(paths: list[str]) -> list[str]:
    """Dotted module names for the changed mutable source files (vendored code and __init__ are skipped)."""
    modules = []
    for path in paths:
        if not (path.startswith(SOURCE_ROOT) and path.endswith(".py")) or path.startswith(SKIP_PREFIXES):
            continue
        if path.rsplit("/", 1)[-1] == "__init__.py":
            continue
        module = path[len(SOURCE_ROOT) : -len(".py")].replace("/", ".")
        if module not in modules:
            modules.append(module)
    return modules


def parse_results(output: str, modules: list[str]) -> dict[str, dict[str, int]]:
    """Count mutants per module and status from `mutmut results` output."""
    counts: dict[str, dict[str, int]] = {m: {} for m in modules}
    for line in output.splitlines():
        match = RESULT_LINE.match(line)
        if not match:
            continue
        name, status = match.groups()
        owner = max((m for m in modules if name.startswith(m + ".")), key=len, default=None)
        if owner:
            counts[owner][status] = counts[owner].get(status, 0) + 1
    return counts


def render(modules: list[str], counts: dict[str, dict[str, int]], note: str = "") -> str:
    lines = ["## Mutation testing (report only)", "", "This job never fails the build or blocks merge.", ""]
    if note:
        lines += [f"> {note}", ""]
    if not modules:
        lines.append("No mutable Python files under `src/factory` changed, so nothing was mutated.")
        return "\n".join(lines) + "\n"
    lines += ["| File | Surviving mutants | Other non-killed |", "| --- | --- | --- |"]
    for module in modules:
        found = counts.get(module, {})
        survived = found.get("survived", 0)
        other = ", ".join(f"{n} {s}" for s, n in sorted(found.items()) if s != "survived") or "0"
        lines.append(f"| `{module.replace('.', '/')}.py` | {survived} | {other} |")
    lines += ["", "A surviving mutant is a code change the tests did not notice: a hint to tighten a test, not a verdict."]
    return "\n".join(lines) + "\n"


def run(cmd: list[str], timeout: int) -> tuple[str, str]:
    """Run a command; return (stdout, problem) where problem is empty on success."""
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired as exc:
        out = exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        return out, f"`{cmd[0]} {cmd[1]}` hit the {timeout // 60} minute limit; results below are partial."
    except OSError as exc:
        return "", f"could not run `{cmd[0]}`: {exc}"
    problem = "" if proc.returncode == 0 else f"`{cmd[0]} {cmd[1]}` exited {proc.returncode}; results below may be incomplete."
    return proc.stdout, problem


def main(argv: list[str]) -> int:
    modules = changed_modules([line.strip() for line in sys.stdin.read().splitlines() if line.strip()])
    counts: dict[str, dict[str, int]] = {}
    note = ""
    if modules:
        _, note = run(["mutmut", "run", *(f"{m}.*" for m in modules)], RUN_TIMEOUT_SECONDS)
        out, results_note = run(["mutmut", "results"], 120)
        note = note or results_note
        counts = parse_results(out, modules)
    report = render(modules, counts, note)
    print(report)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(report)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
