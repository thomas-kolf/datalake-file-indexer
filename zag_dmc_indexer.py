from pathlib import Path
import csv
import re
from datetime import date, datetime

from openpyxl import load_workbook


# Nur für einen lokalen Einzeltest relevant.
# Beim Import durch file_indexer.py werden diese Pfade nicht verwendet.
SCAN_DIR = Path(r"C:\Test\zag_test")
OUTPUT_DIR = Path(r"C:\Test\zag_test")
DEVICE = "KeyenceVR5200"


FIELDNAMES = [
    "dmc",
    "device",
    "file_name",
    "extension",
    "source_xlsx",
    "source_cell",
    "measurement_timestamp",
]


# Erkennt Zeitstempel innerhalb von Werten wie:
# VR-20251209_150020
# 20251209_150020
# 20251209-150020
TIMESTAMP_PATTERN = re.compile(
    r"(?<!\d)\d{8}[_-]\d{6}(?!\d)"
)


def is_timestamp_instead_of_dmc(
    value: object,
) -> bool:
    """
    Checks whether column A contains a timestamp-based value
    instead of an actual DMC.

    Examples recognized as timestamps:
        VR-20251209_150020
        20251209_150020
    """
    if isinstance(value, (datetime, date)):
        return True

    if value is None:
        return False

    text = str(value).strip()

    if text == "":
        return False

    return TIMESTAMP_PATTERN.search(text) is not None


def normalize_dmc(
    value: object,
) -> str:
    """
    Converts the Excel DMC value into a clean string.

    Example:
        96.0 -> 96
    """
    if isinstance(value, float) and value.is_integer():
        return str(int(value))

    return str(value).strip()


def format_measurement_timestamp(
    value: object,
) -> str:
    """
    Formats the measurement timestamp from column F.

    Output:
        DD.MM.YYYY HH:MM:SS
    """
    if value is None or str(value).strip() == "":
        return ""

    if isinstance(value, datetime):
        return value.strftime(
            "%d.%m.%Y %H:%M:%S"
        )

    if isinstance(value, date):
        return value.strftime(
            "%d.%m.%Y 00:00:00"
        )

    return str(value).strip()


def read_dmcs_from_xlsx(
    xlsx_path: Path,
) -> list[tuple[str, str, str]]:
    """
    Reads values from column A starting at A3.

    The measurement timestamp is read from column F
    in the same row.

    Examples:
        DMC from A3
        Measurement timestamp from F3

        DMC from A4
        Measurement timestamp from F4

    Reading stops at the first empty cell in column A.

    If column A contains a timestamp-based value instead
    of a DMC, the DMC is stored as:
        missing_dmc

    Returns:
        [
            (
                dmc,
                source_cell,
                measurement_timestamp,
            ),
            ...
        ]
    """
    workbook = load_workbook(
        xlsx_path,
        read_only=True,
        data_only=True,
    )

    try:
        sheet = workbook.active
        result: list[tuple[str, str, str]] = []

        row = 3

        while True:
            source_cell = f"A{row}"
            timestamp_cell = f"F{row}"

            dmc_value = sheet[source_cell].value
            timestamp_value = sheet[timestamp_cell].value

            if (
                dmc_value is None
                or str(dmc_value).strip() == ""
            ):
                break

            if is_timestamp_instead_of_dmc(
                dmc_value
            ):
                dmc = "missing_dmc"
            else:
                dmc = normalize_dmc(
                    dmc_value
                )

            measurement_timestamp = (
                format_measurement_timestamp(
                    timestamp_value
                )
            )

            result.append(
                (
                    dmc,
                    source_cell,
                    measurement_timestamp,
                )
            )

            row += 1

        return result

    finally:
        workbook.close()


def find_matching_xlsx(
    zag_path: Path,
) -> Path | None:
    """
    Finds the XLSX file belonging to a ZAG file.

    Supported filename variants:
        same_name.xlsx
        same_name_Haupt.xlsx

    If both files exist, same_name.xlsx is preferred.
    """
    normal_xlsx_path = zag_path.with_suffix(
        ".xlsx"
    )

    haupt_xlsx_path = zag_path.with_name(
        f"{zag_path.stem}_Haupt.xlsx"
    )

    if normal_xlsx_path.exists():
        return normal_xlsx_path

    if haupt_xlsx_path.exists():
        return haupt_xlsx_path

    return None


def create_dmc_file_index(
    scan_dir: Path,
    output_dir: Path,
    device: str,
) -> Path | None:
    """
    Scans the provided scan directory for .zag files.

    For each .zag file:
    - finds the matching .xlsx or _Haupt.xlsx
    - reads DMCs from column A
    - reads measurement timestamps from column F
    - writes one row for the .xlsx
    - writes one row for the .zag

    Output example:
        emb_dmc_search_index_20260710.csv
    """
    scan_dir = Path(scan_dir)
    output_dir = Path(output_dir)

    rows: list[dict[str, str]] = []

    index_date = datetime.now().strftime(
        "%Y%m%d"
    )

    output_csv = (
        output_dir
        / f"emb_dmc_search_index_{index_date}.csv"
    )

    zag_files = sorted(
        scan_dir.rglob("*.zag")
    )

    if not zag_files:
        print(
            f"No .zag files found in: "
            f"{scan_dir}"
        )
        return None

    for zag_path in zag_files:
        xlsx_path = find_matching_xlsx(
            zag_path
        )

        if xlsx_path is None:
            print(
                f"WARNING: Matching .xlsx missing for "
                f"{zag_path.name}. Expected either "
                f"{zag_path.stem}.xlsx or "
                f"{zag_path.stem}_Haupt.xlsx"
            )
            continue

        try:
            dmc_rows = read_dmcs_from_xlsx(
                xlsx_path
            )

        except Exception as error:
            print(
                f"ERROR: Could not read "
                f"{xlsx_path.name}: "
                f"{error}"
            )
            continue

        if not dmc_rows:
            print(
                f"WARNING: No usable rows found in "
                f"{xlsx_path.name}"
            )
            continue

        for (
            dmc,
            source_cell,
            measurement_timestamp,
        ) in dmc_rows:
            for linked_file in (
                xlsx_path,
                zag_path,
            ):
                rows.append(
                    {
                        "dmc": dmc,
                        "device": device,
                        "file_name": linked_file.name,
                        "extension": (
                            linked_file
                            .suffix
                            .lower()
                            .lstrip(".")
                        ),
                        "source_xlsx": xlsx_path.name,
                        "source_cell": source_cell,
                        "measurement_timestamp": (
                            measurement_timestamp
                        ),
                    }
                )

    if not rows:
        print(
            "No valid DMC rows found. "
            "No DMC index created."
        )
        return None

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    with output_csv.open(
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as csvfile:
        writer = csv.DictWriter(
            csvfile,
            fieldnames=FIELDNAMES,
            delimiter=",",
        )

        writer.writeheader()
        writer.writerows(rows)

    print(
        f"Created DMC index: "
        f"{output_csv}"
    )

    print(
        f"DMC index rows written: "
        f"{len(rows)}"
    )

    return output_csv


if __name__ == "__main__":
    create_dmc_file_index(
        scan_dir=SCAN_DIR,
        output_dir=OUTPUT_DIR,
        device=DEVICE,
    )