from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import csv


REPORT_FOLDER = Path(
    r"\\vt1.vitesco.com\SMT\didv0776\DataTransfer\Logs\SmokeTests"
)

EXPECTED_INDEX_COLUMNS = [
    "file_name",
    "extension",
    "indexed_timestamp",
    "device",
    "product_area",
    "artifact_group_id",
    "file_path",
]


@dataclass
class SmokeTestRow:
    device: str
    check: str
    status: str
    details: str


def get_today_index_suffix() -> str:
    return datetime.now().strftime(
        "%Y%m%d"
    )


def build_expected_index_path(
    device_config: dict,
) -> Path:
    scan_folder = Path(
        device_config["scan_folder"]
    )

    index_output_folder = device_config.get(
        "index_output_folder",
        "Powerbi_Index",
    )

    index_output_file = device_config.get(
        "index_output_file",
        "file_index.csv",
    )

    base_output_path = (
        scan_folder
        / index_output_folder
        / index_output_file
    )

    date_suffix = get_today_index_suffix()

    return base_output_path.with_name(
        f"{base_output_path.stem}_{date_suffix}{base_output_path.suffix}"
    )


def check_index_file(
    device: str,
    index_file: Path,
) -> list[SmokeTestRow]:
    rows = []

    if not index_file.is_file():
        return [
            SmokeTestRow(
                device=device,
                check="file_index_exists",
                status="FAIL",
                details=str(index_file),
            )
        ]

    rows.append(
        SmokeTestRow(
            device=device,
            check="file_index_exists",
            status="OK",
            details=str(index_file),
        )
    )

    try:
        with index_file.open(
            "r",
            newline="",
            encoding="utf-8-sig",
        ) as file:
            reader = csv.DictReader(
                file,
                delimiter=",",
            )

            header = reader.fieldnames or []

            missing_columns = [
                column
                for column in EXPECTED_INDEX_COLUMNS
                if column not in header
            ]

            if missing_columns:
                rows.append(
                    SmokeTestRow(
                        device=device,
                        check="file_index_header",
                        status="FAIL",
                        details=(
                            "Missing columns: "
                            + ", ".join(missing_columns)
                        ),
                    )
                )

            else:
                rows.append(
                    SmokeTestRow(
                        device=device,
                        check="file_index_header",
                        status="OK",
                        details="Header readable",
                    )
                )

            row_count = sum(
                1
                for _ in reader
            )

            if row_count == 0:
                rows.append(
                    SmokeTestRow(
                        device=device,
                        check="file_index_rows",
                        status="WARNING",
                        details="Index exists but contains 0 data rows",
                    )
                )

            else:
                rows.append(
                    SmokeTestRow(
                        device=device,
                        check="file_index_rows",
                        status="OK",
                        details=f"Rows: {row_count}",
                    )
                )

    except Exception as error:
        rows.append(
            SmokeTestRow(
                device=device,
                check="file_index_readable",
                status="FAIL",
                details=f"{type(error).__name__}: {error}",
            )
        )

    return rows


def run_metrology_smoketest(
    config: dict,
) -> Path | None:
    """
    Writes a non-blocking smoke test report for all enabled
    metrology systems.

    Important:
    This is only a debug/report method.
    It does not stop copy/delete by itself.
    """

    report_rows: list[SmokeTestRow] = []

    enabled_devices = [
        device_config
        for device_config in config["devices"]
        if device_config.get(
            "enabled",
            False,
        )
    ]

    for device_config in enabled_devices:
        device = device_config["device"]
        scan_folder = Path(
            device_config["scan_folder"]
        )

        if scan_folder.is_dir():
            report_rows.append(
                SmokeTestRow(
                    device=device,
                    check="scan_folder_exists",
                    status="OK",
                    details=str(scan_folder),
                )
            )

        else:
            report_rows.append(
                SmokeTestRow(
                    device=device,
                    check="scan_folder_exists",
                    status="FAIL",
                    details=str(scan_folder),
                )
            )

        index_folder = (
            scan_folder
            / device_config.get(
                "index_output_folder",
                "Powerbi_Index",
            )
        )

        if index_folder.is_dir():
            report_rows.append(
                SmokeTestRow(
                    device=device,
                    check="Powerbi_Index_folder_exists",
                    status="OK",
                    details=str(index_folder),
                )
            )

        else:
            report_rows.append(
                SmokeTestRow(
                    device=device,
                    check="Powerbi_Index_folder_exists",
                    status="FAIL",
                    details=str(index_folder),
                )
            )

        index_file = build_expected_index_path(
            device_config
        )

        report_rows.extend(
            check_index_file(
                device=device,
                index_file=index_file,
            )
        )

    REPORT_FOLDER.mkdir(
        parents=True,
        exist_ok=True,
    )

    report_timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    report_path = (
        REPORT_FOLDER
        / f"MetrologySmokeTest_{report_timestamp}.csv"
    )

    with report_path.open(
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "timestamp",
                "device",
                "check",
                "status",
                "details",
            ],
            delimiter=",",
        )

        writer.writeheader()

        timestamp = datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        for row in report_rows:
            writer.writerow(
                {
                    "timestamp": timestamp,
                    "device": row.device,
                    "check": row.check,
                    "status": row.status,
                    "details": row.details,
                }
            )

    return report_path