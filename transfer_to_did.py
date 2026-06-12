from __future__ import annotations

"""
Copies finalized machine-drive content to configured DiD targets.

Process for each enabled machine:
1. Verify that the source drive exists.
2. Copy all files and all non-empty folders to the configured DiD target.
3. Wait until Robocopy has finished.
4. Accept Robocopy exit codes 0-7 as successful.
5. Verify that every intended source file exists in the DiD target.
6. Delete transferred source content only after verified transfer.
7. Preserve configured root-level files such as *.zit recipes.
8. Return copied and deleted artifact counters.

Important:
- The DiD target folder is expected to be empty before each run.
- No staging folder is used.
- /S copies folders containing files but skips empty folders.
- Root-level preserved files are copied but excluded from copied/deleted counters.
"""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import csv
import shutil
import subprocess
import sys

from file_indexer import get_enabled_devices, load_config


@dataclass
class TransferResult:
    device: str
    success: bool
    copied_files: int
    deleted_files: int
    error: str = ""


def get_timestamp() -> tuple[str, str]:
    now = datetime.now()

    return (
        now.strftime("%Y-%m-%d"),
        now.strftime("%H:%M:%S"),
    )


def append_detailed_csv_log(
    log_file: Path,
    action: str,
    item: str,
    result: str,
    error: str = "",
    machine_on: int = 1,
) -> None:
    """
    Appends one event to the machine-specific daily transfer log.
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


def is_inside_excluded_folder(
    file_path: Path,
    source_root: Path,
    excluded_folders: list[str],
) -> bool:
    relative_path = file_path.relative_to(
        source_root
    )

    excluded_names = {
        folder_name.lower()
        for folder_name in excluded_folders
    }

    return any(
        part.lower() in excluded_names
        for part in relative_path.parts
    )


def is_preserved_root_file(
    file_path: Path,
    source_root: Path,
    preserve_suffixes: list[str],
) -> bool:
    """
    Returns True only for preserved files directly below the source root.

    Example:
    V:/EMB_Gan_Prüfvorlage.zit
    """

    return (
        file_path.parent == source_root
        and file_path.suffix.lower()
        in {
            suffix.lower()
            for suffix in preserve_suffixes
        }
    )


def collect_transfer_files(
    source_root: Path,
    excluded_folders: list[str],
) -> list[Path]:
    """
    Returns every source file that Robocopy is expected to transfer.
    """

    files = []

    for file_path in source_root.rglob("*"):
        if not file_path.is_file():
            continue

        if is_inside_excluded_folder(
            file_path=file_path,
            source_root=source_root,
            excluded_folders=excluded_folders,
        ):
            continue

        files.append(
            file_path
        )

    return files


def count_artifact_files(
    files: list[Path],
    source_root: Path,
    preserve_suffixes: list[str],
) -> int:
    """
    Counts transferable artifacts.

    Preserved root-level recipe files are intentionally excluded
    from the copied/deleted counters.
    """

    return sum(
        1
        for file_path in files
        if not is_preserved_root_file(
            file_path=file_path,
            source_root=source_root,
            preserve_suffixes=preserve_suffixes,
        )
    )


def run_robocopy(
    source_root: Path,
    did_target: Path,
    robocopy_log: Path,
    excluded_folders: list[str],
) -> int:
    """
    Copies all files and all non-empty folders into DiD.

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
    ]

    if excluded_folders:
        command.extend(
            [
                "/XD",
                *excluded_folders,
            ]
        )

    command.extend(
        [
            f"/LOG+:{robocopy_log}",
            "/TEE",
        ]
    )

    result = subprocess.run(
        command,
        check=False,
    )

    return result.returncode


def verify_transferred_files(
    source_files: list[Path],
    source_root: Path,
    did_target: Path,
) -> list[Path]:
    """
    Returns files that are missing from the DiD target after Robocopy.
    """

    missing_files = []

    for source_file in source_files:
        relative_path = source_file.relative_to(
            source_root
        )

        target_file = (
            did_target
            / relative_path
        )

        if not target_file.is_file():
            missing_files.append(
                target_file
            )

    return missing_files


def count_files_in_folder(
    folder: Path,
) -> int:
    return sum(
        1
        for path in folder.rglob("*")
        if path.is_file()
    )


def delete_transferred_source_content(
    source_root: Path,
    detailed_csv_log_file: Path,
    preserve_suffixes: list[str],
    excluded_folders: list[str],
) -> tuple[bool, int]:
    """
    Deletes transferred content after successful copy verification.

    Preserved:
    - configured root-level files such as *.zit recipes
    - configured excluded folders

    Deleted:
    - all other root-level files
    - all other root-level folders

    Returns:
    - cleanup success
    - number of deleted artifact files
    """

    cleanup_successful = True
    deleted_files = 0

    excluded_names = {
        folder_name.lower()
        for folder_name in excluded_folders
    }

    for root_item in source_root.iterdir():
        try:
            if (
                root_item.is_dir()
                and root_item.name.lower()
                in excluded_names
            ):
                append_detailed_csv_log(
                    log_file=detailed_csv_log_file,
                    action="KEEP_FOLDER",
                    item=root_item.name,
                    result="OK",
                    error="EXCLUDED_FOLDER_KEPT",
                )

                continue

            if root_item.is_file():
                if is_preserved_root_file(
                    file_path=root_item,
                    source_root=source_root,
                    preserve_suffixes=preserve_suffixes,
                ):
                    append_detailed_csv_log(
                        log_file=detailed_csv_log_file,
                        action="KEEP_FILE",
                        item=root_item.name,
                        result="OK",
                        error="PRESERVED_ROOT_FILE",
                    )

                    continue

                root_item.unlink()

                deleted_files += 1

                append_detailed_csv_log(
                    log_file=detailed_csv_log_file,
                    action="DELETE_FILE",
                    item=root_item.name,
                    result="OK",
                )

                continue

            if root_item.is_dir():
                folder_file_count = count_files_in_folder(
                    root_item
                )

                shutil.rmtree(
                    root_item
                )

                deleted_files += folder_file_count

                append_detailed_csv_log(
                    log_file=detailed_csv_log_file,
                    action="DELETE_FOLDER",
                    item=root_item.name,
                    result="OK",
                    error=(
                        f"DELETED_FILES_"
                        f"{folder_file_count}"
                    ),
                )

        except Exception as error:
            cleanup_successful = False

            append_detailed_csv_log(
                log_file=detailed_csv_log_file,
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

    return (
        cleanup_successful,
        deleted_files,
    )


def transfer_device_to_did(
    device_config: dict,
    detailed_log_root: Path,
) -> TransferResult:
    """
    Transfers one machine folder into its configured DiD target.
    """

    device = device_config["device"]

    source_root = Path(
        device_config["scan_folder"]
    )

    did_target = Path(
        device_config["did_target"]
    )

    preserve_suffixes = device_config.get(
        "preserve_root_file_suffixes",
        [],
    )

    excluded_folders = device_config.get(
        "excluded_copy_folders",
        [],
    )

    current_date, _ = get_timestamp()

    detailed_machine_log_root = (
        detailed_log_root
        / device
    )

    detailed_csv_log_file = (
        detailed_machine_log_root
        / f"{device}_{current_date}.csv"
    )

    robocopy_log_file = (
        detailed_machine_log_root
        / f"Robocopy_{device}_{current_date}.txt"
    )

    detailed_machine_log_root.mkdir(
        parents=True,
        exist_ok=True,
    )

    if not source_root.is_dir():
        error_message = (
            f"Source drive not found: "
            f"{source_root}"
        )

        append_detailed_csv_log(
            log_file=detailed_csv_log_file,
            action="SRC_CHECK",
            item=str(source_root),
            result="FAILED",
            error="SRC_NOT_FOUND",
            machine_on=0,
        )

        return TransferResult(
            device=device,
            success=False,
            copied_files=0,
            deleted_files=0,
            error=error_message,
        )

    did_target.mkdir(
        parents=True,
        exist_ok=True,
    )

    source_files = collect_transfer_files(
        source_root=source_root,
        excluded_folders=excluded_folders,
    )

    expected_artifact_count = count_artifact_files(
        files=source_files,
        source_root=source_root,
        preserve_suffixes=preserve_suffixes,
    )

    print(
        f"Starting DiD transfer for "
        f"{device}: "
        f"{source_root} -> {did_target}"
    )

    robocopy_exit_code = run_robocopy(
        source_root=source_root,
        did_target=did_target,
        robocopy_log=robocopy_log_file,
        excluded_folders=excluded_folders,
    )

    if robocopy_exit_code > 7:
        error_message = (
            f"Robocopy failed with "
            f"exit code {robocopy_exit_code}. "
            f"Nothing was deleted from "
            f"{source_root}"
        )

        append_detailed_csv_log(
            log_file=detailed_csv_log_file,
            action="COPY",
            item=str(source_root),
            result="FAILED",
            error=(
                f"ROBOCOPY_EXIT_"
                f"{robocopy_exit_code}"
            ),
        )

        return TransferResult(
            device=device,
            success=False,
            copied_files=0,
            deleted_files=0,
            error=error_message,
        )

    missing_target_files = verify_transferred_files(
        source_files=source_files,
        source_root=source_root,
        did_target=did_target,
    )

    if missing_target_files:
        error_message = (
            f"Transfer verification failed. "
            f"Missing target files: "
            f"{len(missing_target_files)}. "
            f"Nothing was deleted from "
            f"{source_root}"
        )

        append_detailed_csv_log(
            log_file=detailed_csv_log_file,
            action="VERIFY_COPY",
            item=str(source_root),
            result="FAILED",
            error=(
                f"MISSING_TARGET_FILES_"
                f"{len(missing_target_files)}"
            ),
        )

        return TransferResult(
            device=device,
            success=False,
            copied_files=0,
            deleted_files=0,
            error=error_message,
        )

    append_detailed_csv_log(
        log_file=detailed_csv_log_file,
        action="COPY",
        item=str(source_root),
        result="OK",
        error=(
            f"ROBOCOPY_EXIT_"
            f"{robocopy_exit_code}"
        ),
    )

    print(
        f"Verified transferred artifacts for "
        f"{device}: "
        f"{expected_artifact_count}"
    )

    (
        cleanup_successful,
        deleted_files,
    ) = delete_transferred_source_content(
        source_root=source_root,
        detailed_csv_log_file=detailed_csv_log_file,
        preserve_suffixes=preserve_suffixes,
        excluded_folders=excluded_folders,
    )

    if not cleanup_successful:
        error_message = (
            f"Transfer succeeded for "
            f"{device}, but one or more "
            f"source items could not be deleted."
        )

        append_detailed_csv_log(
            log_file=detailed_csv_log_file,
            action="FINISHED",
            item=device,
            result="FAILED",
            error="SOURCE_CLEANUP_INCOMPLETE",
        )

        return TransferResult(
            device=device,
            success=False,
            copied_files=expected_artifact_count,
            deleted_files=deleted_files,
            error=error_message,
        )

    append_detailed_csv_log(
        log_file=detailed_csv_log_file,
        action="FINISHED",
        item=device,
        result="OK",
    )

    print(
        f"DiD transfer and source cleanup "
        f"finished successfully for "
        f"{device}"
    )

    return TransferResult(
        device=device,
        success=True,
        copied_files=expected_artifact_count,
        deleted_files=deleted_files,
    )


def main() -> None:
    """
    Standalone mode:
    transfers every enabled machine independently.
    """

    config = load_config()

    detailed_log_root = Path(
        config["transfer"][
            "detailed_log_root"
        ]
    )

    failed_devices = []

    for device_config in get_enabled_devices(
        config
    ):
        result = transfer_device_to_did(
            device_config=device_config,
            detailed_log_root=detailed_log_root,
        )

        if not result.success:
            failed_devices.append(
                result.device
            )

    if failed_devices:
        print(
            f"Transfer failed for: "
            f"{', '.join(failed_devices)}",
            file=sys.stderr,
        )

        raise SystemExit(1)


if __name__ == "__main__":
    main()