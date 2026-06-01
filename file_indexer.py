from __future__ import annotations

"""Create and upload a global searchable file index from permanent Raw_Data objects."""

from argparse import ArgumentParser
from datetime import datetime
from pathlib import Path
from urllib.parse import quote
import csv
import sys

import boto3
import tomllib


CONFIG_PATH = "config.toml"
OUTPUT_CSV = "file_index.csv"

FILE_INDEX_TARGET_FOLDER = "file_indexer/toBeProcessed"

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


def detect_product_area(
    key: str,
    product_rules: dict,
) -> str:
    for recipe_folder, product_area in product_rules.items():
        if f"/{recipe_folder}/" in key:
            return product_area

    return "General"


def list_s3_objects(
    s3_client,
    bucket: str,
    prefix: str,
):
    paginator = s3_client.get_paginator("list_objects_v2")

    for page in paginator.paginate(
        Bucket=bucket,
        Prefix=prefix,
    ):
        yield from page.get("Contents", [])


def create_file_row(
    key: str,
    bucket: str,
    device: str,
    product_area: str,
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

    raw_data_prefix = (
        f"{base_prefix.strip('/')}/"
        f"{config['folder']}/"
        "Raw_Data/"
    )

    for obj in list_s3_objects(
        s3_client=s3_client,
        bucket=bucket,
        prefix=raw_data_prefix,
    ):
        key = obj["Key"]

        if key.endswith("/"):
            continue

        rows.append(
            create_file_row(
                key=key,
                bucket=bucket,
                device=config["device"],
                product_area=detect_product_area(
                    key=key,
                    product_rules=product_rules,
                ),
                indexed_timestamp=indexed_timestamp,
            )
        )

    print(f"Indexed {config['folder']}: {len(rows)} files")

    return rows


def write_csv(rows: list[dict]) -> Path:
    output_path = Path(OUTPUT_CSV)

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

    return output_path


def upload_csv(
    s3_client,
    bucket: str,
    base_prefix: str,
    output_path: Path,
    apply: bool,
) -> None:
    target_key = (
        f"{base_prefix.strip('/')}/"
        f"{FILE_INDEX_TARGET_FOLDER}/"
        f"{output_path.name}"
    )

    print(
        f"Upload index: {output_path} "
        f"-> s3://{bucket}/{target_key}"
    )

    if apply:
        s3_client.upload_file(
            str(output_path),
            bucket,
            target_key,
            ExtraArgs={"ContentType": "text/csv"},
        )


def parse_args():
    parser = ArgumentParser()

    parser.add_argument(
        "--dry-run",
        action="store_true",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = load_config()

    bucket = config["bucket"]
    base_prefix = config["base_prefix"]
    devices = config["devices"]
    product_rules = config.get("product_rules", {})

    indexed_timestamp = datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

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

    output_path = write_csv(all_rows)

    upload_csv(
        s3_client=s3_client,
        bucket=bucket,
        base_prefix=base_prefix,
        output_path=output_path,
        apply=not args.dry_run,
    )

    mode = "DRY RUN" if args.dry_run else "APPLIED"

    print(f"Created: {output_path}")
    print(f"Indexed files: {len(all_rows)}")
    print(f"File index upload: {mode}")


if __name__ == "__main__":
    try:
        main()

    except Exception as error:
        print(f"File indexer error: {error}", file=sys.stderr)
        raise