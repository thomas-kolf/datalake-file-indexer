from datetime import datetime
from pathlib import Path
from urllib.parse import quote
import csv
import boto3
import tomllib

CONFIG_PATH = "config.toml"
OUTPUT_CSV = "file_index.csv"

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
    with open(CONFIG_PATH, "rb") as file:
        return tomllib.load(file)


def build_download_link(file_path: str) -> str:
    encoded_path = quote(file_path, safe="")
    return f"datalakedownloader://download?path={encoded_path}"


def is_recipe_file(key: str) -> bool:
    return key.lower().endswith(".zit")


def detect_product_area(key: str, product_rules: dict) -> str:
    for recipe_folder, product_area in product_rules.items():
        if f"/{recipe_folder}/" in key:
            return product_area

    return "General"


def create_processed_key(source_key: str, to_be_processed_prefix: str, processed_prefix: str) -> str:
    relative_key = source_key.replace(to_be_processed_prefix, "", 1)
    parts = relative_key.split("/")

    if len(parts) >= 4 and parts[1] == "data_lake_ready":
        recipe_folder = parts[0]
        file_name = parts[-1]
        return f"{processed_prefix}{recipe_folder}/{file_name}"

    return f"{processed_prefix}{relative_key}"


def create_file_row(
    key: str,
    bucket: str,
    device: str,
    product_rules: dict,
    indexed_timestamp: str,
) -> dict:
    file_name = Path(key).name
    extension = Path(file_name).suffix.replace(".", "").lower()
    file_path = f"s3://{bucket}/{key}"

    return {
        "file_name": file_name,
        "extension": extension,
        "indexed_timestamp": indexed_timestamp,
        "device": device,
        "product_area": detect_product_area(key, product_rules),
        "file_path": file_path,
        "download_link": build_download_link(file_path),
    }


def collect_rows_for_device(
    s3_client,
    bucket: str,
    base_prefix: str,
    config: dict,
    product_rules: dict,
    indexed_timestamp: str,
) -> list[dict]:
    rows = []

    device_folder = config["folder"]
    to_be_processed_prefix = f"{base_prefix}/{device_folder}/toBeProcessed/"

    response = s3_client.list_objects_v2(
        Bucket=bucket,
        Prefix=to_be_processed_prefix,
    )

    for obj in response.get("Contents", []):
        key = obj["Key"]

        if key.endswith("/") or is_recipe_file(key):
            continue

        rows.append(
            create_file_row(
                key=key,
                bucket=bucket,
                device=config["device"],
                product_rules=product_rules,
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
    config = load_config()

    bucket = config["bucket"]
    base_prefix = config["base_prefix"]
    devices = config["devices"]
    product_rules = config.get("product_rules", {})

    indexed_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    s3_client = boto3.client("s3")

    all_rows = []

    for device_config in devices:
        all_rows.extend(
            collect_rows_for_device(
                s3_client=s3_client,
                bucket=bucket,
                base_prefix=base_prefix,
                config=device_config,
                product_rules=product_rules,
                indexed_timestamp=indexed_timestamp,
            )
        )

    write_csv(all_rows)

    print(f"Created {OUTPUT_CSV}")
    print(f"Indexed files: {len(all_rows)}")


if __name__ == "__main__":
    main()