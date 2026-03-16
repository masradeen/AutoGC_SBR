import sys
import time
import re
import base64
import json
import os
import argparse
from rapidfuzz import fuzz
import pandas as pd
from login import login_with_sso
import getpass

RESUME_FILE = "baris.txt"
MASTER_WILAYAH_FILE = "tambahUsaha\master_wilayah_gorontalo.json"
MAX_SIMILARITY = 85

def clean_text(text):
    cleaned = re.sub(r'[^\x20-\x7E\u00C0-\u024F]', '', str(text))
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned

def similarity(a, b):
    return fuzz.token_sort_ratio(a, b)

def find_ids(master, kab_code, kec_code, desa_code):
    """Mencari ID internal berdasarkan kode BPS dari CSV"""
    res = {"kab_id": None, "kec_id": None, "desa_id": None}
    
    # Normalisasi kode (misal: '71' tetap '71', '5' jadi '005')
    kab_code = str(kab_code).strip().zfill(2)
    kec_code = str(kec_code).strip().zfill(3)
    desa_code = str(desa_code).strip().zfill(3)

    # 1. Cari Kabupaten
    kab_obj = next((k for k in master if str(k['kode']) == kab_code), None)
    if not kab_obj: return res
    res["kab_id"] = kab_obj['id']

    # 2. Cari Kecamatan
    kec_obj = next((kc for kc in kab_obj['kecamatan'] if str(kc['kode']) == kec_code), None)
    if not kec_obj: return res
    res["kec_id"] = kec_obj['id']

    # 3. Cari Desa
    desa_obj = next((d for d in kec_obj['desa'] if str(d['kode']) == desa_code), None)
    if desa_obj:
        res["desa_id"] = desa_obj['id']
    
    return res

def main():
    parser = argparse.ArgumentParser(description="Tambah usaha ke SBR via Matcha Pro")
    parser.add_argument("--csv", required=True, help="Nama file CSV yang akan dikirim")
    args = parser.parse_args()

    # Load Master Wilayah Gorontalo
    if not os.path.exists(MASTER_WILAYAH_FILE):
        print(f"Error: File '{MASTER_WILAYAH_FILE}' tidak ditemukan!")
        return
    with open(MASTER_WILAYAH_FILE, "r") as f:
        master_wilayah = json.load(f)

    username = input("Masukkan Username SSO: ").strip()
    password = getpass.getpass("Masukkan Password SSO: ")
    otp_code = sys.argv[3] if len(sys.argv) > 3 else None
    csv_file = args.csv

    page, browser = login_with_sso(username, password, otp_code)

    if page:
        try:
            url_gc = "https://matchapro.web.bps.go.id/dirgc"
            page.goto(url_gc)
            page.wait_for_load_state('networkidle')
            page.wait_for_selector('meta[name="csrf-token"]', state='attached', timeout=10000)

            _token = page.locator('meta[name="csrf-token"]').get_attribute('content')
            print(f"Extracted _token: {_token}")

            # Baca file CSV
            df = pd.read_csv(csv_file, dtype=str) # Force string untuk kode wilayah
            print(f"Loaded {len(df)} rows from {csv_file}")

            post_url = "https://matchapro.web.bps.go.id/dirgc/draft-tambah-usaha"

            def send_post(page, url, payload_dict):
                js_code = """
                async (args) => {
                    const [url, body] = args;
                    const params = new URLSearchParams(body);
                    const resp = await fetch(url, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                            'X-Requested-With': 'XMLHttpRequest'
                        },
                        body: params.toString(),
                    });
                    const text = await resp.text();
                    return { status: resp.status, body: text };
                }
                """
                return page.evaluate(js_code, [url, payload_dict])

            def confirm_submit(page, post_url, url_gc, payload, index, nama_usaha_raw, max_sim):
                nonlocal _token
                payload["confirmSubmit"] = "true"
                resp2 = send_post(page, post_url, payload)
                if resp2['status'] == 200:
                    result2 = json.loads(resp2['body'])
                    print(f"Row {index+1}: CONFIRM SUKSES - {nama_usaha_raw} (max similarity {max_sim:.1f}%)")
                    return True
                return False

            start_row = 0
            if os.path.exists(RESUME_FILE):
                with open(RESUME_FILE, 'r') as f:
                    start_row = int(f.read().strip())
                print(f"Resuming from row {start_row + 1}")

            for index, row in df.iterrows():
                if index < start_row: continue

                # --- VALIDASI & MAPPING ID WILAYAH ---
                ids = find_ids(master_wilayah, row['kabupaten'], row['kecamatan'], row['desa'])
                
                if not ids["desa_id"]:
                    print(f"Row {index+1}: ERROR - Wilayah ({row['kabupaten']}-{row['kecamatan']}-{row['desa']}) tidak ditemukan di JSON. SKIP.")
                    continue

                nama_usaha_raw = clean_text(str(row['name']))
                alamat_raw = clean_text(str(row['address']))

                payload = {
                    "_token": _token,
                    "id_table": "",
                    "nama_usaha": base64.b64encode(nama_usaha_raw.encode('utf-8')).decode('utf-8'),
                    "alamat": base64.b64encode(alamat_raw.encode('utf-8')).decode('utf-8'),
                    "provinsi": "134", # ID Internal Gorontalo
                    "kabupaten": ids["kab_id"],
                    "kecamatan": ids["kec_id"],
                    "desa": ids["desa_id"],
                    "latitude": str(row['lat']),
                    "longitude": str(row['lon']),
                    "confirmSubmit": "false",
                    "totalSimilar": "0"
                }

                row_done = False
                for row_attempt in range(3):
                    try:
                        resp = send_post(page, post_url, payload)
                        result = json.loads(resp['body'])
                        status = result.get('status', '')

                        if status == 'success':
                            print(f"Row {index+1}: SUKSES - {nama_usaha_raw}")
                            row_done = True
                            break
                        elif status == 'warning':
                            similar_data = result.get('similarData', [])
                            desa_input = str(row.get('nmdesa_gc', '')).strip().upper()
                            max_sim = 0
                            max_sim_same_desa = 0
                            
                            for item in similar_data:
                                sim = similarity(nama_usaha_raw, item.get('nama', ''))
                                item_desa = str(item.get('nmdesa', '')).strip().upper()
                                same_desa = item_desa != '' and item_desa == desa_input
                                
                                if sim > max_sim: max_sim = sim
                                if sim > max_sim_same_desa and same_desa:
                                    max_sim_same_desa = sim

                            if max_sim_same_desa > MAX_SIMILARITY:
                                print(f"Row {index+1}: SKIP - USAHA SUDAH ADA (Similarity {max_sim_same_desa:.1f}%)")
                                row_done = True
                                break
                            else:
                                payload["totalSimilar"] = str(len(similar_data))
                                row_done = confirm_submit(page, post_url, url_gc, payload, index, nama_usaha_raw, max_sim)
                                break
                        else:
                            print(f"Row {index+1}: {status} - {result.get('message', '')}")
                            row_done = True
                            break
                    except Exception as e:
                        print(f"Row {index+1}: Percobaan {row_attempt+1} gagal - {e}")
                        time.sleep(2)

                with open(RESUME_FILE, 'w') as f:
                    f.write(str(index + 1))
                time.sleep(1.5)

            if os.path.exists(RESUME_FILE): os.remove(RESUME_FILE)
            print("\nSelesai!")

        finally:
            browser.close()

if __name__ == "__main__":
    main()