import json
import time
import getpass
import os
from login import login_with_sso

def fetch_api(page, url, body_str):
    js_fetch = """
    async ([url, body]) => {
        const resp = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'X-Requested-With': 'XMLHttpRequest'
            },
            body: body
        });
        return await resp.json();
    }
    """
    try:
        return page.evaluate(js_fetch, [url, body_str])
    except Exception as e:
        return {"error": str(e)}

def main():
    username = input("Username SSO: ")
    password = getpass.getpass("Password SSO: ")
    
    page, browser = login_with_sso(username, password)
    
    if page:
        try:
            print("Membuka halaman Matchapro...")
            page.goto("https://matchapro.web.bps.go.id/dirgc", wait_until="networkidle")
            
            _token = page.locator('meta[name="csrf-token"]').get_attribute('content')
            prov_id = "134" # ID Gorontalo
            
            print(f"Mengambil daftar Kabupaten via endpoint khusus...")
            # Menggunakan endpoint yang Anda temukan
            endpoint_kab = "https://matchapro.web.bps.go.id/wil-kabupaten-kota-user-gc"
            list_kab = fetch_api(page, endpoint_kab, f"provinsi={prov_id}&_token={_token}")

            if not isinstance(list_kab, list):
                print(f"Gagal mengambil kabupaten. Respon server: {list_kab}")
                return

            print(f"Berhasil! Ditemukan {len(list_kab)} kabupaten di Gorontalo.")
            
            master_wilayah = []
            for kab in list_kab:
                kab_id = kab.get('id')
                kab_nama = kab.get('nama')
                kab_kode = kab.get('kode')
                
                print(f"\n[Kab] {kab_kode} - {kab_nama}")
                
                # Tarik Kecamatan
                kec_res = fetch_api(page, "https://matchapro.web.bps.go.id/wil-kecamatan", 
                                   f"kabupaten_kota={kab_id}&_token={_token}")
                
                kab_data = {
                    "id": kab_id,
                    "kode": kab_kode,
                    "nama": kab_nama,
                    "kecamatan": []
                }

                if isinstance(kec_res, list):
                    for kec in kec_res:
                        kec_id = kec.get('id')
                        kec_nama = kec.get('nama')
                        kec_kode = kec.get('kode')
                        print(f"  > [Kec] {kec_kode} - {kec_nama}")
                        
                        # Tarik Desa
                        desa_res = fetch_api(page, "https://matchapro.web.bps.go.id/wil-desa", 
                                           f"kecamatan={kec_id}&_token={_token}")
                        
                        kec_data = {
                            "id": kec_id,
                            "kode": kec_kode,
                            "nama": kec_nama,
                            "desa": desa_res if isinstance(desa_res, list) else []
                        }
                        kab_data["kecamatan"].append(kec_data)
                        time.sleep(0.05) # Jeda sangat singkat
                
                master_wilayah.append(kab_data)

            # Simpan ke file JSON
            output_file = "master_wilayah_gorontalo.json"
            with open(output_file, "w") as f:
                json.dump(master_wilayah, f, indent=4)
            
            print(f"\n--- SELESAI ---")
            print(f"Data wilayah telah disimpan di: {os.path.abspath(output_file)}")
            print("Anda sekarang bisa menjalankan script input data utama.")

        except Exception as e:
            print(f"Terjadi kesalahan saat proses: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    main()