from pathlib import Path
import shutil
import subprocess

BASE_DIR = Path("test_upload")
S3_BASE = "s3://datalake-eu-central-1-vt-prod/639r-ait"

DEVICE_FOLDERS = [
    "Keyence_VR5200",
    "Keyence_LMX",
    "Keyence_VHX",
    "Olympus_DSX1000",
]

FILES = {
    "Keyence_VR5200/toBeProcessed/vr_test.xlsx": "vr test",
    "Keyence_LMX/toBeProcessed/lmx_test.csv": "lmx test",
    "Keyence_VHX/toBeProcessed/vhx_test.png": "vhx test",
    "Olympus_DSX1000/toBeProcessed/olympus_test.jpeg": "olympus test",
    "Keyence_VR5200/toBeProcessed/EMB_Gan_Prüfvorlage_zit/data_lake_ready/EMB_Gan_Prüfvorlage/gan_artifact.json": "gan artifact",
}


def reset_local_test_data() -> None:
    for device in DEVICE_FOLDERS:
        device_path = BASE_DIR / device

        if device_path.exists():
            shutil.rmtree(device_path, ignore_errors=True)

        (device_path / "toBeProcessed").mkdir(parents=True, exist_ok=True)
        (device_path / "processed").mkdir(parents=True, exist_ok=True)

    for relative_path, content in FILES.items():
        file_path = BASE_DIR / relative_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")


def reset_s3_test_data() -> None:
    for device in DEVICE_FOLDERS:
        subprocess.run(
            ["aws", "s3", "rm", f"{S3_BASE}/{device}/processed/", "--recursive"],
            check=True,
        )

    subprocess.run(
        ["aws", "s3", "cp", "--recursive", str(BASE_DIR), S3_BASE],
        check=True,
    )


def main() -> None:
    reset_local_test_data()
    print("Local test_upload reset and dummy files created.")

    reset_s3_test_data()
    print("S3 processed folders cleared and dummy files uploaded.")


if __name__ == "__main__":
    main()