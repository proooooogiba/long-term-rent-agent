from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
STREAMLIT_ENTRYPOINT = ROOT_DIR / "app.py"


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "--cli":
        from .cli import main as cli_main

        cli_main()
        return

    command = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(STREAMLIT_ENTRYPOINT),
    ]
    if len(sys.argv) > 1:
        command.extend(sys.argv[1:])
    raise SystemExit(subprocess.call(command, cwd=str(ROOT_DIR)))


if __name__ == "__main__":
    main()
