from __future__ import annotations

"""
Creates a global searchable file_index.csv from finalized machine folders.

Current behavior:
- scans each configured machine folder recursively
- writes one CSV row per file
- detects product_area from configurable recipe-folder rules
- classifies all other files as General
- excludes configured folders such as:
  - Powerbi_Index
  - Powerbi_Details
- never moves, copies or deletes files
- writes one global CSV file into the configured Powerbi_Index folder

The file paths currently represent the jump-host folder structure.
The later transfer process can replace the jump-host prefix with the
corresponding Data-Lake prefix while preserving the relative path.
"""

from datetime import datetime
from pathlib import Path
from urllib.parse import quote
import csv
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


def detect_product_area(
    file_path: Path,
    product_rules: dict,
) -> str:
    """
    Detects whether a file belongs to a configured product-specific folder.

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


def is_inside_excluded_folder(
    file_path: Path,
    scan_folder: Path,
    excluded_folders: list[str],
) -> bool:
    """
    Prevents folders such as Powerbi_Index and Powerbi_Details
    from appearing in the searchable file index.
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


def collect_rows_for_device(
    scan_folder: Path,
    device: str,
    product_rules: dict,
    excluded_folders: list[str],
    indexed_timestamp: str,
) -> list[dict]:
    rows = []

    if not scan_folder.is_dir():
        raise FileNotFoundError(
            f"Scan folder not found: "
            f"{scan_folder}"
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

    print(
        f"Indexed {device}: "
        f"{len(rows)} files"
    )

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
        writer.writerows(
            rows
        )


def main() -> None:
    config = load_config()

    output_path = Path(
        config["file_index_output"]
    )

    product_rules = config.get(
        "product_rules",
        {},
    )

    devices = config[
        "devices"
    ]

    indexed_timestamp = datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    all_rows = []

    for device_config in devices:
        scan_folder = Path(
            device_config[
                "scan_folder"
            ]
        )

        device = device_config[
            "device"
        ]

        excluded_folders = device_config.get(
            "excluded_folders",
            [],
        )

        all_rows.extend(
            collect_rows_for_device(
                scan_folder=scan_folder,
                device=device,
                product_rules=product_rules,
                excluded_folders=excluded_folders,
                indexed_timestamp=indexed_timestamp,
            )
        )

    write_csv(
        rows=all_rows,
        output_path=output_path,
    )

    print(
        f"Created file index: "
        f"{output_path}"
    )

    print(
        f"Indexed files: "
        f"{len(all_rows)}"
    )


if __name__ == "__main__":
    main()