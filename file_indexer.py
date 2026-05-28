# Scans Data Lake machine folders for files inside toBeProcessed,
# detects whether files belong to a product-specific recipe folder
# or are general machine files, copies verified files into the
# corresponding processed folder structure, deletes the originals
# after successful verification, and generates a global
# Power BI-ready file_index.csv containing searchable file metadata
# and download links for downstream discovery and referencing.

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

    # Product-specific wrapper output:
    # Recipe_zit/data_lake_ready/ProductFolder/artifact
    # -> processed/Recipe_zit/artifact
    if len(parts) >= 4 and parts[1] == "data_lake_ready":
        recipe_folder = parts[0]
        file_name = parts[-1]
        return f"{processed_prefix}{recipe_folder}/{file_name}"

    # General files:
    # toBeProcessed/random.txt -> processed/random.txt
    return f"{processed_prefix}{relative_key}"


def object_exists(s3_client, bucket: str, key: str) -> bool:
    try:
        s3_client.head_object(Bucket=bucket, Key=key)
        return True
    except Exception:
        return False


def copy_and_verify_object(s3_client, bucket: str, source_key: str, target_key: str) -> bool:
    s3_client.copy_object(
        Bucket=bucket,
        CopySource={"Bucket": bucket, "Key": source_key},
        Key=target_key,
    )

    return object_exists(s3_client, bucket, target_key)


def create_file_row(
    target_key: str,
    bucket: str,
    device: str,
    product_area: str,
    indexed_timestamp: str,
) -> dict:
    file_name = Path(target_key).name
    extension = Path(file_name).suffix.replace(".", "").lower()
    file_path = f"s3://{bucket}/{target_key}"

    return {
        "file_name": file_name,
        "extension": extension,
        "indexed_timestamp": indexed_timestamp,
        "device": device,
        "product_area": product_area,
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
    processed_prefix = f"{base_prefix}/{device_folder}/processed/"

    response = s3_client.list_objects_v2(
        Bucket=bucket,
        Prefix=to_be_processed_prefix,
    )

    for obj in response.get("Contents", []):
        source_key = obj["Key"]

        if source_key.endswith("/") or is_recipe_file(source_key):
            continue

        product_area = detect_product_area(source_key, product_rules)

        target_key = create_processed_key(
            source_key=source_key,
            to_be_processed_prefix=to_be_processed_prefix,
            processed_prefix=processed_prefix,
        )

        copied_ok = copy_and_verify_object(
            s3_client=s3_client,
            bucket=bucket,
            source_key=source_key,
            target_key=target_key,
        )

        if not copied_ok:
            print(f"Copy verification failed: {source_key}")
            continue

        s3_client.delete_object(
            Bucket=bucket,
            Key=source_key,
        )

        print(f"Moved: {source_key} -> {target_key}")

        rows.append(
            create_file_row(
                target_key=target_key,
                bucket=bucket,
                device=config["device"],
                product_area=product_area,
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
    print(f"Moved and indexed files: {len(all_rows)}")


if __name__ == "__main__":
    main()