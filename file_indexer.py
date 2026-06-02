from __future__ import annotations

"""
Creates a global searchable file index from permanent Raw_Data files.

The Data Lake is exposed by the Jupyter appliance as a normal filesystem:
    /mnt/639r-ait/...

The indexer:
- scans Raw_Data folders for all configured machines
- never moves or deletes permanent files
- generates one global file_index.csv
- writes the CSV directly into:
  /mnt/639r-ait/file_indexer/toBeProcessed/file_index.csv
"""

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
    relative_path = file_path.relative_to(mount_root).as_posix()

    return f"{base_prefix.strip('/')}/{relative_path}"


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
        "download_link": build_download_link(s3_path),
    }


def collect_rows_for_device(
    mount_root: Path,
    bucket: str,
    base_prefix: str,
    config: dict,
    product_rules: dict,
    indexed_timestamp: str,
) -> list[dict]:
    rows = []

    raw_data_folder = (
        mount_root
        / config["folder"]
        / "Raw_Data"
    )

    if not raw_data_folder.is_dir():
        print(f"Skipped missing Raw_Data folder: {raw_data_folder}")
        return rows

    for file_path in raw_data_folder.rglob("*"):
        if not file_path.is_file():
            continue

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

    print(f"Indexed {config['folder']}: {len(rows)} files")

    return rows


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
        writer.writerows(rows)


def run_file_indexer() -> Path:
    config = load_config()

    bucket = config["bucket"]
    base_prefix = config["base_prefix"]
    devices = config["devices"]
    product_rules = config.get("product_rules", {})

    runtime_paths = config["runtime_paths"]

    mount_root = Path(
        runtime_paths["mount_root"]
    )

    output_path = Path(
        runtime_paths["file_index_output"]
    )

    indexed_timestamp = datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    all_rows = []

    for device_config in devices:
        all_rows.extend(
            collect_rows_for_device(
                mount_root=mount_root,
                bucket=bucket,
                base_prefix=base_prefix,
                config=device_config,
                product_rules=product_rules,
                indexed_timestamp=indexed_timestamp,
            )
        )

    write_csv(
        rows=all_rows,
        output_path=output_path,
    )

    print(f"Created file index: {output_path}")
    print(f"Indexed files: {len(all_rows)}")

    return output_path


def main() -> None:
    run_file_indexer()


if __name__ == "__main__":
    try:
        main()

    except Exception as error:
        print(
            f"File indexer error: "
            f"{type(error).__name__}: {error}",
            file=sys.stderr,
        )

        raise