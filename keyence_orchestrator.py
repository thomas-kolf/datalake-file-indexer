from __future__ import annotations

"""
Runs the configured Keyence processing chain on the jump host.

Execution order:
1. Start the Keyence VR-5200 wrapper once.
2. Wait until the wrapper has finished.
3. Loop through all enabled machines.
4. Create one machine-specific file_index.csv.
5. Transfer that machine's finalized content into its DiD target.
6. Delete source content only after verified transfer.
7. Append one machine row to the daily Keyence status CSV.
8. Continue with the remaining machines if one machine fails.

The later upload from DiD into the Data Lake is handled separately.
"""

from datetime import datetime
from pathlib import Path
import subprocess
import sys

from file_indexer import (
    create_file_index_for_device,
    get_enabled_devices,
    get_free_memory,
    load_config,
)
from machine_status_writer import (
    MachineStatusRow,
    append_machine_status,
)
from transfer_to_did import (
    transfer_device_to_did,
)


SCRIPT_DIR = Path(__file__).resolve().parent

WRAPPER_REPO = Path(
    r"C:\keyence-pipeline\keyence-wrapper"
)

WRAPPER_MAIN = (
    WRAPPER_REPO
    / "main.py"
)


def timestamp() -> str:
    return datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )


def log(
    message: str,
) -> None:
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


def write_status_safely(
    status_output_folder: Path,
    status_file_prefix: str,
    status: MachineStatusRow,
) -> bool:
    """
    Writes one daily summary row without stopping other machines
    if the summary CSV itself cannot be written.
    """

    try:
        append_machine_status(
            output_folder=status_output_folder,
            file_prefix=status_file_prefix,
            status=status,
        )

        return True

    except Exception as error:
        log(
            f"Could not write machine status "
            f"for {status.machine_name}: "
            f"{type(error).__name__}: "
            f"{error}"
        )

        return False


def run_keyence_pipeline() -> list[str]:
    """
    Runs:
    wrapper
    -> machine loop
       -> indexer
       -> DiD transfer
       -> status CSV

    Returns a list of errors.
    An empty list means that all enabled machines completed successfully.
    """

    log(
        "=== Keyence pipeline started ==="
    )

    config = load_config()

    product_rules = config.get(
        "product_rules",
        {},
    )

    enabled_devices = get_enabled_devices(
        config
    )

    status_output_folder = Path(
        config["status"][
            "output_folder"
        ]
    )

    status_file_prefix = config[
        "status"
    ].get(
        "file_prefix",
        "Keyence",
    )

    detailed_log_root = Path(
        config["transfer"][
            "detailed_log_root"
        ]
    )

    errors = []

    wrapper_required = any(
        device_config.get(
            "run_wrapper",
            False,
        )
        for device_config in enabled_devices
    )

    wrapper_exit_code = 0

    if wrapper_required:
        wrapper_exit_code = run_script(
            script_path=WRAPPER_MAIN,
            working_directory=WRAPPER_REPO,
            label="Keyence VR-5200 wrapper",
        )

    for device_config in enabled_devices:
        device = device_config[
            "device"
        ]

        source_root = Path(
            device_config[
                "scan_folder"
            ]
        )

        free_memory = get_free_memory(
            source_root
        )

        log(
            f"--- Processing machine: "
            f"{device} ---"
        )

        if (
            device_config.get(
                "run_wrapper",
                False,
            )
            and wrapper_exit_code != 0
        ):
            error_message = (
                f"Wrapper failed with "
                f"exit code {wrapper_exit_code}. "
                f"Indexing and transfer were skipped."
            )

            log(
                f"{device}: "
                f"{error_message}"
            )

            status_written = write_status_safely(
                status_output_folder=status_output_folder,
                status_file_prefix=status_file_prefix,
                status=MachineStatusRow(
                    machine_name=device,
                    machine_on=(
                        1
                        if source_root.is_dir()
                        else 0
                    ),
                    nr_logs_copied=0,
                    nr_logs_deleted=0,
                    free_memory=free_memory,
                    error=error_message,
                ),
            )

            if not status_written:
                errors.append(
                    f"{device}: "
                    f"status CSV could not be written"
                )

            errors.append(
                f"{device}: "
                f"{error_message}"
            )

            continue

        index_result = create_file_index_for_device(
            device_config=device_config,
            product_rules=product_rules,
        )

        if not index_result.success:
            error_message = (
                f"Indexing failed: "
                f"{index_result.error}"
            )

            log(
                f"{device}: "
                f"{error_message}"
            )

            status_written = write_status_safely(
                status_output_folder=status_output_folder,
                status_file_prefix=status_file_prefix,
                status=MachineStatusRow(
                    machine_name=device,
                    machine_on=0,
                    nr_logs_copied=0,
                    nr_logs_deleted=0,
                    free_memory=index_result.free_memory,
                    error=error_message,
                ),
            )

            if not status_written:
                errors.append(
                    f"{device}: "
                    f"status CSV could not be written"
                )

            errors.append(
                f"{device}: "
                f"{error_message}"
            )

            continue

        transfer_result = transfer_device_to_did(
            device_config=device_config,
            detailed_log_root=detailed_log_root,
        )

        status_written = write_status_safely(
            status_output_folder=status_output_folder,
            status_file_prefix=status_file_prefix,
            status=MachineStatusRow(
                machine_name=device,
                machine_on=1,
                nr_logs_copied=(
                    transfer_result
                    .copied_files
                ),
                nr_logs_deleted=(
                    transfer_result
                    .deleted_files
                ),
                free_memory=(
                    index_result
                    .free_memory
                ),
                error=(
                    transfer_result
                    .error
                ),
            ),
        )

        if not status_written:
            errors.append(
                f"{device}: "
                f"status CSV could not be written"
            )

        if not transfer_result.success:
            errors.append(
                f"{device}: "
                f"{transfer_result.error}"
            )

            log(
                f"{device}: "
                f"{transfer_result.error}"
            )

            continue

        log(
            f"{device}: completed successfully | "
            f"copied={transfer_result.copied_files} | "
            f"deleted={transfer_result.deleted_files}"
        )

    if errors:
        log(
            "=== Keyence pipeline finished "
            "with one or more errors ==="
        )

    else:
        log(
            "=== Keyence pipeline finished "
            "successfully ==="
        )

    return errors


def main() -> None:
    errors = run_keyence_pipeline()

    if errors:
        print(
            "Keyence pipeline completed "
            "with errors:",
            file=sys.stderr,
        )

        for error in errors:
            print(
                f"- {error}",
                file=sys.stderr,
            )

        raise SystemExit(1)


if __name__ == "__main__":
    main()