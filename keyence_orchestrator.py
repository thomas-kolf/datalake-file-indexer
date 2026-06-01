from __future__ import annotations

"""
Local Keyence test orchestrator.

Execution order:
    1. Start keyence-wrapper/main.py in the separate wrapper repository.
    2. Wait until the wrapper process has ended.
    3. Run keyence_output_router.py.
    4. Upload available wrapper outputs to S3 by default.
    5. Continue even when the wrapper returns a non-zero exit code.

The file indexer is intentionally not started yet.
It must first be refactored to scan Raw_Data instead of toBeProcessed.
"""

from argparse import ArgumentParser
from datetime import datetime
from pathlib import Path
import subprocess
import sys


DEFAULT_WRAPPER_REPO = Path(r"C:\Users\uiv51287\keyence-wrapper")
DEFAULT_RECIPE_FOLDER = "EMB_Gan_Prüfvorlage_zit"

SCRIPT_DIR = Path(__file__).resolve().parent
ROUTER_SCRIPT = SCRIPT_DIR / "keyence_output_router.py"


def timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def log(message: str) -> None:
    print(f"[{timestamp()}] {message}")


def run_wrapper(wrapper_repo: Path) -> int:
    wrapper_main = wrapper_repo / "main.py"

    if not wrapper_main.is_file():
        log(f"Wrapper main.py not found: {wrapper_main}")
        return 1

    log(f"Starting wrapper: {wrapper_main}")

    result = subprocess.run(
        [sys.executable, str(wrapper_main)],
        cwd=wrapper_repo,
        check=False,
    )

    log(f"Wrapper finished with exit code {result.returncode}")

    return result.returncode


def run_router(
    wrapper_repo: Path,
    date_folder: str,
    recipe_folder: str,
    dry_run: bool,
) -> int:
    command = [
        sys.executable,
        str(ROUTER_SCRIPT),
        "--wrapper-repo",
        str(wrapper_repo),
        "--date",
        date_folder,
        "--recipe-folder",
        recipe_folder,
    ]

    if dry_run:
        command.append("--dry-run")

    log("Starting Keyence output router")

    result = subprocess.run(
        command,
        cwd=SCRIPT_DIR,
        check=False,
    )

    log(f"Router finished with exit code {result.returncode}")

    return result.returncode


def parse_args():
    parser = ArgumentParser()

    parser.add_argument(
        "--wrapper-repo",
        type=Path,
        default=DEFAULT_WRAPPER_REPO,
        help="Path to the local keyence-wrapper repository.",
    )

    parser.add_argument(
        "--date",
        required=True,
        help="Target YYYYMMDD folder below Raw_Data.",
    )

    parser.add_argument(
        "--recipe-folder",
        default=DEFAULT_RECIPE_FOLDER,
        help="Recipe folder used below Raw_Data and toBeProcessed.",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Start wrapper but only print planned S3 routing actions.",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if not args.wrapper_repo.is_dir():
        raise FileNotFoundError(
            f"Wrapper repository not found: {args.wrapper_repo}"
        )

    log("=== Keyence pipeline started ===")

    wrapper_exit_code = run_wrapper(args.wrapper_repo)

    if wrapper_exit_code != 0:
        log(
            "Wrapper reported an error. Routing still continues so that "
            "available outputs can be retained and the next run is not blocked."
        )

    router_exit_code = run_router(
        wrapper_repo=args.wrapper_repo,
        date_folder=args.date,
        recipe_folder=args.recipe_folder,
        dry_run=args.dry_run,
    )

    if router_exit_code != 0:
        log(
            "Router reported an error. "
            "The orchestrator continues after logging it."
        )

    log(
        "File indexer step is currently disabled "
        "until file_indexer.py scans Raw_Data."
    )

    log("=== Keyence pipeline finished ===")


if __name__ == "__main__":
    main()