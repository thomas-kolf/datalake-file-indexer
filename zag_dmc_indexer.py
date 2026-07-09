from pathlib import Path
import csv
from datetime import datetime
from openpyxl import load_workbook


# Für lokalen Test anpassen
SCAN_DIR = Path(r"C:\Test\zag_test")
OUTPUT_CSV = Path(r"C:\Test\zag_test\dmc_file_index.csv")
DEVICE = "KeyenceVR5200"


def read_dmcs_from_xlsx(xlsx_path: Path) -> list[tuple[str, str]]:
    """
    Reads DMC values from column A starting at A3.
    Stops at the first empty cell.
    Returns: [(dmc, source_cell), ...]
    """
    workbook = load_workbook(xlsx_path, read_only=True, data_only=True)

    try:
        sheet = workbook.active
        result = []

        row = 3
        while True:
            cell_ref = f"A{row}"
            value = sheet[cell_ref].value

            if value is None or str(value).strip() == "":
                break

            dmc = str(value).strip()
            result.append((dmc, cell_ref))
            row += 1

        return result

    finally:
        workbook.close()


def create_dmc_file_index(scan_dir: Path, output_csv: Path, device: str) -> None:
    rows = []
    indexed_timestamp = datetime.now().strftime("%d.%m.%Y %H:%M:%S")

    zag_files = list(scan_dir.rglob("*.zag"))

    if not zag_files:
        print(f"No .zag files found in: {scan_dir}")
        return

    for zag_path in zag_files:
        xlsx_path = zag_path.with_suffix(".xlsx")

        if not xlsx_path.exists():
            print(f"WARNING: Matching .xlsx missing for {zag_path.name}")
            continue

        dmcs = read_dmcs_from_xlsx(xlsx_path)

        if not dmcs:
            print(f"WARNING: No DMCs found in {xlsx_path.name}")
            continue

        for dmc, source_cell in dmcs:
            for linked_file in (xlsx_path, zag_path):
                rows.append({
                    "dmc": dmc,
                    "device": device,
                    "file_name": linked_file.name,
                    "extension": linked_file.suffix.lower(),
                    "source_xlsx": xlsx_path.name,
                    "source_cell": source_cell,
                    "indexed_timestamp": indexed_timestamp,
                })

    output_csv.parent.mkdir(parents=True, exist_ok=True)

    with output_csv.open("w", newline="", encoding="utf-8-sig") as csvfile:
        fieldnames = [
            "dmc",
            "device",
            "file_name",
            "extension",
            "source_xlsx",
            "source_cell",
            "indexed_timestamp",
        ]

        writer = csv.DictWriter(csvfile, fieldnames=fieldnames, delimiter=",")
        writer.writeheader()
        writer.writerows(rows)

    print(f"Created: {output_csv}")
    print(f"Rows written: {len(rows)}")


if __name__ == "__main__":
    create_dmc_file_index(SCAN_DIR, OUTPUT_CSV, DEVICE)