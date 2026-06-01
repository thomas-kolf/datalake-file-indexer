from __future__ import annotations

"""
Upload the locally generated Keyence wrapper outputs into the S3 Data Lake structure.

Local test flow:
    keyence-wrapper/main.py
    -> local wrapper output folders
    -> this router
    -> S3 Raw_Data / toBeProcessed / Logs

Important:
- The wrapper itself remains unchanged.
- No local wrapper output is deleted by this first test version.
- S3 changes are only performed when --apply is supplied.
"""

from argparse import ArgumentParser
from pathlib import Path
import mimetypes
import sys

import boto3


BUCKET = "datalake-eu-central-1-vt-prod"
BASE_PREFIX = "639r-ait"
DEVICE_FOLDER = "Keyence_VR5200"

DEFAULT_WRAPPER_REPO = Path(r"C:\Users\uiv51287\keyence-wrapper")
DEFAULT_RECIPE_FOLDER = "EMB_Gan_Prüfvorlage_zit"

# The first existing candidate is used. Adjust only when your wrapper uses
# a different folder name.
DATA_LAKE_READY_CANDIDATES = [
    "data_lake_ready",
]

POWER_BI_READY_CANDIDATES = [
    "PowerBI_ready",
    "powerbi_ready",
    "power_bi_ready",
]

# These folders are copied below Raw_Data/YYYYMMDD/ as permanent reference
# outputs. Their folder names are intentionally retained to avoid collisions.
REFERENCE_OUTPUT_CANDIDATES = [
    "failed_process",
    "failed_processes",
    "no_dmc_related",
    "not_specifiable",
    "reports",
]

LOG_OUTPUT_CANDIDATES = [
    "Logs",
    "logs",
]


def normalize_prefix(value: str) -> str:
    return value.strip("/")


def join_key(*parts: str) -> str:
    return "/".join(normalize_prefix(part) for part in parts if part)


def find_existing_folder(base_folder: Path, candidates: list[str]) -> Path | None:
    for candidate in candidates:
        folder = base_folder / candidate
        if folder.is_dir():
            return folder
    return None


def iter_files(folder: Path):
    for path in folder.rglob("*"):
        if path.is_file():
            yield path


def list_s3_keys(s3_client, bucket: str, prefix: str) -> list[str]:
    keys: list[str] = []
    paginator = s3_client.get_paginator("list_objects_v2")

    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        keys.extend(obj["Key"] for obj in page.get("Contents", []))

    return keys


def delete_s3_prefix(s3_client, bucket: str, prefix: str, apply: bool) -> None:
    keys = list_s3_keys(s3_client, bucket, prefix)

    if not keys:
        print(f"No existing S3 objects to remove: s3://{bucket}/{prefix}")
        return

    print(f"Existing objects below s3://{bucket}/{prefix}: {len(keys)}")

    if not apply:
        print("DRY RUN: existing objects would be deleted before replacement.")
        return

    for start in range(0, len(keys), 1000):
        batch = keys[start:start + 1000]
        s3_client.delete_objects(
            Bucket=bucket,
            Delete={"Objects": [{"Key": key} for key in batch]},
        )

    print(f"Deleted old prefix contents: s3://{bucket}/{prefix}")


def upload_file(
    s3_client,
    bucket: str,
    local_file: Path,
    target_key: str,
    apply: bool,
) -> None:
    print(f"Upload: {local_file} -> s3://{bucket}/{target_key}")

    if not apply:
        return

    content_type, _ = mimetypes.guess_type(local_file.name)
    extra_args = {"ContentType": content_type} if content_type else None

    if extra_args:
        s3_client.upload_file(
            str(local_file),
            bucket,
            target_key,
            ExtraArgs=extra_args,
        )
    else:
        s3_client.upload_file(str(local_file), bucket, target_key)


def upload_tree(
    s3_client,
    bucket: str,
    source_folder: Path,
    target_prefix: str,
    apply: bool,
) -> int:
    uploaded = 0

    for local_file in iter_files(source_folder):
        relative_path = local_file.relative_to(source_folder).as_posix()
        target_key = join_key(target_prefix, relative_path)

        upload_file(
            s3_client=s3_client,
            bucket=bucket,
            local_file=local_file,
            target_key=target_key,
            apply=apply,
        )
        uploaded += 1

    return uploaded


def route_data_lake_ready(
    s3_client,
    wrapper_repo: Path,
    date_folder: str,
    recipe_folder: str,
    apply: bool,
) -> int:
    source_folder = find_existing_folder(wrapper_repo, DATA_LAKE_READY_CANDIDATES)

    if source_folder is None:
        print("Skipped: no local data_lake_ready folder found.")
        return 0

    target_prefix = join_key(
        BASE_PREFIX,
        DEVICE_FOLDER,
        "Raw_Data",
        date_folder,
        recipe_folder,
    ) + "/"

    # Replace the initially transferred raw recipe-folder contents with the
    # standardized wrapper outputs.
    delete_s3_prefix(
        s3_client=s3_client,
        bucket=BUCKET,
        prefix=target_prefix,
        apply=apply,
    )

    return upload_tree(
        s3_client=s3_client,
        bucket=BUCKET,
        source_folder=source_folder,
        target_prefix=target_prefix,
        apply=apply,
    )


def route_power_bi_csvs(
    s3_client,
    wrapper_repo: Path,
    recipe_folder: str,
    apply: bool,
) -> int:
    source_folder = find_existing_folder(wrapper_repo, POWER_BI_READY_CANDIDATES)

    if source_folder is None:
        print("Skipped: no local PowerBI_ready folder found.")
        return 0

    target_prefix = join_key(
        BASE_PREFIX,
        DEVICE_FOLDER,
        "toBeProcessed",
        recipe_folder,
    )

    uploaded = 0

    for local_file in iter_files(source_folder):
        if local_file.suffix.lower() != ".csv":
            continue

        # The BI queue contains the generated product CSVs directly.
        target_key = join_key(target_prefix, local_file.name)

        upload_file(
            s3_client=s3_client,
            bucket=BUCKET,
            local_file=local_file,
            target_key=target_key,
            apply=apply,
        )
        uploaded += 1

    return uploaded


def route_reference_outputs(
    s3_client,
    wrapper_repo: Path,
    date_folder: str,
    apply: bool,
) -> int:
    uploaded = 0

    for folder_name in REFERENCE_OUTPUT_CANDIDATES:
        source_folder = wrapper_repo / folder_name

        if not source_folder.is_dir():
            continue

        target_prefix = join_key(
            BASE_PREFIX,
            DEVICE_FOLDER,
            "Raw_Data",
            date_folder,
            folder_name,
        )

        uploaded += upload_tree(
            s3_client=s3_client,
            bucket=BUCKET,
            source_folder=source_folder,
            target_prefix=target_prefix,
            apply=apply,
        )

    return uploaded


def route_logs(
    s3_client,
    wrapper_repo: Path,
    apply: bool,
) -> int:
    uploaded = 0

    for folder_name in LOG_OUTPUT_CANDIDATES:
        source_folder = wrapper_repo / folder_name

        if not source_folder.is_dir():
            continue

        target_prefix = join_key(
            BASE_PREFIX,
            DEVICE_FOLDER,
            "Logs",
        )

        uploaded += upload_tree(
            s3_client=s3_client,
            bucket=BUCKET,
            source_folder=source_folder,
            target_prefix=target_prefix,
            apply=apply,
        )

    return uploaded


def route_wrapper_outputs(
    wrapper_repo: Path,
    date_folder: str,
    recipe_folder: str,
    apply: bool,
) -> None:
    s3_client = boto3.client("s3")

    print("\n=== Route standardized Keyence artifacts ===")
    ready_count = route_data_lake_ready(
        s3_client=s3_client,
        wrapper_repo=wrapper_repo,
        date_folder=date_folder,
        recipe_folder=recipe_folder,
        apply=apply,
    )

    print("\n=== Queue Power BI CSV files ===")
    power_bi_count = route_power_bi_csvs(
        s3_client=s3_client,
        wrapper_repo=wrapper_repo,
        recipe_folder=recipe_folder,
        apply=apply,
    )

    print("\n=== Route permanent reference outputs ===")
    reference_count = route_reference_outputs(
        s3_client=s3_client,
        wrapper_repo=wrapper_repo,
        date_folder=date_folder,
        apply=apply,
    )

    print("\n=== Route logs ===")
    log_count = route_logs(
        s3_client=s3_client,
        wrapper_repo=wrapper_repo,
        apply=apply,
    )

    mode = "APPLIED" if apply else "DRY RUN"
    print(f"\nRouting finished ({mode}).")
    print(f"Standardized artifacts: {ready_count}")
    print(f"Power BI queue CSV files: {power_bi_count}")
    print(f"Permanent reference files: {reference_count}")
    print(f"Log files: {log_count}")


def parse_args():
    parser = ArgumentParser()
    parser.add_argument(
        "--wrapper-repo",
        type=Path,
        default=DEFAULT_WRAPPER_REPO,
        help="Path to the local keyence-wrapper repository.",
    )
    parser.add_argument(
        "--date",
        required=True,
        help="Target YYYYMMDD folder below Raw_Data.",
    )
    parser.add_argument(
        "--recipe-folder",
        default=DEFAULT_RECIPE_FOLDER,
        help="Recipe folder used below Raw_Data and toBeProcessed.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually modify S3. Without this flag, only print planned actions.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if not args.wrapper_repo.is_dir():
        raise FileNotFoundError(f"Wrapper repository not found: {args.wrapper_repo}")

    if len(args.date) != 8 or not args.date.isdigit():
        raise ValueError("--date must use YYYYMMDD format.")

    route_wrapper_outputs(
        wrapper_repo=args.wrapper_repo,
        date_folder=args.date,
        recipe_folder=args.recipe_folder,
        apply=args.apply,
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"Router error: {error}", file=sys.stderr)
        raise
