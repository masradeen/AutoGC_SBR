import requests
import pandas as pd
import time
import sys
import json
import re
import getpass
import datetime
import random
from login import login_with_sso, user_agents

version = "1.2.5"

def extract_tokens(page):
    # Tunggu hingga tag meta token CSRF terpasang
    page.wait_for_selector('meta[name="csrf-token"]', state='attached', timeout=10000)

    # Ekstrak _token dari halaman (token CSRF dari tag meta)
    token_element = page.locator('meta[name="csrf-token"]')
    if token_element.count() > 0:
        _token = token_element.get_attribute('content')
    else:
        raise Exception("Gagal mengekstrak _token - tag meta tidak ditemukan")

    # Ekstrak gc_token dari konten halaman
    content = page.content()
    match = re.search(r"let\s+gcSubmitToken\s*=\s*(['\"])([^'\"]+)\1", content)
    if match:
        gc_token = match.group(2)
    else:
        if "Akses lewat matchapro mobile aja" in content or "Not Authorized" in content:
            print("\n" + "="*50)
            print("❌ ERROR FATAL: AKSES DITOLAK SERVER")
            print("Penyebab: Browser terdeteksi sebagai Desktop, bukan Mobile.")
            print("="*50 + "\n")
        
        try:
            with open("debug_page_content.html", "w", encoding="utf-8") as f:
                f.write(content)
            print("Gagal menemukan gc_token. Detail disimpan ke debug_page_content.html")
        except Exception as e:
            print(f"Gagal menyimpan debug page: {e}")
            
        raise Exception("Token tidak ditemukan.")
    
    return _token, gc_token

def main():
    # Login Info
    print(f"--- MatchaPro Data Scraper v{version} ---")
    username = input("Masukkan username: ")
    password = getpass.getpass("Masukkan Password SSO: ")
    otp_code = input("Masukkan OTP (kosongkan jika tidak ada): ").strip() or None

    # Lakukan login dan dapatkan objek halaman
    page, browser = login_with_sso(username, password, otp_code)

    if page:
        try:
            ua = page.evaluate("navigator.userAgent")
            print(f"\n[INFO] Browser User Agent: {ua}")
            
            # Navigasi ke direktori GC
            url_gc = "https://matchapro.web.bps.go.id/dirgc"
            page.goto(url_gc)
            page.wait_for_load_state('networkidle')

            # Ekstrak tokens
            _token, gc_token = extract_tokens(page)
            print(f"[_] Token CSRF: {_token[:10]}...")
            print(f"[_] Token GC: {gc_token[:10]}...")

            # Dapatkan cookies dari Playwright untuk Requests
            cookies = page.context.cookies()
            session_cookies = {cookie['name']: cookie['value'] for cookie in cookies}

            # Header Kamuflase
            headers = {
                "Host": "matchapro.web.bps.go.id",
                "Sec-Ch-Ua-Mobile": "?1",
                "User-Agent": user_agents,
                "X-Csrf-Token": _token,
                "X-Requested-With": "com.matchapro.app",
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "Referer": "https://matchapro.web.bps.go.id/direktori_usaha/hasil-tambah-usaha",
            }

            # --- INPUT TANGGAL TARGET ---
            print("\n" + "="*35)
            print("  PENARIKAN DATA TANGGAL SPESIFIK  ")
            print("="*35)
            
            today = datetime.datetime.now().strftime("%Y-%m-%d")
            input_date = input(f"Masukkan tanggal (YYYY-MM-DD) [Default {today}]: ").strip()
            target_date = input_date if input_date else today
            
            all_data = []
            current_page = 1
            max_retries = 3 # Jumlah percobaan jika koneksi terputus

            print(f"\n[INFO] Mencari data khusus tanggal: {target_date}")

            while True:
                payload = {
                    "page": str(current_page),
                    "per_page": "15"
                }
                
                print(f"-> Memeriksa halaman {current_page}...", end="\r")
                
                # --- MEKANISME RETRY UNTUK ANTISIPASI CONNECTION ABORTED ---
                response = None
                for attempt in range(max_retries):
                    try:
                        response = requests.post(
                            "https://matchapro.web.bps.go.id/direktori_usaha/hasil-tambah-usaha-viewer", 
                            headers=headers, 
                            data=payload, 
                            cookies=session_cookies,
                            timeout=20
                        )
                        break # Berhasil, keluar dari loop retry
                    except (requests.exceptions.ConnectionError, requests.exceptions.ChunkedEncodingError) as e:
                        if attempt < max_retries - 1:
                            print(f"\n[!] Koneksi terputus, mencoba lagi ({attempt+1}/{max_retries})...")
                            time.sleep(5)
                        else:
                            print("\n[!] Gagal menghubungi server setelah beberapa kali percobaan.")
                            raise e

                if response and response.status_code == 200:
                    json_res = response.json()
                    data_page = json_res.get("data", [])
                    
                    if not data_page:
                        break
                        
                    # Filter data yang cocok dengan tanggal target
                    relevant_data = [d for d in data_page if d.get("created_at", "").startswith(target_date)]
                    
                    if relevant_data:
                        all_data.extend(relevant_data)
                        print(f"\n[OK] Halaman {current_page}: Menambahkan {len(relevant_data)} data.")

                    # LOGIKA STOP: Jika data terakhir di halaman ini sudah lebih tua dari target
                    last_item_date = data_page[-1].get("created_at", "")
                    if last_item_date and last_item_date < target_date:
                        print(f"\n[FINISH] Mencapai data tanggal {last_item_date[:10]}. Pencarian dihentikan.")
                        break
                    
                    if current_page >= json_res.get("last_page", 1):
                        break
                        
                    current_page += 1
                    # Jeda acak agar tidak terdeteksi bot (2-4 detik)
                    time.sleep(random.uniform(2, 4)) 
                else:
                    status = response.status_code if response else "No Response"
                    print(f"\n[!] Berhenti di halaman {current_page}. Status: {status}")
                    break

            # Simpan hasil
            if all_data:
                file_name = f"data_usaha_{target_date}.json"
                with open(file_name, "w", encoding="utf-8") as f:
                    json.dump(all_data, f, indent=4, ensure_ascii=False)
                print(f"\n" + "-"*35)
                print(f"✅ SUKSES: {len(all_data)} data tersimpan.")
                print(f"📂 Lokasi: {file_name}")
                print("-"*35)
            else:
                print("\n[!] Selesai. Tidak ada data ditemukan untuk tanggal tersebut.")
            
            input("\nTekan ENTER untuk menutup browser...")

        except Exception as e:
            print(f"\n[ERROR] Terjadi kesalahan: {e}")
        finally:
            browser.close()
            print("[INFO] Browser ditutup.")
    else:
        print("Login gagal.")

if __name__ == "__main__":
    main()