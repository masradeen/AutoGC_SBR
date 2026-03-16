import requests
import pandas as pd
import time
import sys
import json
import re
import getpass
from login import login_with_sso, user_agents

version = "1.2.4"

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
    # Mencoba mencocokkan 'let gcSubmitToken' dengan kutip satu atau dua dan spasi fleksibel
    match = re.search(r"let\s+gcSubmitToken\s*=\s*(['\"])([^'\"]+)\1", content)
    if match:
        gc_token = match.group(2)
    else:
        # Analisa konten error
        if "Akses lewat matchapro mobile aja" in content or "Not Authorized" in content:
            print("\n" + "="*50)
            print("❌ ERROR FATAL: AKES DITOLAK SERVER")
            print("Penyebab: Laptop ini terdeteksi sebagai Desktop, bukan Mobile.")
            print("SOLUSI: Pastikan file 'login.py' di laptop ini SUDAH DIPERBARUI")
            print("        agar sama persis dengan yang ada di laptop utama.")
            print("="*50 + "\n")
        
        # Simpan konten halaman untuk debugging jika token tidak ditemukan
        try:
            with open("debug_page_content.html", "w", encoding="utf-8") as f:
                f.write(content)
            print("Gagal menemukan gc_token. Konten halaman telah disimpan ke debug_page_content.html")
        except Exception as e:
            print(f"Gagal menyimpan debug page: {e}")
            
        raise Exception("Token tidak ditemukan (Cek pesan error di atas)")
    
    return _token, gc_token

def main():

    # login
    username = input("Masukkan username: ")
    password = getpass.getpass("Masukkan Password SSO: ")
    otp_code = input("Masukkan OTP (kosongkan jika tidak ada): ").strip() or None

    # Lakukan login dan dapatkan objek halaman
    page, browser = login_with_sso(username, password, otp_code)

    if page:
        try:
            # DEBUG: Cek identitas browser
            ua = page.evaluate("navigator.userAgent")
            print(f"\n[INFO] Browser User Agent: {ua}")
            if "Android" not in ua and "Mobile" not in ua:
                print("⚠️  WARNING: Script tidak berjalan dalam mode Mobile!")
                print("    Kemungkinan file 'login.py' belum diupdate di laptop ini.")
            else:
                print("[INFO] Mode Mobile aktif. Kamuflase berhasil. Lanjutkan.....\n")

            # Navigasi ke /dirgc
            url_gc = "https://matchapro.web.bps.go.id/dirgc"
            page.goto(url_gc)
            page.wait_for_load_state('networkidle')

            # Ekstrak tokens
            _token, gc_token = extract_tokens(page)
            print(f"Ekstrak _token: {_token}")
            print(f"gc_token: {gc_token}")

            # Dapatkan cookies
            cookies = page.context.cookies()
            session_cookies = {cookie['name']: cookie['value'] for cookie in cookies}

            url = "https://matchapro.web.bps.go.id/dirgc/konfirmasi-user"
            

            # set header kamuflase
            headers = {
                "host": "matchapro.web.bps.go.id",
                "connection": "keep-alive",
                "sec-ch-ua": "\"Android WebView\";v=\"143\", \"Chromium\";v=\"143\", \"Not A(Brand\";v=\"24\"",
                "sec-ch-ua-mobile": "?1",
                "sec-ch-ua-platform": "\"Android\"",
                "upgrade-insecure-requests": "1",
                "user-agent": user_agents,
                "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                "x-requested-with": "com.matchapro.app",
                "sec-fetch-site": "same-origin",
                "sec-fetch-mode": "navigate",
                "sec-fetch-user": "?1",
                "sec-fetch-dest": "document",
                "referer": "https://matchapro.web.bps.go.id/",
                "accept-encoding": "gzip, deflate, br, zstd",
                "accept-language": "en-GB,en-US;q=0.9,en;q=0.8",
            }

            # --- BAGIAN PENARIKAN DATA (MODIFIKASI SAYA) ---
            print("\n[INFO] Mulai menarik data usaha...")
            
            api_url = "https://matchapro.web.bps.go.id/direktori_usaha/hasil-tambah-usaha-viewer"
            
            # Update headers dengan CSRF Token yang baru didapat
            headers["X-CSRF-TOKEN"] = _token
            headers["Accept"] = "application/json, text/javascript, */*; q=0.01"
            headers.pop("upgrade-insecure-requests", None) # Hapus jika ada karena ini request JSON

            all_data = []
            current_page = 1
            
            while True:
                payload = {
                    "page": str(current_page),
                    "per_page": "15"
                }
                
                print(f"Sedang mengambil halaman {current_page}...", end="\r")
                
                # Gunakan requests dengan cookies dari Playwright
                response = requests.post(
                    api_url, 
                    headers=headers, 
                    data=payload, 
                    cookies=session_cookies,
                    timeout=15
                )

                if response.status_code == 200:
                    json_res = response.json()
                    data_page = json_res.get("data", [])
                    
                    if not data_page:
                        break
                        
                    all_data.extend(data_page)
                    
                    # Cek apakah ini halaman terakhir
                    if current_page >= json_res.get("last_page", 1):
                        break
                        
                    current_page += 1
                    time.sleep(0.5) # Jeda sopan
                else:
                    print(f"\n[!] Berhenti di halaman {current_page}. Status: {response.status_code}")
                    print("Pesan Error:", response.text)
                    break

            # Simpan hasil ke file JSON
            if all_data:
                file_name = "data_direktori_usaha.json"
                with open(file_name, "w", encoding="utf-8") as f:
                    json.dump(all_data, f, indent=4, ensure_ascii=False)
                print(f"\n[SUKSES] Berhasil mengambil {len(all_data)} data.")
                print(f"[INFO] Data disimpan di: {file_name}")
            else:
                print("\n[!] Tidak ada data yang berhasil ditarik.")
            
            # --- AKHIR BAGIAN MODIFIKASI ---
            input("Browser aktif. Tekan ENTER jika ingin menutup...")

        except Exception as e:
            print(f"Error: {e}")
        finally:
            # Close browser
            browser.close()
    else:
        print("Login gagal, tidak dapat melanjutkan permintaan.")

if __name__ == "__main__":
    main()


