from __future__ import annotations

"""
Runs the configured metrology preprocessing chain on the jump host.

Execution order:
1. Start the Keyence VR-5200 wrapper once if at least one enabled device requires it.
2. Wait until the wrapper has finished.
3. Loop through all enabled metrology devices.
4. Create one machine-specific file_index_YYYYMMDD.csv per device.
5. For Keyence VR-5200, the embedded DMC index is created inside the file indexer.
6. Write a non-blocking smoke test report for debugging.
7. Continue with the remaining machines if one machine fails.

Important:
This script does not copy, move or delete machine-drive content.
The final copy/delete step is handled by the central batch script.
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
from metrology_smoketest import (
    run_metrology_smoketest,
)


WRAPPER_REPO = Path(
    r"C:\Processing\keyence-pipeline\keyence-wrapper"
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


def run_keyence_pipeline() -> list[str]:
    """
    Runs:
    wrapper if required
    -> machine loop
       -> file indexer
    -> non-blocking smoke test report

    Returns a list of errors.
    An empty list means that all enabled machines were indexed successfully.
    """

    log(
        "=== Metrology preprocessing started ==="
    )

    config = load_config()

    product_rules = config.get(
        "product_rules",
        {},
    )

    enabled_devices = get_enabled_devices(
        config
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
            f"--- Indexing machine: "
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
                f"Indexing was skipped."
            )

            log(
                f"{device}: "
                f"{error_message}"
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

            errors.append(
                f"{device}: "
                f"{error_message}"
            )

            continue

        log(
            f"{device}: indexing completed successfully | "
            f"indexed_rows={index_result.indexed_rows} | "
            f"free_memory={free_memory}"
        )

    try:
        smoke_report_path = run_metrology_smoketest(
            config
        )

        if smoke_report_path is not None:
            log(
                f"Metrology smoke test report written: "
                f"{smoke_report_path}"
            )

    except Exception as error:
        log(
            f"Metrology smoke test could not be written: "
            f"{type(error).__name__}: "
            f"{error}"
        )

    if errors:
        log(
            "=== Metrology preprocessing finished "
            "with one or more errors ==="
        )

    else:
        log(
            "=== Metrology preprocessing finished "
            "successfully ==="
        )

    return errors


def main() -> None:
    errors = run_keyence_pipeline()

    if errors:
        print(
            "Metrology preprocessing completed "
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