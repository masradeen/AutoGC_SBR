import requests
import json
import time

url = "https://matchapro.web.bps.go.id/direktori_usaha/hasil-tambah-usaha-viewer"

# Header ini meniru WebView Android
headers = {
    "Host": "matchapro.web.bps.go.id",
    "Connection": "keep-alive",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "X-Requested-With": "XMLHttpRequest",
    "User-Agent": "Mozilla/5.0 (Linux; Android 12; Pixel 6 Build/SD1A.210817.036; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/121.0.6167.178 Mobile Safari/537.36",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Origin": "https://matchapro.web.bps.go.id",
    "Referer": "https://matchapro.web.bps.go.id/direktori_usaha/hasil-tambah-usaha-viewer",
    "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
}

# --- PENTING ---
# Karena ini sistem CSRF, Anda TETAP butuh Cookie & Token awal.
# Jika Anda bisa membuka aplikasi di HP, coba "Share" atau gunakan 
# aplikasi 'HttpCanary' atau 'PCAP Remote' di Android untuk melihat 
# Header yang dikirim oleh HP Anda.
# ----------------

def scrape_with_android_identity():
    # Gunakan Session agar Cookie dikelola otomatis
    session = requests.Session()
    
    # Masukkan Cookie manual hasil 'intip' dari HP jika ada
    # session.cookies.set("laravel_session", "ISI_DARI_HP")
    # headers["X-CSRF-TOKEN"] = "ISI_DARI_HP"

    all_data = []
    
    try:
        # Mencoba ambil halaman 1
        payload = {"page": "1", "per_page": "15"}
        print("Mencoba mengakses dengan identitas Android...")
        
        response = session.post(url, headers=headers, data=payload)
        
        if response.status_code == 200:
            json_response = response.json()
            all_data.extend(json_response.get("data", []))
            last_page = json_response.get("last_page", 1)
            
            print(f"Sukses! Menemukan {last_page} halaman.")
            
            for p in range(2, last_page + 1):
                print(f"Mengambil halaman {p}...")
                p_payload = {"page": str(p), "per_page": "15"}
                p_res = session.post(url, headers=headers, data=p_payload)
                if p_res.status_code == 200:
                    all_data.extend(p_res.json().get("data", []))
                time.sleep(1)
        else:
            print(f"Gagal. Status: {response.status_code}")
            print("Pesan Server:", response.text)

    except Exception as e:
        print(f"Error: {e}")

    if all_data:
        with open('data_bps_android.json', 'w', encoding='utf-8') as f:
            json.dump(all_data, f, indent=4, ensure_ascii=False)
        print(f"Berhasil menyimpan {len(all_data)} data.")

if __name__ == "__main__":
    scrape_with_android_identity()