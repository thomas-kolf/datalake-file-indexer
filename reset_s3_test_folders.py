import subprocess


S3_BASE = "s3://datalake-eu-central-1-vt-prod/639r-ait"

DEVICE_FOLDERS = [
    "Keyence_VR5200",
    "Keyence_LMX",
    "Keyence_VHX",
    "Olympus_DSX1000",
]

# Hier einfach festlegen, welche Unterordner geleert werden sollen.
SUBFOLDERS_TO_DELETE = [
    "Raw_Data",
    "toBeProcessed",
    "processed",
]


def delete_s3_folder(device: str, subfolder: str) -> None:
    s3_path = f"{S3_BASE}/{device}/{subfolder}/"

    print(f"Deleting: {s3_path}")

    subprocess.run(
        ["aws", "s3", "rm", s3_path, "--recursive"],
        check=True,
    )


def main() -> None:
    for device in DEVICE_FOLDERS:
        for subfolder in SUBFOLDERS_TO_DELETE:
            delete_s3_folder(device, subfolder)

    print("S3 test folders cleared.")


if __name__ == "__main__":
    main()