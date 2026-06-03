from __future__ import annotations

"""
Runs the Keyence VR-5200 processing chain on the jump host.

Execution order:
1. Start the Keyence wrapper.
2. Wait until the wrapper has finished.
3. Start the file indexer.
4. Wait until the indexer has finished.

The later transfer from the finalized machine drive into the Data Lake
is handled separately and is intentionally not part of this orchestrator.
"""

from datetime import datetime
from pathlib import Path
import subprocess
import sys


SCRIPT_DIR = Path(__file__).resolve().parent

WRAPPER_REPO = Path(
    r"C:\Users\uiv51287\keyence-wrapper"
)

WRAPPER_MAIN = (
    WRAPPER_REPO
    / "main.py"
)

FILE_INDEXER_SCRIPT = (
    SCRIPT_DIR
    / "file_indexer.py"
)


def timestamp() -> str:
    return datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )


def log(message: str) -> None:
    print(
        f"[{timestamp()}] "
        f"{message}"
    )


def run_script(
    script_path: Path,
    working_directory: Path,
    label: str,
) -> int:
    """
    Starts one Python script and waits until it has finished.
    """

    if not script_path.is_file():
        log(
            f"{label} not found: "
            f"{script_path}"
        )

        return 1

    log(
        f"Starting {label}: "
        f"{script_path}"
    )

    try:
        result = subprocess.run(
            [
                sys.executable,
                str(script_path),
            ],
            cwd=working_directory,
            check=False,
        )

        log(
            f"{label} finished with "
            f"exit code {result.returncode}"
        )

        return result.returncode

    except Exception as error:
        log(
            f"{label} could not be started: "
            f"{type(error).__name__}: "
            f"{error}"
        )

        return 1


def run_keyence_pipeline() -> str:
    """
    Runs:
    wrapper -> file indexer

    Returns:
    - empty string if both scripts completed successfully
    - error description otherwise
    """

    log(
        "=== Keyence pipeline started ==="
    )

    wrapper_exit_code = run_script(
        script_path=WRAPPER_MAIN,
        working_directory=WRAPPER_REPO,
        label="Keyence wrapper",
    )

    if wrapper_exit_code != 0:
        error_message = (
            f"Keyence wrapper failed with "
            f"exit code {wrapper_exit_code}. "
            f"File indexer was not started."
        )

        log(
            error_message
        )

        return error_message

    indexer_exit_code = run_script(
        script_path=FILE_INDEXER_SCRIPT,
        working_directory=SCRIPT_DIR,
        label="File indexer",
    )

    if indexer_exit_code != 0:
        error_message = (
            f"File indexer failed with "
            f"exit code {indexer_exit_code}."
        )

        log(
            error_message
        )

        return error_message

    log(
        "=== Keyence pipeline finished successfully ==="
    )

    return ""


def main() -> None:
    error_message = (
        run_keyence_pipeline()
    )

    if error_message:
        print(
            f"Keyence pipeline completed "
            f"with error: "
            f"{error_message}",
            file=sys.stderr,
        )


if __name__ == "__main__":
    main()