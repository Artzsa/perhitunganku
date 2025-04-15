import telebot
import gspread
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
from oauth2client.service_account import ServiceAccountCredentials
import io

# === KONFIGURASI TOKEN TELEGRAM DAN GOOGLE SHEET ===
TOKEN = '8048576532:AAEAYO9-1RHEKF-k-NlXoOgAkCJGmocX6lo'  # Ganti dengan token bot Telegram Anda
bot = telebot.TeleBot(TOKEN)

# Autentikasi Google Sheets
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
client = gspread.authorize(creds)
sheet = client.open("Perhitunganku").worksheet("Sheet1")  # Sheet1 untuk transaksi
sheet_budget = client.open("Perhitunganku").worksheet("Sheet2")  # Sheet2 untuk anggaran

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

# === FUNGSI UNTUK MENGAMBIL ANGGARAN DARI SHEET2 ===
def get_budget_for_category(user_id, kategori):
    try:
        records = sheet_budget.get_all_records()
        for row in records:
            if str(row['ID User']) == str(user_id) and row['Kategori'].lower() == kategori.lower():
                return int(row['Budget'])
    except:
        return None
    return None

# === Set Anggaran
@bot.message_handler(commands=['set_anggaran'])
def set_anggaran(message):
    try:
        # Format: /set_anggaran [kategori] [jumlah]
        command = message.text.split()
        if len(command) != 3:
            bot.reply_to(message, "❌ Format salah. Gunakan: /set_anggaran [kategori] [jumlah]")
            return
        
        kategori = command[1]
        jumlah = int(command[2])

        # Ambil ID User dari pesan
        user_id = message.from_user.id

        # Menambahkan anggaran ke Sheet2
        sheet_budget.append_row([kategori, jumlah, user_id])

        bot.reply_to(message, f"✅ Anggaran untuk kategori '{kategori}' telah ditambahkan: Rp {jumlah:,}")
    except Exception as e:
        bot.reply_to(message, f"❌ Terjadi kesalahan: {str(e)}")

# === Cek Anggaran 
@bot.message_handler(commands=['cek_anggaran'])
def cek_anggaran(message):
    try:
        # Format: /cek_anggaran [kategori]
        command = message.text.split()
        if len(command) != 2:
            bot.reply_to(message, "❌ Format salah. Gunakan: /cek_anggaran [kategori]")
            return
        
        kategori = command[1]
        user_id = message.from_user.id
        
        # Mencari anggaran yang sesuai di Sheet2
        anggaran_data = sheet_budget.get_all_records()
        total_anggaran = 0  # Variabel untuk menjumlahkan anggaran
        total_pengeluaran = 0  # Variabel untuk menjumlahkan pengeluaran
        anggaran_found = False
        
        for row in anggaran_data:
            if row['ID User'] == user_id and row['Kategori'] == kategori:
                anggaran_found = True
                total_anggaran += row['Budget']  # Menambahkan anggaran jika ditemukan kategori yang sama
        
        # Mencari pengeluaran berdasarkan kategori
        pengeluaran_data = sheet.get_all_records()  # Sheet transaksi pengeluaran
        for row in pengeluaran_data:
            if row['ID User'] == user_id and row['Kategori'] == kategori and row['Tipe'].lower() == 'pengeluaran':
                total_pengeluaran += int(row['Nominal'])  # Menambahkan pengeluaran jika kategori sama
        
        if anggaran_found:
            saldo_anggaran = total_anggaran - total_pengeluaran
            bot.reply_to(message, f"✅ Anggaran yang tersisa untuk kategori '{kategori}':\nRp {saldo_anggaran:,} (Anggaran: Rp {total_anggaran:,} - Pengeluaran: Rp {total_pengeluaran:,})")
        else:
            bot.reply_to(message, f"❌ Anggaran untuk kategori '{kategori}' tidak ditemukan.")
    
    except Exception as e:
        bot.reply_to(message, f"❌ Terjadi kesalahan: {str(e)}")


# === FUNGSI UNTUK MENGHITUNG PENGELUARAN BULANAN PER KATEGORI ===
def get_monthly_spending_by_category(user_id, kategori):
    today = datetime.now()
    awal_bulan = today.replace(day=1)
    akhir_bulan = (awal_bulan.replace(month=today.month % 12 + 1, day=1) - timedelta(days=1))

    records = sheet.get_all_records()
    total = 0
    for row in records:
        try:
            row_date = datetime.strptime(row['Tanggal'], "%d-%m-%Y")
            if (str(row['ID User']) == str(user_id) and
                row['Tipe'].lower() == 'pengeluaran' and
                row['Kategori'].lower() == kategori.lower() and
                awal_bulan.date() <= row_date.date() <= akhir_bulan.date()):
                total += int(row['Nominal'])
        except:
            continue
    return total

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

        response = f"✅ {data['tipe'].capitalize()} tercatat!\nKategori: {data['kategori']}\nJumlah: Rp {data['nominal']:,}"

        # Cek anggaran jika pengeluaran
        if data['tipe'] == 'pengeluaran':
            budget = get_budget_for_category(message.from_user.id, data['kategori'])
            if budget is not None:
                total_spent = get_monthly_spending_by_category(message.from_user.id, data['kategori'])
                if total_spent > budget:
                    response += f"\n⚠️ Pengeluaran di kategori *{data['kategori']}* telah melebihi anggaran!\n💸 Total: Rp {total_spent:,} / Rp {budget:,}"

        bot.reply_to(message, response, parse_mode='Markdown')
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

# === FUNGSI UNTUK MEMBUAT GRAFIK ===
def create_graph(pemasukan, pengeluaran, period):
    labels = ['Pemasukan', 'Pengeluaran']
    values = [pemasukan, pengeluaran]

    # Membuat grafik
    fig, ax = plt.subplots()
    ax.bar(labels, values, color=['green', 'red'])

    # Menambahkan judul dan label
    ax.set_title(f"Ringkasan {period}")
    ax.set_ylabel("Jumlah (Rp)")
    ax.set_xlabel("Kategori")

    # Menyimpan grafik dalam format gambar PNG
    img_stream = io.BytesIO()
    plt.savefig(img_stream, format='png')
    img_stream.seek(0)  # Kembali ke awal stream gambar
    return img_stream

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

# === /LAPORANHARI ===
@bot.message_handler(commands=['laporanhari'])
def handle_laporan_hari(message):
    today = datetime.now().date()

    pemasukan, pengeluaran, saldo = hitung_total(
        message.from_user.id,
        lambda d: d.date() == today
    )

    img_stream = create_graph(pemasukan, pengeluaran, f"Hari {today.strftime('%d-%m-%Y')}")
    bot.send_photo(message.chat.id, img_stream, caption=f"📅 Laporan Hari Ini ({today.strftime('%d-%m-%Y')}):\n📥 Pemasukan: Rp {pemasukan:,}\n📤 Pengeluaran: Rp {pengeluaran:,}\n💰 Saldo: Rp {saldo:,}")

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

# === /LAPORANHARI ===
@bot.message_handler(commands=['laporanhari'])
def handle_laporan_hari(message):
    today = datetime.now().date()

    pemasukan, pengeluaran, saldo = hitung_total(
        message.from_user.id,
        lambda d: d.date() == today
    )

    img_stream = create_graph(pemasukan, pengeluaran, f"Hari {today.strftime('%d-%m-%Y')}")
    bot.send_photo(message.chat.id, img_stream, caption=f"📅 Laporan Hari Ini ({today.strftime('%d-%m-%Y')}):\n📥 Pemasukan: Rp {pemasukan:,}\n📤 Pengeluaran: Rp {pengeluaran:,}\n💰 Saldo: Rp {saldo:,}")

# === /LAPORANMINGGU ===
@bot.message_handler(commands=['laporanminggu'])
def handle_laporan_minggu(message):
    today = datetime.now()
    awal_minggu = today - timedelta(days=today.weekday())
    akhir_minggu = awal_minggu + timedelta(days=6)

    pemasukan, pengeluaran, saldo = hitung_total(
        message.from_user.id,
        lambda d: awal_minggu.date() <= d.date() <= akhir_minggu.date()
    )

    img_stream = create_graph(pemasukan, pengeluaran, f"Minggu ({awal_minggu.strftime('%d-%m-%Y')} - {akhir_minggu.strftime('%d-%m-%Y')})")
    bot.send_photo(message.chat.id, img_stream, caption=f"📅 Laporan Mingguan ({awal_minggu.strftime('%d-%m-%Y')} - {akhir_minggu.strftime('%d-%m-%Y')}):\n📥 Pemasukan: Rp {pemasukan:,}\n📤 Pengeluaran: Rp {pengeluaran:,}\n💰 Saldo: Rp {saldo:,}")

# === /LAPORANBULANAN ===
@bot.message_handler(commands=['laporanbulanan'])
def handle_laporan_bulanan(message):
    today = datetime.now()
    awal_bulan = today.replace(day=1)
    akhir_bulan = (awal_bulan.replace(month=today.month % 12 + 1, day=1) - timedelta(days=1))

    pemasukan, pengeluaran, saldo = hitung_total(
        message.from_user.id,
        lambda d: awal_bulan.date() <= d.date() <= akhir_bulan.date()
    )

    img_stream = create_graph(pemasukan, pengeluaran, f"Bulan ({awal_bulan.strftime('%B %Y')})")
    bot.send_photo(message.chat.id, img_stream, caption=f"📅 Laporan Bulanan ({awal_bulan.strftime('%B %Y')}):\n📥 Pemasukan: Rp {pemasukan:,}\n📤 Pengeluaran: Rp {pengeluaran:,}\n💰 Saldo: Rp {saldo:,}")

# === /REKAPBULANAN MM YYYY DENGAN GRAFIK ===
@bot.message_handler(commands=['rekapbulanan'])
def handle_rekap_bulanan(message):
    try:
        _, bulan, tahun = message.text.split()
        
        # Validasi format bulan dan tahun
        if int(bulan) < 1 or int(bulan) > 12 or int(tahun) < 2000:
            raise ValueError("Bulan atau Tahun tidak valid")
        
        # Menentukan tanggal awal dan akhir bulan yang dipilih
        awal = datetime.strptime(f"01-{bulan}-{tahun}", "%d-%m-%Y")
        akhir = (awal.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)

        # Hitung total pemasukan, pengeluaran, dan saldo untuk bulan yang dipilih
        pemasukan, pengeluaran, saldo = hitung_total(
            message.from_user.id,
            lambda d: awal.date() <= d.date() <= akhir.date()
        )

        # Menghasilkan Grafik
        labels = ['Pemasukan', 'Pengeluaran']
        values = [pemasukan, pengeluaran]
        
        # Membuat grafik batang
        fig, ax = plt.subplots()
        ax.bar(labels, values, color=['green', 'red'])
        ax.set_title(f"Rekap Transaksi Bulan {awal.strftime('%B %Y')}")
        ax.set_ylabel("Jumlah (Rp)")

        # Simpan grafik sebagai gambar dalam format byte
        image_stream = io.BytesIO()
        fig.savefig(image_stream, format='png')
        image_stream.seek(0)

        # Kirim gambar grafik ke Telegram
        bot.send_photo(message.chat.id, image_stream)

        # Kirim informasi rekap
        response = (
            f"📅 Rekap Bulan {awal.strftime('%B %Y')}:\n"
            f"📥 Pemasukan: Rp {pemasukan:,}\n"
            f"📤 Pengeluaran: Rp {pengeluaran:,}\n"
            f"💰 Saldo: Rp {saldo:,}"
        )
        bot.reply_to(message, response)

    except Exception as e:
        bot.reply_to(message, f"❌ Format salah atau terjadi kesalahan: {e}\nGunakan: /rekapbulanan mm yyyy\nContoh: /rekapbulanan 01 2025")
# === 
@bot.message_handler(commands=['kategori'])
def handle_kategori(message):
    # Ambil kategori yang diminta setelah '/kategori'
    kategori = message.text.split()[1] if len(message.text.split()) > 1 else None
    if not kategori:
        bot.reply_to(message, "❌ Format salah. Gunakan format:\n/kategori [kategori]\nContoh: /kategori makanan")
        return

    user_id = str(message.from_user.id)
    pemasukan = 0
    pengeluaran = 0

    try:
        records = sheet.get_all_records()

        for row in records:
            try:
                row_date_str = str(row.get('Tanggal', '')).strip()
                row_user_id = str(row.get('ID User', '')).strip()
                row_tipe = str(row.get('Tipe', '')).strip().lower()
                row_nominal = int(str(row.get('Nominal', '0')).replace(',', '').strip())
                row_kategori = str(row.get('Kategori', '')).strip().lower()

                # Memeriksa apakah kategori cocok dan data milik user
                if row_kategori.lower() == kategori.lower() and row_user_id == user_id:
                    if row_tipe == 'pemasukan':
                        pemasukan += row_nominal
                    elif row_tipe == 'pengeluaran':
                        pengeluaran += row_nominal

            except Exception as e:
                print(f"❌ Lewati baris karena error: {e} | Data: {row}")

        saldo = pemasukan - pengeluaran

        response = (
            f"📅 Total untuk kategori '{kategori.capitalize()}':\n"
            f"📥 Pemasukan: Rp {pemasukan:,}\n"
            f"📤 Pengeluaran: Rp {pengeluaran:,}\n"
            f"💰 Saldo: Rp {saldo:,}"
        )

        bot.reply_to(message, response)

    except Exception as e:
        bot.reply_to(message, f"❌ Gagal mengambil data kategori.\n{str(e)}")

# === RUNNING BOT ===
print("jalan...")
bot.polling()
