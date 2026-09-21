"""Read-only deployment checks; run with the project's Python environment."""
from pathlib import Path
import subprocess
import sys


def main():
    root = Path(__file__).resolve().parent.parent
    commands = (
        ["check", "--deploy", "--fail-level", "WARNING"],
        ["migrate", "--check"],
        ["collectstatic", "--dry-run", "--noinput", "--verbosity", "0"],
    )
    failed = False
    for command in commands:
        print("Pruefung: " + " ".join(command), flush=True)
        result = subprocess.run(
            [sys.executable, str(root / "manage.py"), *command,
             "--settings=config.settings.production"],
            cwd=root,
        )
        failed |= result.returncode != 0
    return int(failed)


if __name__ == "__main__":
    sys.exit(main())
