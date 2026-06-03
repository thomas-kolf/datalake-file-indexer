from __future__ import annotations

"""
Creates a searchable file_index.csv from one configured folder.

Local quick-export configuration:
- scans the configured folder recursively
- detects product_area from the folder structure
- writes one CSV row per file
- does not move, copy or delete files
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


def build_download_link(file_path: str) -> str:
    encoded_path = quote(file_path, safe="")

    return f"datalakedownloader://download?path={encoded_path}"


def detect_product_area(
    file_path: Path,
    product_rules: dict,
) -> str:
    path_text = file_path.as_posix().lower()

    for recipe_folder, product_area in product_rules.items():
        if recipe_folder.lower() in path_text:
            return product_area

    return "General"


def create_file_row(
    file_path: Path,
    device: str,
    product_rules: dict,
    indexed_timestamp: str,
) -> dict:
    path_text = str(file_path)

    return {
        "file_name": file_path.name,
        "extension": file_path.suffix.replace(".", "").lower(),
        "indexed_timestamp": indexed_timestamp,
        "device": device,
        "product_area": detect_product_area(
            file_path=file_path,
            product_rules=product_rules,
        ),
        "file_path": path_text,
        "download_link": build_download_link(path_text),
    }


def collect_rows(
    scan_folder: Path,
    device: str,
    product_rules: dict,
    indexed_timestamp: str,
) -> list[dict]:
    rows = []

    if not scan_folder.is_dir():
        raise FileNotFoundError(
            f"Scan folder not found: {scan_folder}"
        )

    for file_path in scan_folder.rglob("*"):
        if not file_path.is_file():
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


def main() -> None:
    config = load_config()

    scan_folder = Path(
        config["scan_folder"]
    )

    output_path = Path(
        config["file_index_output"]
    )

    device = config["device"]

    product_rules = config.get(
        "product_rules",
        {},
    )

    indexed_timestamp = datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    rows = collect_rows(
        scan_folder=scan_folder,
        device=device,
        product_rules=product_rules,
        indexed_timestamp=indexed_timestamp,
    )

    write_csv(
        rows=rows,
        output_path=output_path,
    )

    print(f"Scanned folder: {scan_folder}")
    print(f"Created file index: {output_path}")
    print(f"Indexed files: {len(rows)}")


if __name__ == "__main__":
    main()