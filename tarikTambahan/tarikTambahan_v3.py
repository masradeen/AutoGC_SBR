import requests
import pandas as pd
import time
import json
import re
import getpass
import datetime
import random
from openpyxl.utils import get_column_letter
from login import login_with_sso, user_agents

version = "1.3.9"

def extract_tokens(page):
    page.wait_for_selector('meta[name="csrf-token"]', state='attached', timeout=10000)
    return page.locator('meta[name="csrf-token"]').get_attribute('content')

def save_to_excel(data, filename):
    try:
        df = pd.DataFrame(data)
        if 'id_table' in df.columns: df = df.drop_duplicates(subset=['id_table'])
        with pd.ExcelWriter(filename, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Data Usaha')
            worksheet = writer.sheets['Data Usaha']
            for i, col in enumerate(df.columns):
                max_len = max(df[col].astype(str).map(len).max() if not df[col].empty else 0, len(col)) + 2
                worksheet.column_dimensions[get_column_letter(i + 1)].width = min(max_len, 50)
        print(f"✅ EXCEL BERHASIL: {filename}")
    except Exception as e: print(f"❌ Excel Error: {e}")

def main():
    print(f"--- MatchaPro Deep Scanner v{version} ---")
    username = input("Username: ")
    password = getpass.getpass("Password SSO: ")
    otp_code = input("OTP: ").strip() or None

    page, browser = login_with_sso(username, password, otp_code)
    if not page: return

    try:
        print("\n[1/3] Sinkronisasi Session...")
        page.goto("https://matchapro.web.bps.go.id/dirgc")
        page.wait_for_load_state('networkidle')
        _token = extract_tokens(page)
        session_cookies = {c['name']: c['value'] for c in page.context.cookies()}

        headers = {
            "Host": "matchapro.web.bps.go.id",
            "Accept": "*/*",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "X-Csrf-Token": _token,
            "X-Requested-With": "XMLHttpRequest",
            "Origin": "https://matchapro.web.bps.go.id",
            "Referer": "https://matchapro.web.bps.go.id/dirgc",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
        }

        print("\n" + "="*45)
        end_date = input("Tarik sampai tanggal berapa? (YYYY-MM-DD): ").strip()
        print("="*45)

        all_data = []
        current_page = 1
        empty_count = 0 # Untuk toleransi halaman kosong

        print(f"\n[2/3] Memulai Deep Scan...")

        while True:
            payload = {
                "_token": _token,
                "page": str(current_page),
                "per_page": "15",
                "search_nama": "",
                "search_alamat": "",
                "search_status": "ALL",
                "ptotal": "29864" # Sesuai angka yang Anda lihat di web
            }

            print(f"-> Mencoba Halaman {current_page}... (Total Didapat: {len(all_data)})", end="\r")
            
            res = requests.post(
                "https://matchapro.web.bps.go.id/direktori_usaha/hasil-tambah-usaha-viewer",
                headers=headers, data=payload, cookies=session_cookies, timeout=30
            )
            
            if res.status_code != 200: break
            
            data_page = res.json().get("data", [])
            
            if not data_page:
                empty_count += 1
                if empty_count > 3: # Jika 3 halaman berturut-turut kosong, baru stop
                    break
                current_page += 1
                continue
            
            empty_count = 0 # Reset jika ada data
            
            # Filter Tanggal
            today = datetime.datetime.now().strftime("%Y-%m-%d")
            for d in data_page:
                dt = d.get("created_at", "")
                if dt and end_date <= dt[:10] <= today:
                    all_data.append(d)

            if current_page >= res.json().get("last_page", 1):
                break
                
            current_page += 1
            time.sleep(1)

        if all_data:
            save_to_excel(all_data, f"HASIL_DEEP_SCAN_{end_date}.xlsx")
        else:
            print(f"\n❌ Data tetap tidak ditemukan. Kemungkinan besar API membatasi akses hanya ke data milik User ID Anda.")

    finally:
        browser.close()

if __name__ == "__main__":
    main()