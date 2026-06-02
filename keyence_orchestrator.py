from __future__ import annotations

"""
Runs the Keyence-specific processing chain inside the Data-Lake appliance.

Execution order:
1. Clear the temporary standardized staging folder.
2. Start the Keyence wrapper and wait until it has finished.
3. Replace original unstandardized Raw_Data recipe folders only if verified
   staged output files exist.
4. Start the global Raw_Data file indexer.

Important:
- The wrapper itself processes:
  /mnt/639r-ait/Keyence_VR5200/toBeProcessed/
- The wrapper writes standardized files temporarily into:
  /mnt/639r-ait/Processing/Wrapper/data_lake_ready/
- The wrapper itself already routes:
  - failed files into Raw_Data/<date>/
  - Statistics into Raw_Data/<date>/Statistics/
  - Power-BI CSV files into toBeProcessed/<recipe>/
  - logs into Logs/<date>/
"""

from datetime import datetime
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tomllib


SCRIPT_DIR = Path(__file__).resolve().parent
CONFIG_PATH = SCRIPT_DIR / "config.toml"

FILE_INDEXER_SCRIPT = SCRIPT_DIR / "file_indexer.py"

DATE_PREFIX_PATTERN = re.compile(
    r"^(?P<date>\d{8})_"
)


def timestamp() -> str:
    return datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )


def log(message: str) -> None:
    print(f"[{timestamp()}] {message}")


def load_config() -> dict:
    with CONFIG_PATH.open("rb") as file:
        return tomllib.load(file)


def clear_staging_folder(
    staging_folder: Path,
) -> None:
    """
    Removes staging output from earlier wrapper runs.

    This affects only:
    Processing/Wrapper/data_lake_ready/

    Permanent Raw_Data files remain untouched.
    """

    if staging_folder.exists():
        shutil.rmtree(staging_folder)

    staging_folder.mkdir(
        parents=True,
        exist_ok=True,
    )

    log(f"Cleared staging folder: {staging_folder}")


def run_script(
    script_path: Path,
    working_directory: Path,
    label: str,
) -> int:
    log(f"Starting {label}: {script_path}")

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
            f"{type(error).__name__}: {error}"
        )

        return 1


def get_date_from_file_name(
    file_path: Path,
) -> str | None:
    match = DATE_PREFIX_PATTERN.match(
        file_path.name
    )

    if match is None:
        return None

    return match.group("date")


def collect_staged_files_by_recipe_and_date(
    staging_folder: Path,
) -> dict[tuple[str, str], list[Path]]:
    """
    Groups staged wrapper outputs by:
    - recipe folder
    - YYYYMMDD date parsed from standardized file name
    """

    staged_files: dict[
        tuple[str, str],
        list[Path],
    ] = {}

    if not staging_folder.is_dir():
        return staged_files

    for recipe_folder in staging_folder.iterdir():
        if not recipe_folder.is_dir():
            continue

        recipe_name = recipe_folder.name

        for staged_file in recipe_folder.rglob("*"):
            if not staged_file.is_file():
                continue

            date_folder_name = get_date_from_file_name(
                staged_file
            )

            if date_folder_name is None:
                log(
                    f"Skipped staged file without YYYYMMDD prefix: "
                    f"{staged_file}"
                )

                continue

            key = (
                recipe_name,
                date_folder_name,
            )

            staged_files.setdefault(
                key,
                [],
            ).append(staged_file)

    return staged_files


def replace_raw_recipe_folder(
    raw_data_root: Path,
    staging_recipe_root: Path,
    recipe_name: str,
    date_folder_name: str,
    staged_files: list[Path],
) -> int:
    """
    Replaces only:
    Raw_Data/<date>/<recipe_name>/

    It never deletes:
    Raw_Data/<date>/

    Therefore these permanent files remain untouched:
    - .zit files
    - random machine files
    - incomplete or unstandardized files
    - Statistics folders
    """

    target_recipe_folder = (
        raw_data_root
        / date_folder_name
        / recipe_name
    )

    if not staged_files:
        log(
            f"Skipped empty staged recipe output: "
            f"{recipe_name} | {date_folder_name}"
        )

        return 0

    if target_recipe_folder.exists():
        shutil.rmtree(
            target_recipe_folder
        )

        log(
            f"Deleted old unstandardized recipe folder: "
            f"{target_recipe_folder}"
        )

    copied_files = 0

    for source_file in staged_files:
        relative_path = source_file.relative_to(
            staging_recipe_root
        )

        target_file = (
            target_recipe_folder
            / relative_path
        )

        target_file.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        shutil.copy2(
            source_file,
            target_file,
        )

        copied_files += 1

    log(
        f"Copied standardized recipe files: "
        f"{recipe_name} | {date_folder_name} | "
        f"files={copied_files}"
    )

    return copied_files


def route_standardized_outputs(
    staging_folder: Path,
    raw_data_root: Path,
) -> int:
    """
    Replaces original Raw_Data recipe folders with verified
    standardized wrapper artifacts.
    """

    staged_files = collect_staged_files_by_recipe_and_date(
        staging_folder=staging_folder,
    )

    if not staged_files:
        log(
            "No staged standardized output files found. "
            "Raw_Data recipe folders remain untouched."
        )

        return 0

    copied_files = 0

    for (
        recipe_name,
        date_folder_name,
    ), files in staged_files.items():
        staging_recipe_root = (
            staging_folder
            / recipe_name
        )

        copied_files += replace_raw_recipe_folder(
            raw_data_root=raw_data_root,
            staging_recipe_root=staging_recipe_root,
            recipe_name=recipe_name,
            date_folder_name=date_folder_name,
            staged_files=files,
        )

    return copied_files


def run_keyence_pipeline() -> str:
    """
    Runs the complete Keyence chain.

    Returns:
    - empty string if no technical error occurred
    - error description otherwise

    The caller can log the error and continue processing other machines.
    """

    config = load_config()
    runtime_paths = config["runtime_paths"]

    wrapper_repo = Path(
        runtime_paths["wrapper_repo_dir"]
    )

    wrapper_main = (
        wrapper_repo
        / "main.py"
    )

    staging_folder = Path(
        runtime_paths["wrapper_staging_dir"]
    )

    raw_data_root = Path(
        runtime_paths["keyence_raw_data_dir"]
    )

    if not wrapper_main.is_file():
        error_message = (
            f"Keyence wrapper main.py not found: "
            f"{wrapper_main}"
        )

        log(error_message)
        return error_message

    log("=== Keyence pipeline started ===")

    clear_staging_folder(
        staging_folder=staging_folder,
    )

    wrapper_exit_code = run_script(
        script_path=wrapper_main,
        working_directory=wrapper_repo,
        label="Keyence wrapper",
    )

    if wrapper_exit_code != 0:
        error_message = (
            f"Keyence wrapper failed with "
            f"exit code {wrapper_exit_code}. "
            f"Raw_Data recipe folders remain untouched."
        )

        log(error_message)

        # The index still reflects the real permanent Raw_Data state.
        run_script(
            script_path=FILE_INDEXER_SCRIPT,
            working_directory=SCRIPT_DIR,
            label="Raw_Data file indexer",
        )

        log("=== Keyence pipeline finished with wrapper error ===")

        return error_message

    copied_files = route_standardized_outputs(
        staging_folder=staging_folder,
        raw_data_root=raw_data_root,
    )

    log(
        f"Standardized artifacts routed: "
        f"{copied_files}"
    )

    indexer_exit_code = run_script(
        script_path=FILE_INDEXER_SCRIPT,
        working_directory=SCRIPT_DIR,
        label="Raw_Data file indexer",
    )

    if indexer_exit_code != 0:
        error_message = (
            f"Raw_Data file indexer failed with "
            f"exit code {indexer_exit_code}"
        )

        log(error_message)
        return error_message

    log("=== Keyence pipeline finished successfully ===")

    return ""


def main() -> None:
    error_message = run_keyence_pipeline()

    if error_message:
        print(
            f"Keyence pipeline completed with error: "
            f"{error_message}",
            file=sys.stderr,
        )


if __name__ == "__main__":
    main()