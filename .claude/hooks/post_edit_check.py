"""PostToolUse hook: guardrails enforced by the harness, not by trust.

After an Edit/Write:
  pipeline/**/*.py  -> pytest (quiet, stop at first failure)
  web/src/**/*.ts(x) -> TypeScript typecheck
Exit code 2 sends the failure output back to Claude so it fixes it straight away.
Works inside git worktrees too (it runs checks in the edited file's own checkout).
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True).stdout.strip()


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    fp = (payload.get("tool_input") or {}).get("file_path") or ""
    if not fp:
        return 0
    path = Path(fp).resolve()
    if not path.exists():
        return 0
    root = git(path.parent, "rev-parse", "--show-toplevel")
    if not root:
        return 0
    root_p = Path(root)
    rel = path.relative_to(root_p).as_posix() if path.is_relative_to(root_p) else ""

    if rel.startswith("pipeline/") and path.suffix == ".py":
        # The venv lives in the main checkout; worktrees share it.
        common = Path(git(root_p, "rev-parse", "--path-format=absolute", "--git-common-dir"))
        py = common.parent / ".venv" / "Scripts" / "python.exe"
        if not py.exists():
            py = common.parent / ".venv" / "bin" / "python"
        if not py.exists() or not (root_p / "pipeline" / "tests").exists():
            return 0
        r = subprocess.run([str(py), "-m", "pytest", "pipeline/tests", "-q", "-x", "--no-header", "-p", "no:cacheprovider"],
                           cwd=root_p, capture_output=True, text=True, timeout=170)
        if r.returncode not in (0, 5):  # 5 = no tests collected
            sys.stderr.write(f"[hook] pytest failed after editing {rel}:\n{r.stdout[-3000:]}\n{r.stderr[-1000:]}")
            return 2
        return 0

    if rel.startswith("web/src/") and path.suffix in (".ts", ".tsx"):
        web = root_p / "web"
        tsc = web / "node_modules" / "typescript" / "bin" / "tsc"
        if not tsc.exists():
            return 0
        r = subprocess.run(["node", str(tsc), "--noEmit", "-p", "."], cwd=web, capture_output=True, text=True, timeout=170)
        if r.returncode != 0:
            sys.stderr.write(f"[hook] TypeScript errors after editing {rel}:\n{r.stdout[-3000:]}")
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
