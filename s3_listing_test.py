import boto3

BUCKET = "datalake-eu-central-1-vt-prod"
BASE_PREFIX = "639r-ait"

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


def list_files_for_device(s3_client, config: dict) -> None:
    print()
    print(f"Device: {config['device']}")
    print(f"Prefix: {config['prefix']}")

    response = s3_client.list_objects_v2(
        Bucket=BUCKET,
        Prefix=config["prefix"],
    )

    objects = response.get("Contents", [])

    if not objects:
        print("No files found.")
        return

    for obj in objects:
        key = obj["Key"]

        if key.endswith("/"):
            continue

        print(f"- {key}")


def main() -> None:
    s3_client = boto3.client("s3")

    for config in DEVICE_CONFIGS:
        list_files_for_device(s3_client, config)


if __name__ == "__main__":
    main()