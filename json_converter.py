import pandas as pd
import json

def save_to_excel(data, filename="data_direktori_usaha_tambahan.xlsx"):
    """
    Mengubah list of dictionaries menjadi file Excel yang rapi
    dengan penyesuaian lebar kolom otomatis.
    """
    try:
        if not data:
            print("[!] Tidak ada data untuk dikonversi.")
            return

        print(f"\n[INFO] Memproses {len(data)} data ke Excel...")
        df = pd.DataFrame(data)

        # Pembersihan Duplikat
        if 'id_table' in df.columns:
            df = df.drop_duplicates(subset=['id_table'])

        # Gunakan ExcelWriter untuk mengatur format (seperti lebar kolom)
        with pd.ExcelWriter(filename, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Data Usaha')
            
            # Mengatur lebar kolom otomatis agar rapi
            worksheet = writer.sheets['Data Usaha']
            for i, col in enumerate(df.columns):
                max_len = max(df[col].astype(str).map(len).max(), len(col)) + 2
                worksheet.column_dimensions[chr(65 + i)].width = min(max_len, 50) # Maks lebar 50

        print(f"✅ Berhasil! File tersimpan di: {filename}")

    except Exception as e:
        print(f"❌ Error saat konversi Excel: {e}")

def load_json_and_convert(json_file, excel_file):
    """
    Fungsi tambahan jika Anda ingin mengonversi ulang dari file JSON yang sudah ada.
    """
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        save_to_excel(data, excel_file)
    except Exception as e:
        print(f"❌ Gagal membaca JSON: {e}")

if __name__ == "__main__":
    # Ganti 'data_direktori_usaha.json' dengan nama file JSON hasil scraping Anda
    nama_file_json = "data_direktori_usaha.json" 
    nama_file_excel = "Hasil_Konversi_Manual.xlsx"
    
    print(f"--- Program Konverter JSON ke Excel ---")
    load_json_and_convert(nama_file_json, nama_file_excel)