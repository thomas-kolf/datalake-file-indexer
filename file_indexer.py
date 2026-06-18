from __future__ import annotations

"""
Creates one searchable file_index_YYYYMMDD.csv per configured machine.

Behavior:
- scans each enabled machine folder recursively
- writes one CSV row per file
- optionally adds folder rows for:
  - Statistics/
  - Statistics/<YYYYMMDD>/
- detects product_area from configurable recipe-folder rules
- classifies all other files as General
- excludes configured folders such as:
  - Powerbi_Index
  - Powerbi_Details
  - Logs
- never moves, copies or deletes machine files
- continues processing other machines if one machine is unavailable
"""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import quote
import csv
import shutil
import sys
import tomllib


SCRIPT_DIR = Path(__file__).resolve().parent
CONFIG_PATH = SCRIPT_DIR / "config.toml"

STATISTICS_FOLDER_NAME = "Statistics"

COLUMNS = [
    "file_name",
    "extension",
    "indexed_timestamp",
    "device",
    "product_area",
    "file_path",
    "download_link",
]


@dataclass
class IndexResult:
    device: str
    success: bool
    output_path: Path | None
    indexed_rows: int
    free_memory: int | None
    error: str = ""


def load_config() -> dict:
    with CONFIG_PATH.open("rb") as file:
        return tomllib.load(file)


def build_download_link(
    file_path: str,
) -> str:
    encoded_path = quote(
        file_path,
        safe="",
    )

    return (
        f"datalakedownloader://download?"
        f"path={encoded_path}"
    )


def get_index_timestamp() -> str:
    """
    Timestamp format written into the CSV:
    DD.MM.YYYY HH:MM:SS
    """

    return datetime.now().strftime(
        "%d.%m.%Y %H:%M:%S"
    )


def get_index_file_date() -> str:
    """
    Date suffix for the output filename:
    YYYYMMDD
    """

    return datetime.now().strftime(
        "%Y%m%d"
    )


def build_dated_output_path(
    output_path: Path,
) -> Path:
    """
    Converts:
    file_index.csv
    ->
    file_index_YYYYMMDD.csv
    """

    date_suffix = get_index_file_date()

    return output_path.with_name(
        f"{output_path.stem}_{date_suffix}{output_path.suffix}"
    )


def detect_product_area(
    file_path: Path,
    product_rules: dict,
) -> str:
    """
    Detects whether a file belongs to a configured product folder.

    Example:
    EMB_Gan_Prüfvorlage_zit/
    -> EMB_Gan

    Files outside configured product folders:
    -> General
    """

    path_text = file_path.as_posix().lower()

    for recipe_folder, product_area in product_rules.items():
        if recipe_folder.lower() in path_text:
            return product_area

    return "General"


def is_date_folder_name(
    folder_name: str,
) -> bool:
    """
    Returns True only for YYYYMMDD folder names.
    """

    return (
        len(folder_name) == 8
        and folder_name.isdigit()
    )


def is_inside_excluded_folder(
    file_path: Path,
    scan_folder: Path,
    excluded_folders: list[str],
) -> bool:
    """
    Prevents excluded folders from appearing in the searchable index.
    """

    relative_path = file_path.relative_to(
        scan_folder
    )

    excluded_names = {
        folder_name.lower()
        for folder_name in excluded_folders
    }

    return any(
        part.lower() in excluded_names
        for part in relative_path.parts
    )


def create_file_row(
    file_path: Path,
    device: str,
    product_rules: dict,
    indexed_timestamp: str,
) -> dict:
    path_text = str(
        file_path
    )

    return {
        "file_name": file_path.name,
        "extension": (
            file_path
            .suffix
            .replace(".", "")
            .lower()
        ),
        "indexed_timestamp": indexed_timestamp,
        "device": device,
        "product_area": detect_product_area(
            file_path=file_path,
            product_rules=product_rules,
        ),
        "file_path": path_text,
        "download_link": build_download_link(
            path_text
        ),
    }


def create_folder_row(
    folder_path: Path,
    device: str,
    indexed_timestamp: str,
) -> dict:
    """
    Creates a searchable and downloadable folder reference.

    Used only for:
    - Statistics/
    - Statistics/<YYYYMMDD>/
    """

    path_text = str(
        folder_path
    )

    return {
        "file_name": folder_path.name,
        "extension": "folder",
        "indexed_timestamp": indexed_timestamp,
        "device": device,
        "product_area": "General",
        "file_path": path_text,
        "download_link": build_download_link(
            path_text
        ),
    }


def collect_statistics_folder_rows(
    scan_folder: Path,
    device: str,
    indexed_timestamp: str,
) -> list[dict]:
    """
    Adds folder references only for:
    - <scan_folder>/Statistics/
    - <scan_folder>/Statistics/<YYYYMMDD>/
    """

    rows = []

    statistics_root = (
        scan_folder
        / STATISTICS_FOLDER_NAME
    )

    if not statistics_root.is_dir():
        return rows

    rows.append(
        create_folder_row(
            folder_path=statistics_root,
            device=device,
            indexed_timestamp=indexed_timestamp,
        )
    )

    for date_folder in statistics_root.iterdir():
        if not date_folder.is_dir():
            continue

        if not is_date_folder_name(
            date_folder.name
        ):
            continue

        rows.append(
            create_folder_row(
                folder_path=date_folder,
                device=device,
                indexed_timestamp=indexed_timestamp,
            )
        )

    return rows


def collect_rows_for_device(
    scan_folder: Path,
    device: str,
    product_rules: dict,
    excluded_folders: list[str],
    include_statistics_folder_rows: bool,
    indexed_timestamp: str,
) -> list[dict]:
    rows = []

    if not scan_folder.is_dir():
        raise FileNotFoundError(
            f"Scan folder not found: "
            f"{scan_folder}"
        )

    if include_statistics_folder_rows:
        rows.extend(
            collect_statistics_folder_rows(
                scan_folder=scan_folder,
                device=device,
                indexed_timestamp=indexed_timestamp,
            )
        )

    for file_path in scan_folder.rglob("*"):
        if not file_path.is_file():
            continue

        if is_inside_excluded_folder(
            file_path=file_path,
            scan_folder=scan_folder,
            excluded_folders=excluded_folders,
        ):
            continue

        rows.append(
            create_file_row(
                file_path=file_path,
                device=device,
                product_rules=product_rules,
                indexed_timestamp=indexed_timestamp,
            )
        )

    return rows


def write_csv(
    rows: list[dict],
    output_path: Path,
) -> None:
    """
    Writes the generated CSV atomically.

    The old dated CSV is replaced only after the new temporary
    CSV was written successfully.
    """

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary_output_path = (
        output_path
        .with_suffix(".tmp")
    )

    with temporary_output_path.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=COLUMNS,
            delimiter=",",
        )

        writer.writeheader()
        writer.writerows(
            rows
        )

    temporary_output_path.replace(
        output_path
    )


def get_free_memory(
    machine_root: Path,
) -> int | None:
    """
    Returns free bytes on the drive containing the machine folder.
    """

    try:
        return shutil.disk_usage(
            machine_root
        ).free

    except Exception:
        return None


def create_file_index_for_device(
    device_config: dict,
    product_rules: dict,
) -> IndexResult:
    """
    Creates one machine-specific file_index_YYYYMMDD.csv.

    MachineOn logic:
    - success=True  -> machine folder reachable and index written
    - success=False -> machine folder unavailable or indexing failed
    """

    device = device_config["device"]

    scan_folder = Path(
        device_config["scan_folder"]
    )

    base_output_path = (
        scan_folder
        / device_config.get(
            "index_output_folder",
            "Powerbi_Index",
        )
        / device_config.get(
            "index_output_file",
            "file_index.csv",
        )
    )

    output_path = build_dated_output_path(
        base_output_path
    )

    indexed_timestamp = get_index_timestamp()

    if not scan_folder.is_dir():
        error_message = (
            f"Scan folder not found: "
            f"{scan_folder}"
        )

        print(
            f"{device}: "
            f"{error_message}"
        )

        return IndexResult(
            device=device,
            success=False,
            output_path=None,
            indexed_rows=0,
            free_memory=None,
            error=error_message,
        )

    free_memory = get_free_memory(
        scan_folder
    )

    try:
        rows = collect_rows_for_device(
            scan_folder=scan_folder,
            device=device,
            product_rules=product_rules,
            excluded_folders=device_config.get(
                "excluded_index_folders",
                [],
            ),
            include_statistics_folder_rows=device_config.get(
                "include_statistics_folder_rows",
                False,
            ),
            indexed_timestamp=indexed_timestamp,
        )

        write_csv(
            rows=rows,
            output_path=output_path,
        )

        print(
            f"Created file index for "
            f"{device}: "
            f"{output_path}"
        )

        print(
            f"Indexed rows for "
            f"{device}: "
            f"{len(rows)}"
        )

        return IndexResult(
            device=device,
            success=True,
            output_path=output_path,
            indexed_rows=len(rows),
            free_memory=free_memory,
        )

    except Exception as error:
        error_message = (
            f"{type(error).__name__}: "
            f"{error}"
        )

        print(
            f"File indexer error for "
            f"{device}: "
            f"{error_message}",
            file=sys.stderr,
        )

        return IndexResult(
            device=device,
            success=False,
            output_path=None,
            indexed_rows=0,
            free_memory=free_memory,
            error=error_message,
        )


def get_enabled_devices(
    config: dict,
) -> list[dict]:
    return [
        device_config
        for device_config in config["devices"]
        if device_config.get(
            "enabled",
            False,
        )
    ]


def main() -> None:
    """
    Standalone mode:
    creates an index for every enabled machine.
    """

    config = load_config()

    product_rules = config.get(
        "product_rules",
        {},
    )

    failed_devices = []

    for device_config in get_enabled_devices(
        config
    ):
        result = create_file_index_for_device(
            device_config=device_config,
            product_rules=product_rules,
        )

        if not result.success:
            failed_devices.append(
                result.device
            )

    if failed_devices:
        print(
            f"Indexing failed for: "
            f"{', '.join(failed_devices)}",
            file=sys.stderr,
        )

        raise SystemExit(1)


if __name__ == "__main__":
    main()