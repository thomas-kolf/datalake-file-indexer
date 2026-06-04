from __future__ import annotations

"""
Copies the finalized Keyence VR-5200 machine-drive content to the DiD drive.

Process:
1. Verify that V:/ exists.
2. Copy all files and all non-empty folders from V:/ to the DiD target.
3. Wait until Robocopy has finished.
4. Accept Robocopy exit codes 0-7 as successful.
5. Delete the transferred content from V:/ only after a successful copy.
6. Keep root-level *.zit recipe files on V:/.
7. Write CSV and Robocopy logs into the DiD log folder.

Important:
- The DiD target folder is expected to be empty before each run.
- No staging folder is used.
- /S copies folders containing files but skips empty folders.
"""

from datetime import datetime
from pathlib import Path
import csv
import shutil
import subprocess
import sys


SOURCE_ROOT = Path("V:/")

DID_TARGET = Path(
    r"\\vt1.vitesco.com\SMT\didv0776\DataTransfer\Keyence_VR5200_Data"
)

DID_LOG_ROOT = Path(
    r"\\vt1.vitesco.com\SMT\DIDV0776\DataTransfer\Logs\KeyenceVR5200"
)

MACHINE_NAME = "KeyenceVR5200"

PROTECTED_ROOT_FILE_SUFFIXES = {
    ".zit",
}

EXCLUDED_COPY_FOLDERS = [
    "System Volume Information",
    "$RECYCLE.BIN",
]


def get_timestamp() -> tuple[str, str]:
    now = datetime.now()

    return (
        now.strftime("%Y-%m-%d"),
        now.strftime("%H:%M:%S"),
    )


def append_csv_log(
    log_file: Path,
    action: str,
    item: str,
    result: str,
    error: str = "",
    machine_on: int = 1,
) -> None:
    """
    Appends one event to the daily transfer log.
    """

    current_date, current_time = get_timestamp()

    log_file.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    file_exists = log_file.is_file()

    with log_file.open(
        "a",
        newline="",
        encoding="utf-8",
    ) as file:
        writer = csv.writer(
            file
        )

        if not file_exists:
            writer.writerow(
                [
                    "Date",
                    "Time",
                    "MachineOn",
                    "Action",
                    "Item",
                    "Result",
                    "Error",
                ]
            )

        writer.writerow(
            [
                current_date,
                current_time,
                machine_on,
                action,
                item,
                result,
                error,
            ]
        )


def run_robocopy(
    source_root: Path,
    did_target: Path,
    robocopy_log: Path,
) -> int:
    """
    Copies all files and all non-empty folders from V:/ into DiD.

    Robocopy exit codes:
    0-7  = successful or acceptable result
    > 7  = failure
    """

    command = [
        "robocopy",
        str(source_root),
        str(did_target),
        "/S",
        "/COPY:DAT",
        "/DCOPY:T",
        "/R:2",
        "/W:2",
        "/XJ",
        "/XD",
        *EXCLUDED_COPY_FOLDERS,
        f"/LOG+:{robocopy_log}",
        "/TEE",
    ]

    result = subprocess.run(
        command,
        check=False,
    )

    return result.returncode


def delete_transferred_source_content(
    source_root: Path,
    csv_log_file: Path,
) -> bool:
    """
    Deletes transferred content from V:/ after successful Robocopy.

    Preserved:
    - root-level *.zit recipe files

    Deleted:
    - all other root-level files
    - all root-level folders
    """

    cleanup_successful = True

    for root_item in source_root.iterdir():
        try:
            if root_item.is_file():
                if (
                    root_item.suffix.lower()
                    in PROTECTED_ROOT_FILE_SUFFIXES
                ):
                    append_csv_log(
                        log_file=csv_log_file,
                        action="KEEP_FILE",
                        item=root_item.name,
                        result="OK",
                        error="RECIPE_FILE_KEPT",
                    )

                    continue

                root_item.unlink()

                append_csv_log(
                    log_file=csv_log_file,
                    action="DELETE_FILE",
                    item=root_item.name,
                    result="OK",
                )

                continue

            if root_item.is_dir():
                shutil.rmtree(
                    root_item
                )

                append_csv_log(
                    log_file=csv_log_file,
                    action="DELETE_FOLDER",
                    item=root_item.name,
                    result="OK",
                )

        except Exception as error:
            cleanup_successful = False

            append_csv_log(
                log_file=csv_log_file,
                action=(
                    "DELETE_FOLDER"
                    if root_item.is_dir()
                    else "DELETE_FILE"
                ),
                item=root_item.name,
                result="FAILED",
                error=(
                    f"{type(error).__name__}: "
                    f"{error}"
                ),
            )

    return cleanup_successful


def transfer_to_did() -> str:
    """
    Copies the finalized V:/ structure to DiD and then cleans V:/.

    Returns:
    - empty string if transfer and cleanup succeeded
    - error description otherwise
    """

    current_date, _ = get_timestamp()

    csv_log_file = (
        DID_LOG_ROOT
        / f"{MACHINE_NAME}_{current_date}.csv"
    )

    robocopy_log_file = (
        DID_LOG_ROOT
        / f"Robocopy_{MACHINE_NAME}_{current_date}.txt"
    )

    DID_LOG_ROOT.mkdir(
        parents=True,
        exist_ok=True,
    )

    if not SOURCE_ROOT.is_dir():
        error_message = (
            f"Source drive not found: "
            f"{SOURCE_ROOT}"
        )

        append_csv_log(
            log_file=csv_log_file,
            action="SRC_CHECK",
            item=str(SOURCE_ROOT),
            result="FAILED",
            error="SRC_NOT_FOUND",
            machine_on=0,
        )

        return error_message

    DID_TARGET.mkdir(
        parents=True,
        exist_ok=True,
    )

    print(
        f"Starting DiD transfer: "
        f"{SOURCE_ROOT} -> {DID_TARGET}"
    )

    robocopy_exit_code = run_robocopy(
        source_root=SOURCE_ROOT,
        did_target=DID_TARGET,
        robocopy_log=robocopy_log_file,
    )

    if robocopy_exit_code > 7:
        error_message = (
            f"Robocopy failed with "
            f"exit code {robocopy_exit_code}. "
            f"Nothing was deleted from {SOURCE_ROOT}"
        )

        append_csv_log(
            log_file=csv_log_file,
            action="COPY",
            item=str(SOURCE_ROOT),
            result="FAILED",
            error=f"ROBOCOPY_EXIT_{robocopy_exit_code}",
        )

        return error_message

    append_csv_log(
        log_file=csv_log_file,
        action="COPY",
        item=str(SOURCE_ROOT),
        result="OK",
        error=f"ROBOCOPY_EXIT_{robocopy_exit_code}",
    )

    print(
        f"DiD transfer completed with "
        f"Robocopy exit code {robocopy_exit_code}"
    )

    cleanup_successful = delete_transferred_source_content(
        source_root=SOURCE_ROOT,
        csv_log_file=csv_log_file,
    )

    if not cleanup_successful:
        error_message = (
            "DiD transfer succeeded, but one or more "
            "items could not be deleted from V:/"
        )

        append_csv_log(
            log_file=csv_log_file,
            action="FINISHED",
            item=MACHINE_NAME,
            result="FAILED",
            error="SOURCE_CLEANUP_INCOMPLETE",
        )

        return error_message

    append_csv_log(
        log_file=csv_log_file,
        action="FINISHED",
        item=MACHINE_NAME,
        result="OK",
    )

    print(
        "DiD transfer and source cleanup "
        "finished successfully"
    )

    return ""


def main() -> None:
    error_message = transfer_to_did()

    if error_message:
        print(
            f"DiD transfer completed with error: "
            f"{error_message}",
            file=sys.stderr,
        )

        raise SystemExit(1)


if __name__ == "__main__":
    main()