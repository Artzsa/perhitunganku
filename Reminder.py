import telebot
import gspread
from datetime import datetime, timedelta
from oauth2client.service_account import ServiceAccountCredentials
import time
import schedule

# === KONFIGURASI TOKEN TELEGRAM DAN GOOGLE SHEET ===
TOKEN = '8048576532:AAEAYO9-1RHEKF-k-NlXoOgAkCJGmocX6lo'
bot = telebot.TeleBot(TOKEN)

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
client = gspread.authorize(creds)
sheet = client.open("Perhitunganku").worksheet("Sheet2")  # Menggunakan Sheet2 untuk pengingat

# === MENAMBAHKAN PENGINGAT KE SHEET2 ===
@bot.message_handler(commands=['ingat'])
def handle_ingat(message):
    try:
        # Format pesan pengingat: /ingat HH:MM [pesan]
        parts = message.text.split()
        if len(parts) != 3:
            raise ValueError("Format salah. Gunakan: /ingat HH:MM [pesan]")
        
        waktu_input = parts[1]
        pengingat = parts[2]
        
        # Menyimpan pengingat di Sheet2
        user_id = message.from_user.id
        tanggal = datetime.now().strftime('%d-%m-%Y')
        sheet.append_row([tanggal, waktu_input, pengingat, user_id])
        
        bot.reply_to(message, f"✅ Pengingat untuk {waktu_input} telah disimpan: {pengingat}")
    except Exception as e:
        bot.reply_to(message, f"❌ Terjadi kesalahan: {e}")

# === CEK DAN KIRIM PENGINGAT SETIAP MENIT ===
def cek_pengingat():
    now = datetime.now().strftime('%H:%M')  # Mendapatkan waktu saat ini dalam format HH:MM
    records = sheet.get_all_records()  # Ambil semua catatan dari Sheet2
    
    for row in records:
        if row['Waktu'] == now:  # Jika waktu pengingat sama dengan waktu saat ini
            user_id = row['ID User']
            pengingat = row['Pengingat']
            bot.send_message(user_id, f"⏰ Pengingat: {pengingat}")  # Kirim pesan pengingat ke pengguna
            
# Menjadwalkan pengecekan setiap menit
schedule.every(1).minute.do(cek_pengingat)

# === JALANKAN BOT ===
def run_bot():
    print("🤖 Bot berjalan...")
    while True:
        schedule.run_pending()
        time.sleep(60)  # Tunggu 1 menit sebelum memeriksa pengingat lagi

# Mulai pengecekan pengingat dan menjalankan bot
run_bot()
