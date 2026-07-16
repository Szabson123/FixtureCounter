import json
import os
import time
import uuid
from datetime import datetime


def clone_wats_report(source_data, output_folder, new_serial):
    """Klonuje raport WATS, podmieniając unikalne ID, Serial Number oraz czas startu."""
    # 1. Głęboka kopia słownika (żeby nie modyfikować oryginału w pamięci)
    cloned_data = json.loads(json.dumps(source_data))

    # 2. Generowanie nowego, w pełni unikalnego UUID (GUID)
    new_uuid = str(uuid.uuid4())
    cloned_data["id"] = new_uuid

    # 3. Podmiana numeru seryjnego
    cloned_data["sn"] = str(new_serial)

    # 4. Podmiana czasu na aktualny (format ISO 8601 z 'Z' na końcu dla UTC)
    current_time_iso = (
        datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S") + "Z"
    )  # Uwzględnia aktualny rok 2026
    cloned_data["start"] = current_time_iso
    cloned_data["startUTC"] = current_time_iso

    # 5. Upewnienie się, że folder docelowy istnieje
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    # 6. Zapis nowego pliku JSON
    file_name = f"report_sn_{new_serial}.json"
    full_path = os.path.join(output_folder, file_name)

    with open(full_path, "w", encoding="utf-8") as f:
        json.dump(cloned_data, f, indent=2, ensure_ascii=False)

    print(f" Sukces: Wygenerowano raport dla SN {new_serial} -> {full_path}")


# --- BAZOWY SZABLON Z TWOIMI PARAMETRAMI PROCESU ---
template_data = {
    "type": "T",
    "id": "00000000-0000-0000-0000-000000100005",
    "pn": "12345678A",
    "sn": "100005",
    "rev": "1.0",
    "processCode": 418,  # Twój nowy kod procesu (jako INT)
    "processName": "SzymTest",  # Twoja nowa nazwa procesu (musi się zgadzać 1:1!)
    "result": "P",
    "machineName": "CAL01",
    "location": "",
    "purpose": "",
    "start": "2026-07-13T09:00:00Z",
    "startUTC": "2026-07-13T09:00:00Z",
    "root": {
        "id": 0,
        "group": "M",
        "stepType": "SequenceCall",
        "name": "SzymTest",  # Zmienione na SzymTest dla spójności sekwencji
        "status": "P",
        "steps": [
            {
                "id": 1,
                "group": "M",
                "stepType": "ET_NLT",
                "name": "Imax (RST) (cos-37°=0.8c)",
                "status": "P",
                "numericMeas": [
                    {
                        "compOp": "GELE",
                        "status": "P",
                        "unit": "%",
                        "value": -0.05,
                        "lowLimit": -0.6,
                        "highLimit": 0.6,
                    }
                ],
            }
        ],
        "seqCall": {
            "path": "SzymTest",
            "name": "SzymTest",
            "version": "1.0.2",
        },
    },
    "uut": {"execTime": 12.45, "user": "Operator"},
}

target_dir = r"C:\WatsTransfer"

print(
    f"🚀 Rozpoczynam masowe generowanie 100 raportów dla procesu {template_data['processName']}..."
)

for i in range(100):
    current_sn = 200100 + i

    clone_wats_report(template_data, target_dir, new_serial=current_sn)

    time.sleep(1)

print(
    "\n✅ Gotowe! Wszystkie pliki zostały wrzucone. Szukaj w panelu WWW procesu 'SzymTest' lub stacji 'CAL01'."
)