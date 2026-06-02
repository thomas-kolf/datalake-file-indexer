from __future__ import annotations

"""
Creates and updates a global searchable file index from permanent Raw_Data files.

The Data Lake is exposed by the Jupyter appliance as a normal filesystem:
    /mnt/639r-ait/...

Daily behavior:
- scans only Raw_Data/<YYYYMMDD>/ for all configured machines
- additionally scans Raw_Data/Statistics/<YYYYMMDD>/ if it exists
- preserves historical rows from previous daily runs
- refreshes rows for the requested date if the same day is processed again
- never moves or deletes permanent files
- writes the CSV directly into:
  /mnt/639r-ait/file_indexer/toBeProcessed/file_index.csv
"""

from argparse import ArgumentParser
from datetime import datetime
from pathlib import Path
from urllib.parse import quote
import csv
import sys
import tomllib


SCRIPT_DIR = Path(__file__).resolve().parent
CONFIG_PATH = SCRIPT_DIR / "config.toml"

COLUMNS = [
    "file_name",
    "extension",
    "indexed_timestamp",
    "device",
    "product_area",
    "file_path",
    "download_link",
]


def load_config() -> dict:
    with CONFIG_PATH.open("rb") as file:
        return tomllib.load(file)


def validate_date_folder(date_folder: str) -> None:
    """
    Ensures that the requested daily folder uses YYYYMMDD format.
    """

    if len(date_folder) != 8 or not date_folder.isdigit():
        raise ValueError(
            "Date folder must use YYYYMMDD format."
        )


def build_download_link(file_path: str) -> str:
    encoded_path = quote(file_path, safe="")

    return f"datalakedownloader://download?path={encoded_path}"


def detect_product_area(
    relative_s3_key: str,
    product_rules: dict,
) -> str:
    for recipe_folder, product_area in product_rules.items():
        if f"/{recipe_folder}/" in f"/{relative_s3_key}/":
            return product_area

    return "General"


def build_s3_key(
    file_path: Path,
    mount_root: Path,
    base_prefix: str,
) -> str:
    relative_path = file_path.relative_to(
        mount_root
    ).as_posix()

    return (
        f"{base_prefix.strip('/')}/"
        f"{relative_path}"
    )


def create_file_row(
    file_path: Path,
    mount_root: Path,
    bucket: str,
    base_prefix: str,
    device: str,
    product_rules: dict,
    indexed_timestamp: str,
) -> dict:
    s3_key = build_s3_key(
        file_path=file_path,
        mount_root=mount_root,
        base_prefix=base_prefix,
    )

    s3_path = f"s3://{bucket}/{s3_key}"

    return {
        "file_name": file_path.name,
        "extension": file_path.suffix.replace(".", "").lower(),
        "indexed_timestamp": indexed_timestamp,
        "device": device,
        "product_area": detect_product_area(
            relative_s3_key=s3_key,
            product_rules=product_rules,
        ),
        "file_path": s3_path,
        "download_link": build_download_link(
            s3_path
        ),
    }


def collect_files_from_folder(
    folder: Path,
) -> list[Path]:
    """
    Returns all files below one folder.
    Missing folders are treated as empty.
    """

    if not folder.is_dir():
        return []

    return [
        file_path
        for file_path in folder.rglob("*")
        if file_path.is_file()
    ]


def collect_daily_files(
    raw_data_folder: Path,
    date_folder: str,
) -> list[Path]:
    """
    Collects files for one daily index run.

    Normal files:
        Raw_Data/<YYYYMMDD>/

    Statistics files:
        Raw_Data/Statistics/<YYYYMMDD>/
    """

    daily_folder = (
        raw_data_folder
        / date_folder
    )

    statistics_daily_folder = (
        raw_data_folder
        / "Statistics"
        / date_folder
    )

    collected_files = []

    collected_files.extend(
        collect_files_from_folder(
            daily_folder
        )
    )

    collected_files.extend(
        collect_files_from_folder(
            statistics_daily_folder
        )
    )

    unique_files = []
    seen_paths = set()

    for file_path in collected_files:
        resolved_path = file_path.resolve()

        if resolved_path in seen_paths:
            continue

        seen_paths.add(
            resolved_path
        )

        unique_files.append(
            file_path
        )

    return unique_files


def collect_rows_for_device(
    mount_root: Path,
    bucket: str,
    base_prefix: str,
    config: dict,
    product_rules: dict,
    indexed_timestamp: str,
    date_folder: str,
) -> list[dict]:
    rows = []

    raw_data_folder = (
        mount_root
        / config["folder"]
        / "Raw_Data"
    )

    if not raw_data_folder.is_dir():
        print(
            f"Skipped missing Raw_Data folder: "
            f"{raw_data_folder}"
        )

        return rows

    daily_files = collect_daily_files(
        raw_data_folder=raw_data_folder,
        date_folder=date_folder,
    )

    for file_path in daily_files:
        rows.append(
            create_file_row(
                file_path=file_path,
                mount_root=mount_root,
                bucket=bucket,
                base_prefix=base_prefix,
                device=config["device"],
                product_rules=product_rules,
                indexed_timestamp=indexed_timestamp,
            )
        )

    print(
        f"Indexed {config['folder']} "
        f"for {date_folder}: "
        f"{len(rows)} files"
    )

    return rows


def read_existing_rows(
    output_path: Path,
) -> list[dict]:
    """
    Reads the existing global index.

    If no file exists yet, an empty index is returned.
    """

    if not output_path.is_file():
        return []

    with output_path.open(
        "r",
        newline="",
        encoding="utf-8",
    ) as file:
        reader = csv.DictReader(
            file
        )

        return list(
            reader
        )


def build_daily_scope_prefixes(
    bucket: str,
    base_prefix: str,
    devices: list[dict],
    date_folder: str,
) -> list[str]:
    """
    Builds the S3 prefixes that belong to the requested daily run.

    These prefixes are removed from the existing CSV before the current
    daily state is inserted again.

    This prevents obsolete entries if the same day is processed repeatedly.
    """

    prefixes = []

    for device_config in devices:
        device_folder = device_config["folder"]

        prefixes.append(
            f"s3://{bucket}/"
            f"{base_prefix.strip('/')}/"
            f"{device_folder}/"
            f"Raw_Data/"
            f"{date_folder}/"
        )

        prefixes.append(
            f"s3://{bucket}/"
            f"{base_prefix.strip('/')}/"
            f"{device_folder}/"
            f"Raw_Data/"
            f"Statistics/"
            f"{date_folder}/"
        )

    return prefixes


def remove_existing_daily_rows(
    existing_rows: list[dict],
    daily_scope_prefixes: list[str],
) -> list[dict]:
    """
    Removes existing rows for the requested date.

    Historical rows from all other dates remain untouched.
    """

    retained_rows = []

    for row in existing_rows:
        file_path = row.get(
            "file_path",
            "",
        )

        belongs_to_current_daily_scope = any(
            file_path.startswith(prefix)
            for prefix in daily_scope_prefixes
        )

        if belongs_to_current_daily_scope:
            continue

        retained_rows.append(
            row
        )

    return retained_rows


def merge_rows(
    historical_rows: list[dict],
    daily_rows: list[dict],
) -> list[dict]:
    """
    Combines historical rows with the freshly indexed daily rows.

    file_path is used as the stable unique key.
    """

    rows_by_file_path = {}

    for row in historical_rows:
        file_path = row.get(
            "file_path"
        )

        if file_path:
            rows_by_file_path[
                file_path
            ] = row

    for row in daily_rows:
        rows_by_file_path[
            row["file_path"]
        ] = row

    return sorted(
        rows_by_file_path.values(),
        key=lambda row: row["file_path"],
    )


def write_csv(
    rows: list[dict],
    output_path: Path,
) -> None:
    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with output_path.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=COLUMNS,
        )

        writer.writeheader()
        writer.writerows(
            rows
        )


def run_file_indexer(
    date_folder: str | None = None,
) -> Path:
    """
    Updates the global index for one daily folder.

    If no date is supplied, today's YYYYMMDD folder is used.
    """

    if date_folder is None:
        date_folder = datetime.now().strftime(
            "%Y%m%d"
        )

    validate_date_folder(
        date_folder
    )

    config = load_config()

    bucket = config["bucket"]
    base_prefix = config["base_prefix"]
    devices = config["devices"]

    product_rules = config.get(
        "product_rules",
        {},
    )

    runtime_paths = config[
        "runtime_paths"
    ]

    mount_root = Path(
        runtime_paths["mount_root"]
    )

    output_path = Path(
        runtime_paths["file_index_output"]
    )

    indexed_timestamp = datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    daily_rows = []

    for device_config in devices:
        daily_rows.extend(
            collect_rows_for_device(
                mount_root=mount_root,
                bucket=bucket,
                base_prefix=base_prefix,
                config=device_config,
                product_rules=product_rules,
                indexed_timestamp=indexed_timestamp,
                date_folder=date_folder,
            )
        )

    existing_rows = read_existing_rows(
        output_path=output_path,
    )

    daily_scope_prefixes = build_daily_scope_prefixes(
        bucket=bucket,
        base_prefix=base_prefix,
        devices=devices,
        date_folder=date_folder,
    )

    historical_rows = remove_existing_daily_rows(
        existing_rows=existing_rows,
        daily_scope_prefixes=daily_scope_prefixes,
    )

    merged_rows = merge_rows(
        historical_rows=historical_rows,
        daily_rows=daily_rows,
    )

    write_csv(
        rows=merged_rows,
        output_path=output_path,
    )

    print(
        f"Updated file index: "
        f"{output_path}"
    )

    print(
        f"Daily folder: "
        f"{date_folder}"
    )

    print(
        f"Rows indexed during this run: "
        f"{len(daily_rows)}"
    )

    print(
        f"Historical rows retained: "
        f"{len(historical_rows)}"
    )

    print(
        f"Total rows in file index: "
        f"{len(merged_rows)}"
    )

    return output_path


def parse_args():
    parser = ArgumentParser()

    parser.add_argument(
        "--date",
        required=False,
        help=(
            "Daily folder to index. "
            "Format: YYYYMMDD. "
            "Defaults to today."
        ),
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    run_file_indexer(
        date_folder=args.date,
    )


if __name__ == "__main__":
    try:
        main()

    except Exception as error:
        print(
            f"File indexer error: "
            f"{type(error).__name__}: "
            f"{error}",
            file=sys.stderr,
        )

        raise