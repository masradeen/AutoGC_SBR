import pandas as pd
import json
import os

def save_to_excel(data, filename):
    """
    Mengubah list of dictionaries menjadi file Excel yang rapi.
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

        with pd.ExcelWriter(filename, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Data Usaha')
            
            worksheet = writer.sheets['Data Usaha']
            # Penyesuaian lebar kolom otomatis
            for i, col in enumerate(df.columns):
                column_data = df[col].astype(str).map(len)
                max_len = max(column_data.max() if not column_data.empty else 0, len(col)) + 2
                # Menggunakan utilitas openpyxl untuk mendapatkan nama kolom (A, B, C, dst)
                from openpyxl.utils import get_column_letter
                worksheet.column_dimensions[get_column_letter(i + 1)].width = min(max_len, 50)

        print(f"✅ Berhasil! File Excel tersimpan di: {filename}")

    except Exception as e:
        print(f"❌ Error saat konversi Excel: {e}")

def load_json_and_convert(target_date):
    """
    Membaca JSON berdasarkan tanggal dan mengonversinya ke Excel.
    """
    # Nama file input dan output berdasarkan tanggal
    json_file = f"data_usaha_{target_date}.json"
    excel_file = f"Data_Usaha_SBR_{target_date}.xlsx"

    if not os.path.exists(json_file):
        print(f"❌ Error: File {json_file} tidak ditemukan!")
        return

    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        save_to_excel(data, excel_file)
    except Exception as e:
        print(f"❌ Gagal membaca JSON: {e}")

if __name__ == "__main__":
    import datetime
    print(f"--- Program Konverter JSON ke Excel Dinamis ---")
    
    # Otomatis hari ini jika ingin cepat
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    
    input_date = input(f"Masukkan tanggal penarikan (YYYY-MM-DD) [Default {today}]: ").strip()
    target_date = input_date if input_date else today
    
    load_json_and_convert(target_date)