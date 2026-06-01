from __future__ import annotations

"""Run wrapper -> router -> Raw_Data file indexer without global pipeline stops."""

from argparse import ArgumentParser
from datetime import datetime
from pathlib import Path
import subprocess
import sys


DEFAULT_WRAPPER_REPO = Path(
    r"C:\Users\uiv51287\keyence-wrapper"
)

DEFAULT_RECIPE_FOLDER = "EMB_Gan_Prüfvorlage_zit"

SCRIPT_DIR = Path(__file__).resolve().parent

ROUTER_SCRIPT = (
    SCRIPT_DIR
    / "keyence_output_router.py"
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
    print(f"[{timestamp()}] {message}")


def run_subprocess(
    command: list[str],
    cwd: Path,
    label: str,
) -> int:
    log(f"Starting {label}")

    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            check=False,
        )

        log(
            f"{label} finished "
            f"with exit code {result.returncode}"
        )

        return result.returncode

    except Exception as error:
        log(
            f"{label} could not be started: "
            f"{error}"
        )

        return 1


def run_wrapper(
    wrapper_repo: Path,
) -> int:
    wrapper_main = wrapper_repo / "main.py"

    if not wrapper_main.is_file():
        log(
            f"Wrapper main.py not found: "
            f"{wrapper_main}"
        )

        return 1

    return run_subprocess(
        command=[
            sys.executable,
            str(wrapper_main),
        ],
        cwd=wrapper_repo,
        label="wrapper",
    )


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

    return run_subprocess(
        command=command,
        cwd=SCRIPT_DIR,
        label="Keyence output router",
    )


def run_file_indexer(
    dry_run: bool,
) -> int:
    command = [
        sys.executable,
        str(FILE_INDEXER_SCRIPT),
    ]

    if dry_run:
        command.append("--dry-run")

    return run_subprocess(
        command=command,
        cwd=SCRIPT_DIR,
        label="Raw_Data file indexer",
    )


def parse_args():
    parser = ArgumentParser()

    parser.add_argument(
        "--wrapper-repo",
        type=Path,
        default=DEFAULT_WRAPPER_REPO,
    )

    parser.add_argument(
        "--date",
        required=True,
        help="Target YYYYMMDD folder below Raw_Data.",
    )

    parser.add_argument(
        "--recipe-folder",
        default=DEFAULT_RECIPE_FOLDER,
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if not args.wrapper_repo.is_dir():
        raise FileNotFoundError(
            f"Wrapper repository not found: "
            f"{args.wrapper_repo}"
        )

    log("=== Keyence pipeline started ===")

    if run_wrapper(args.wrapper_repo) != 0:
        log(
            "Wrapper reported an error. "
            "Pipeline continues."
        )

    if run_router(
        wrapper_repo=args.wrapper_repo,
        date_folder=args.date,
        recipe_folder=args.recipe_folder,
        dry_run=args.dry_run,
    ) != 0:
        log(
            "Router reported an error. "
            "Pipeline continues."
        )

    if run_file_indexer(
        dry_run=args.dry_run,
    ) != 0:
        log(
            "File indexer reported an error. "
            "Pipeline continues."
        )

    log("=== Keyence pipeline finished ===")


if __name__ == "__main__":
    main()