from datetime import datetime
from pathlib import Path
from urllib.parse import quote
import csv
import boto3

BUCKET = "datalake-eu-central-1-vt-prod"
BASE_PREFIX = "639r-ait"

OUTPUT_CSV = "file_index.csv"

DEVICE_CONFIGS = [
    {
        "device": "Keyence LM-X",
        "prefix": f"{BASE_PREFIX}/Keyence_LMX/toBeProcessed/",
    },
    {
        "device": "Olympus DSX1000",
        "prefix": f"{BASE_PREFIX}/Olympus_DSX1000/toBeProcessed/",
    },
    {
        "device": "Keyence VR5200",
        "prefix": f"{BASE_PREFIX}/Keyence_VR5200/toBeProcessed/",
    },
    {
        "device": "Keyence VHX",
        "prefix": f"{BASE_PREFIX}/Keyence_VHX/toBeProcessed/",
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


def detect_product_area(key: str) -> str:
    key_lower = key.lower()

    if "gan_emb" in key_lower or "gan_celle" in key_lower:
        return "GaN_Emb"

    return "General"


def create_file_row(obj: dict, device: str, indexed_timestamp: str) -> dict:
    key = obj["Key"]
    file_name = Path(key).name
    extension = Path(file_name).suffix.replace(".", "").lower()
    file_path = f"s3://{BUCKET}/{key}"

    return {
        "file_name": file_name,
        "extension": extension,
        "indexed_timestamp": indexed_timestamp,
        "device": device,
        "product_area": detect_product_area(key),
        "file_path": file_path,
        "download_link": build_download_link(file_path),
    }


def collect_rows_for_device(s3_client, config: dict, indexed_timestamp: str) -> list[dict]:
    rows = []

    response = s3_client.list_objects_v2(
        Bucket=BUCKET,
        Prefix=config["prefix"],
    )

    for obj in response.get("Contents", []):
        key = obj["Key"]

        if key.endswith("/"):
            continue

        rows.append(
            create_file_row(
                obj=obj,
                device=config["device"],
                indexed_timestamp=indexed_timestamp,
            )
        )

    return rows


def write_csv(rows: list[dict]) -> None:
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    indexed_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    s3_client = boto3.client("s3")

    all_rows = []

    for config in DEVICE_CONFIGS:
        all_rows.extend(
            collect_rows_for_device(
                s3_client=s3_client,
                config=config,
                indexed_timestamp=indexed_timestamp,
            )
        )

    write_csv(all_rows)

    print(f"Created {OUTPUT_CSV}")
    print(f"Indexed files: {len(all_rows)}")


if __name__ == "__main__":
    main()