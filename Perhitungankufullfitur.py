

import telebot
import gspread
from datetime import datetime, timedelta
from oauth2client.service_account import ServiceAccountCredentials


# === KONFIGURASI TOKEN TELEGRAM DAN GOOGLE SHEET ===
TOKEN = '8048576532:AAEAYO9-1RHEKF-k-NlXoOgAkCJGmocX6lo'
bot = telebot.TeleBot(TOKEN)

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
client = gspread.authorize(creds)
sheet = client.open("Perhitunganku").worksheet("Sheet1")

# === PARSE INPUT PESAN UNTUK TRANSAKSI ===
def parse_message(msg):
    try:
        parts = msg.split('/')
        if len(parts) != 2:
            return None

        deskripsi_dan_nominal = parts[0].strip()
        kategori = parts[1].strip()

        if '+' in deskripsi_dan_nominal:
            deskripsi, nominal = deskripsi_dan_nominal.split('+')
            tipe = 'pemasukan'
        elif '-' in deskripsi_dan_nominal:
            deskripsi, nominal = deskripsi_dan_nominal.split('-')
            tipe = 'pengeluaran'
        else:
            return None

        return {
            'keterangan': deskripsi.strip(),
            'nominal': int(nominal.strip()),
            'kategori': kategori,
            'tipe': tipe
        }

    except Exception:
        return None

# === SIMPAN DATA SAAT PENGGUNA KIRIM PESAN BIASA ===
@bot.message_handler(func=lambda message: not message.text.startswith('/'))
def handle_message(message):
    data = parse_message(message.text)
    if data:
        tanggal = datetime.now().strftime('%d-%m-%Y')
        sheet.append_row([
            tanggal,
            data['nominal'],
            data['keterangan'],
            data['kategori'],
            data['tipe'],
            message.from_user.id
        ])
        bot.reply_to(message, f"✅ {data['tipe'].capitalize()} tercatat!\nKategori: {data['kategori']}\nJumlah: Rp {data['nominal']:,}")
    else:
        bot.reply_to(message, "❌ Format salah.\nGunakan: [keterangan] +/-[jumlah] /[kategori]\nContoh:\nMakan -10000 /makanan")

# === FUNGSI HITUNG TOTAL ===
def hitung_total(user_id, filter_fungsi=None):
    pemasukan = 0
    pengeluaran = 0
    records = sheet.get_all_records()

    for row in records:
        try:
            row_date = datetime.strptime(row['Tanggal'], "%d-%m-%Y")
            row_user = str(row['ID User'])
            if str(user_id) != row_user:
                continue
            if filter_fungsi and not filter_fungsi(row_date):
                continue

            if row['Tipe'].lower() == 'pemasukan':
                pemasukan += int(row['Nominal'])
            elif row['Tipe'].lower() == 'pengeluaran':
                pengeluaran += int(row['Nominal'])
        except:
            continue

    return pemasukan, pengeluaran, pemasukan - pengeluaran

# === /TOTAL ===
@bot.message_handler(commands=['total'])
def handle_total(message):
    pemasukan, pengeluaran, saldo = hitung_total(message.from_user.id)
    response = (
        f"📊 Total Semua Transaksi:\n"
        f"📥 Pemasukan: Rp {pemasukan:,}\n"
        f"📤 Pengeluaran: Rp {pengeluaran:,}\n"
        f"💰 Saldo: Rp {saldo:,}"
    )
    bot.reply_to(message, response)

# === /TOTALHARIINI ===
@bot.message_handler(commands=['totalhariini'])
def handle_total_hariini(message):
    today = datetime.now().date()
    pemasukan, pengeluaran, saldo = hitung_total(message.from_user.id, lambda d: d.date() == today)
    response = (
        f"📅 Total Hari Ini ({today.strftime('%d-%m-%Y')}):\n"
        f"📥 Pemasukan: Rp {pemasukan:,}\n"
        f"📤 Pengeluaran: Rp {pengeluaran:,}\n"
        f"💰 Saldo: Rp {saldo:,}"
    )
    bot.reply_to(message, response)

# === /TOTALPERTANGGAL DD-MM-YYYY ===
@bot.message_handler(commands=['totalpertanggal'])
def handle_total_pertanggal(message):
    try:
        parts = message.text.split()
        if len(parts) != 2:
            raise ValueError("Format salah")
        tanggal_input = datetime.strptime(parts[1], '%d-%m-%Y')
        pemasukan, pengeluaran, saldo = hitung_total(message.from_user.id, lambda d: d.date() == tanggal_input.date())
        response = (
            f"📅 Total Tanggal {tanggal_input.strftime('%d-%m-%Y')}:\n"
            f"📥 Pemasukan: Rp {pemasukan:,}\n"
            f"📤 Pengeluaran: Rp {pengeluaran:,}\n"
            f"💰 Saldo: Rp {saldo:,}"
        )
        bot.reply_to(message, response)
    except:
        bot.reply_to(message, "❌ Format salah.\nGunakan: /totalpertanggal dd-mm-yyyy")

# === Fungsi untuk menghitung total berdasarkan filter tanggal ===
def hitung_total(user_id, filter_func):
    pemasukan = 0
    pengeluaran = 0
    records = sheet.get_all_records()
    
    for row in records:
        try:
            row_date_str = str(row.get('Tanggal', '')).strip()
            row_user_id = str(row.get('ID User', '')).strip()
            row_tipe = str(row.get('Tipe', '')).strip().lower()
            row_nominal = int(str(row.get('Nominal', '0')).replace(',', '').strip())

            # Cek apakah data sesuai dengan user dan filter tanggal
            row_date = datetime.strptime(row_date_str, '%d-%m-%Y')
            if row_user_id == str(user_id) and filter_func(row_date):
                if row_tipe == 'pemasukan':
                    pemasukan += row_nominal
                elif row_tipe == 'pengeluaran':
                    pengeluaran += row_nominal

        except Exception as e:
            print(f"❌ Lewati baris karena error: {e} | Data: {row}")

    saldo = pemasukan - pengeluaran
    return pemasukan, pengeluaran, saldo

# === /TOTALMINGGUAN ===
@bot.message_handler(commands=['totalmingguan'])
def handle_total_mingguan(message):
    today = datetime.now()
    
    # Menentukan awal minggu (Senin)
    awal_minggu = today - timedelta(days=today.weekday())
    
    # Menentukan akhir minggu (Minggu)
    akhir_minggu = awal_minggu + timedelta(days=6)  # Minggu ini
    
    # Hitung total pemasukan, pengeluaran, dan saldo untuk minggu ini
    pemasukan, pengeluaran, saldo = hitung_total(
        message.from_user.id,
        lambda d: awal_minggu.date() <= d.date() <= akhir_minggu.date()  # Filter dari Senin sampai Minggu
    )
    
    response = (
        f"📆 Total Minggu Ini ({awal_minggu.strftime('%d-%m-%Y')} - {akhir_minggu.strftime('%d-%m-%Y')}):\n"
        f"📥 Pemasukan: Rp {pemasukan:,}\n"
        f"📤 Pengeluaran: Rp {pengeluaran:,}\n"
        f"💰 Saldo: Rp {saldo:,}"
    )
    
    bot.reply_to(message, response)


# === /REKAPBULANAN MM YYYY ===
@bot.message_handler(commands=['rekapbulanan'])
def handle_rekap_bulanan(message):
    try:
        _, bulan, tahun = message.text.split()
        awal = datetime.strptime(f"01-{bulan}-{tahun}", "%d-%m-%Y")
        akhir = (awal.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)

        pemasukan, pengeluaran, saldo = hitung_total(
            message.from_user.id,
            lambda d: awal.date() <= d.date() <= akhir.date()
        )

        response = (
            f"📅 Rekap Bulan {awal.strftime('%B %Y')}:\n"
            f"📥 Pemasukan: Rp {pemasukan:,}\n"
            f"📤 Pengeluaran: Rp {pengeluaran:,}\n"
            f"💰 Saldo: Rp {saldo:,}"
        )
        bot.reply_to(message, response)
    except:
        bot.reply_to(message, "❌ Format salah.\nGunakan: /rekapbulanan mm yyyy")

# === /KATEGORI makanan ===
@bot.message_handler(commands=['kategori'])
def handle_kategori(message):
    try:
        kategori = message.text.split()[1].lower()
        pemasukan = 0
        pengeluaran = 0
        user_id = str(message.from_user.id)

        records = sheet.get_all_records()
        for row in records:
            if str(row['ID User']) != user_id:
                continue
            if str(row['Kategori']).lower() != kategori:
                continue

            if row['Tipe'].lower() == 'pemasukan':
                pemasukan += int(row['Nominal'])
            elif row['Tipe'].lower() == 'pengeluaran':
                pengeluaran += int(row['Nominal'])

        saldo = pemasukan - pengeluaran
        response = (
            f"🔎 Total Kategori '{kategori}':\n"
            f"📥 Pemasukan: Rp {pemasukan:,}\n"
            f"📤 Pengeluaran: Rp {pengeluaran:,}\n"
            f"💰 Saldo: Rp {saldo:,}"
        )
        bot.reply_to(message, response)
    except:
        bot.reply_to(message, "❌ Format salah.\nGunakan: /kategori [nama_kategori]")

# === JALANKAN BOT ===
print("🤖 Bot berjalan...")
bot.polling(none_stop=True)
