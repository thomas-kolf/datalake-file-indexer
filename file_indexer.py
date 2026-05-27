from pathlib import Path
from datetime import datetime
from urllib.parse import quote
import csv
import shutil

BASE_DIR = Path("data_lake_mock")

OUTPUT_DIR = BASE_DIR / "file_index_exports"

DEVICE_CONFIGS = [
    {
        "device": "Keyence VR5200",
        "folder": "Keyence_VR5200",
    },
    {
        "device": "Keyence LM-X",
        "folder": "Keyence_LMX",
    },
    {
        "device": "Olympus",
        "folder": "Olympus",
    },
]

COLUMNS = [
    "file_name",
    "extension",
    "indexed_timestamp",
    "device",
    "product_area",
    "file_path",
    "download_link",
]


def build_download_link(file_path: str) -> str:
    encoded_path = quote(file_path, safe="")
    return f"datalakedownloader://download?path={encoded_path}"


def detect_product_area(file_path: Path) -> str:
    path_text = str(file_path).lower()

    if "gan_emb" in path_text or "gan_celle" in path_text:
        return "GaN_Emb"

    return "General"


def process_device(config: dict, indexed_timestamp: str) -> list[dict]:
    rows = []

    device_folder = BASE_DIR / config["folder"]
    to_be_processed = device_folder / "to_be_processed"
    processed = device_folder / "processed"

    processed.mkdir(parents=True, exist_ok=True)

    if not to_be_processed.exists():
        print(f"Skipped missing folder: {to_be_processed}")
        return rows

    for source_path in to_be_processed.rglob("*"):
        if not source_path.is_file():
            continue

        relative_path = source_path.relative_to(to_be_processed)
        target_path = processed / relative_path
        target_path.parent.mkdir(parents=True, exist_ok=True)

        shutil.move(str(source_path), str(target_path))

        file_path = str(target_path)

        rows.append({
            "file_name": target_path.name,
            "extension": target_path.suffix.replace(".", "").lower(),
            "indexed_timestamp": indexed_timestamp,
            "device": config["device"],
            "product_area": detect_product_area(target_path),
            "file_path": file_path,
            "download_link": build_download_link(file_path),
        })

    return rows


def write_file_index(rows: list[dict]) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    output_path = OUTPUT_DIR / "file_index.csv"

    with output_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    return output_path


def main() -> None:
    indexed_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    all_rows = []

    for config in DEVICE_CONFIGS:
        all_rows.extend(process_device(config, indexed_timestamp))

    output_path = write_file_index(all_rows)

    print(f"Created: {output_path}")
    print(f"Indexed files: {len(all_rows)}")


if __name__ == "__main__":
    main()