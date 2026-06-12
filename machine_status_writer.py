from __future__ import annotations

"""
Writes one daily machine-status CSV for all configured Keyence machines.

Output example:
\\vt1.vitesco.com\SMT\didv0776\DataTransfer\Logs\AllMachines\
└── Keyence_2026_06_12.csv

Columns:
Date
Time
MachineName
MachineOn
NrLogsCopied
NrLogsDeleted
FreeMemory
Error
"""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import csv


COLUMNS = [
    "Date",
    "Time",
    "MachineName",
    "MachineOn",
    "NrLogsCopied",
    "NrLogsDeleted",
    "FreeMemory",
    "Error",
]


@dataclass
class MachineStatusRow:
    machine_name: str
    machine_on: int
    nr_logs_copied: int
    nr_logs_deleted: int
    free_memory: int | None
    error: str = ""


def get_current_date_and_time() -> tuple[str, str]:
    now = datetime.now()

    return (
        now.strftime("%Y-%m-%d"),
        now.strftime("%H:%M:%S"),
    )


def get_daily_status_file(
    output_folder: Path,
    file_prefix: str,
) -> Path:
    current_date, _ = get_current_date_and_time()

    file_date = current_date.replace(
        "-",
        "_",
    )

    return (
        output_folder
        / f"{file_prefix}_{file_date}.csv"
    )


def append_machine_status(
    output_folder: Path,
    file_prefix: str,
    status: MachineStatusRow,
) -> Path:
    """
    Appends one machine row to the daily Keyence status CSV.
    """

    output_folder.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_file = get_daily_status_file(
        output_folder=output_folder,
        file_prefix=file_prefix,
    )

    file_exists = output_file.is_file()

    current_date, current_time = (
        get_current_date_and_time()
    )

    with output_file.open(
        "a",
        newline="",
        encoding="utf-8",
    ) as file:
        writer = csv.writer(
            file
        )

        if not file_exists:
            writer.writerow(
                COLUMNS
            )

        writer.writerow(
            [
                current_date,
                current_time,
                status.machine_name,
                status.machine_on,
                status.nr_logs_copied,
                status.nr_logs_deleted,
                (
                    status.free_memory
                    if status.free_memory
                    is not None
                    else ""
                ),
                status.error,
            ]
        )

    print(
        f"Machine status written: "
        f"{output_file} | "
        f"{status.machine_name}"
    )

    return output_file