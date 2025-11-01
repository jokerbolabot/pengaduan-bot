import os
import json
import gspread
import logging
import pytz
import asyncio
from datetime import datetime
from telegram import Update, MenuButtonCommands, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import (
    Application, CommandHandler, MessageHandler, ContextTypes,
    filters
)

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Config
BOT_TOKEN = os.environ.get("BOT_TOKEN")
GOOGLE_CREDENTIALS_JSON = os.environ.get("GOOGLE_CREDENTIALS")
GOOGLE_SHEET_NAME = "Pengaduan Global"
ADMIN_IDS = [5704050846, 8388423519]

# Timezone Jakarta
JAKARTA_TZ = pytz.timezone('Asia/Jakarta')

# Website configuration untuk referensi internal saja (tidak ditampilkan ke user)
WEBSITES = {
    'jokerbola': {'code': 'JB', 'name': 'JokerBola'},
    'nagabola': {'code': 'NB', 'name': 'NagaBola'}, 
    'macanbola': {'code': 'MB', 'name': 'MacanBola'},
    'ligapedia': {'code': 'LP', 'name': 'LigaPedia'},
    'pasarliga': {'code': 'PL', 'name': 'PasarLiga'}
}

# Setup Google Sheets
try:
    gc = gspread.service_account_from_dict(json.loads(GOOGLE_CREDENTIALS_JSON))
    sh = gc.open(GOOGLE_SHEET_NAME)
    worksheet = sh.sheet1
    logger.info("✅ Google Sheets connected successfully")
except Exception as e:
    logger.error(f"❌ Google Sheets connection failed: {e}")
    worksheet = None

# ===== KEYBOARD SETUP =====
def get_main_menu_keyboard():
    """Keyboard untuk menu utama"""
    keyboard = [
        [KeyboardButton("📝 Buat Pengaduan Baru"), KeyboardButton("🔍 Cek Status Tiket")],
        [KeyboardButton("ℹ️ Cara Penggunaan"), KeyboardButton("🆘 Bantuan")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, input_field_placeholder="Pilih menu...")

def get_cancel_only_keyboard():
    """Keyboard dengan hanya tombol cancel"""
    keyboard = [[KeyboardButton("❌ Batalkan Proses")]]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, input_field_placeholder="Ketik pesan Anda...")

def get_skip_photo_keyboard():
    """Keyboard untuk skip foto"""
    keyboard = [
        [KeyboardButton("📸 Kirim Foto Bukti"), KeyboardButton("⏩ Lewati Tanpa Foto")],
        [KeyboardButton("❌ Batalkan Proses")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, input_field_placeholder="Pilih opsi...")

# Helper functions
def get_jakarta_time():
    """Dapatkan waktu Jakarta sekarang"""
    return datetime.now(JAKARTA_TZ).strftime("%d/%m/%Y %H:%M:%S")

def generate_ticket_number(website_input):
    """Generate ticket number berdasarkan input website customer"""
    try:
        all_data = worksheet.get_all_records()
        today = datetime.now(JAKARTA_TZ).strftime("%d%m%Y")  # DDMMYYYY
        
        # Cek apakah website input cocok dengan yang kita kenali
        website_code = "OTH"  # Default untuk website lain
        for key, info in WEBSITES.items():
            if key.lower() in website_input.lower() or info['name'].lower() in website_input.lower():
                website_code = info['code']
                break
        
        # Hitung tiket hari ini untuk website tertentu
        count_today = sum(1 for row in all_data 
                         if str(row.get('Ticket ID', '')).startswith(f"{website_code}-{today}"))
        
        return f"{website_code}-{today}-{count_today+1:03d}"
    except Exception as e:
        logger.error(f"Error generating ticket: {e}")
        return f"OTH-{datetime.now(JAKARTA_TZ).strftime('%d%m%Y')}-001"

def escape_html(text):
    """Escape karakter khusus HTML"""
    if not text:
        return ""
    escape_chars = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;'
    }
    return ''.join(escape_chars.get(char, char) for char in str(text))

# ===== STATE MANAGEMENT =====
user_states = {}

def get_user_state(user_id):
    """Dapatkan state user dengan default values"""
    if user_id not in user_states:
        user_states[user_id] = {
            "mode": None,
            "step": None,
            "data": {}
        }
    return user_states[user_id]

def clear_user_state(user_id):
    """Clear state user"""
    if user_id in user_states:
        del user_states[user_id]

# ===== MENU BUTTON HANDLERS =====
async def setup_menu_button(application: Application):
    """Setup menu button untuk semua user"""
    try:
        await application.bot.set_chat_menu_button(
            menu_button=MenuButtonCommands()
        )
        logger.info("✅ Menu button commands berhasil diatur")
    except Exception as e:
        logger.error(f"❌ Gagal mengatur menu button: {e}")

async def set_commands_menu(application: Application):
    """Set daftar commands yang akan muncul di menu button"""
    commands = [
        ("start", "Mulai bot dan tampilkan menu utama"),
        ("buat_pengaduan", "Buat pengaduan baru"),
        ("cek_status", "Cek status tiket pengaduan"),
        ("bantuan", "Tampilkan bantuan penggunaan"),
        ("cancel", "Batalkan proses saat ini")
    ]
    
    try:
        await application.bot.set_my_commands(commands)
        logger.info("✅ Menu commands berhasil diatur")
    except Exception as e:
        logger.error(f"❌ Gagal mengatur menu commands: {e}")

# ===== HANDLERS =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command - reset semua state dan tampilkan menu"""
    user_id = update.message.from_user.id
    clear_user_state(user_id)
    
    welcome_text = (
        "🎉 <b>Selamat datang di Layanan Pengaduan Customer Service!</b>\n\n"
        "Kami siap membantu menyelesaikan masalah Anda di <b>berbagai platform dan website</b>.\n\n"
        "🚀 <b>Layanan kami mencakup:</b>\n"
        "• Website gaming & betting\n"
        "• Platform online lainnya\n"
        "• Masalah akun & transaksi\n"
        "• Layanan customer support\n\n"
        "👇 <b>Silakan pilih menu di bawah:</b>"
    )
    
    await update.message.reply_text(
        welcome_text,
        parse_mode="HTML",
        reply_markup=get_main_menu_keyboard()
    )

async def handle_buat_pengaduan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Memulai pengaduan baru - CUSTOMER INPUT WEBSITE BEBAS"""
    user_id = update.message.from_user.id
    clear_user_state(user_id)
    user_state = get_user_state(user_id)
    user_state["mode"] = "pengaduan"
    user_state["step"] = "nama_website"
    
    await update.message.reply_text(
        "📝 <b>Membuat Pengaduan Baru</b>\n\n"
        "Silakan tulis <b>nama website/platform</b> tempat Anda mengalami masalah:\n\n"
        "💡 <b>Contoh:</b>\n"
        "• JokerBola123\n"
        "• NagaBola88\n" 
        "• MacanBola\n"
        "• Atau website lainnya...\n\n"
        "✍️ <b>Tulis nama website:</b>",
        parse_mode="HTML",
        reply_markup=get_cancel_only_keyboard()
    )

async def handle_cek_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cek status tiket"""
    user_id = update.message.from_user.id
    clear_user_state(user_id)
    user_state = get_user_state(user_id)
    user_state["mode"] = "cek_status"
    user_state["step"] = "input_tiket"
    
    await update.message.reply_text(
        "🔍 <b>Cek Status Tiket Pengaduan</b>\n\n"
        "Silakan masukkan <b>Nomor Tiket</b> yang Anda terima:\n\n"
        "🎫 <b>Format tiket:</b> <code>KODE-TANGGAL-NOMOR</code>\n"
        "💡 <b>Contoh:</b> <code>JB-31102025-001</code>\n\n"
        "✍️ <b>Ketik nomor tiket Anda:</b>",
        parse_mode="HTML",
        reply_markup=get_cancel_only_keyboard()
    )

async def handle_bantuan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menu bantuan"""
    help_text = (
        "🆘 <b>Pusat Bantuan Customer Service</b>\n\n"
        
        "📋 <b>CARA BUAT PENGADUAN:</b>\n"
        "1. Pilih <b>📝 Buat Pengaduan Baru</b>\n"
        "2. Tulis <b>nama website</b> yang bermasalah\n"
        "3. Isi <b>nama lengkap</b> Anda\n" 
        "4. Masukkan <b>username/ID</b> di website tersebut\n"
        "5. Jelaskan <b>keluhan</b> secara detail\n"
        "6. Kirim <b>foto bukti</b> (jika ada)\n\n"
        
        "🔍 <b>CEK STATUS PENGADUAN:</b>\n"
        "1. Pilih <b>🔍 Cek Status Tiket</b>\n"
        "2. Masukkan <b>nomor tiket</b> yang diterima\n"
        "3. Lihat status terbaru pengaduan\n\n"
        
        "💡 <b>INFORMASI PENTING:</b>\n"
        "• Layanan untuk <b>berbagai website/platform</b>\n"
        "• Proses cepat & profesional\n"
        "• Tim support siap membantu 24/7\n"
        "• Simpan nomor tiket dengan baik\n\n"
        
        "❓ <b>MASIH BINGUNG?</b>\n"
        "Gunakan tombol <b>📝 Buat Pengaduan Baru</b> untuk memulai!"
    )
    
    await update.message.reply_text(
        help_text,
        parse_mode="HTML",
        reply_markup=get_main_menu_keyboard()
    )

async def handle_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle cancel dari command atau tombol"""
    user_id = update.message.from_user.id
    clear_user_state(user_id)
    
    await update.message.reply_text(
        "❌ <b>Proses dibatalkan</b>\n\n"
        "Kembali ke menu utama.\n\n"
        "Silakan pilih menu yang diinginkan:",
        parse_mode="HTML",
        reply_markup=get_main_menu_keyboard()
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle semua pesan text dengan state management"""
    user_message = update.message.text.strip()
    user_id = update.message.from_user.id
    
    user_state = get_user_state(user_id)
    logger.info(f"User {user_id} message: {user_message}, state: {user_state}")
    
    # Handle tombol navigasi utama
    if user_message in ["📝 Buat Pengaduan Baru", "/buat_pengaduan"]:
        await handle_buat_pengaduan(update, context)
        return
    elif user_message in ["🔍 Cek Status Tiket", "/cek_status"]:
        await handle_cek_status(update, context)
        return
    elif user_message in ["ℹ️ Cara Penggunaan", "🆘 Bantuan", "/bantuan", "/help"]:
        await handle_bantuan(update, context)
        return
    elif user_message in ["❌ Batalkan Proses", "/cancel", "cancel", "batal"]:
        await handle_cancel(update, context)
        return
    
    # Handle tombol konfirmasi bukti
    if user_message in ["📸 Kirim Foto Bukti", "⏩ Lewati Tanpa Foto"]:
        await handle_bukti_selection(update, context, user_message)
        return
    
    # Handle berdasarkan state
    mode = user_state["mode"]
    step = user_state.get("step", "")
    
    if mode == "pengaduan":
        await handle_pengaduan_flow(update, context, user_message, user_state)
    elif mode == "cek_status" and step == "input_tiket":
        await proses_cek_status(update, context, user_message, user_state)
    else:
        logger.warning(f"Unknown state for user {user_id}: {user_state}")
        clear_user_state(user_id)
        await show_menu(update, context)

async def handle_bukti_selection(update: Update, context: ContextTypes.DEFAULT_TYPE, selection: str):
    """Handle pemilihan opsi bukti"""
    user_id = update.message.from_user.id
    user_state = get_user_state(user_id)
    
    if selection == "📸 Kirim Foto Bukti":
        await update.message.reply_text(
            "📸 <b>Silakan kirim foto bukti sekarang:</b>\n\n"
            "Anda dapat mengirim:\n"
            "• Screenshot error\n"
            "• Foto transaksi\n" 
            "• Bukti percakapan\n"
            "• Atau bukti lainnya\n\n"
            "📎 <b>Unggah foto dari galeri Anda...</b>",
            parse_mode="HTML",
            reply_markup=get_cancel_only_keyboard()
        )
    elif selection == "⏩ Lewati Tanpa Foto":
        user_state["data"]["bukti"] = "Tidak ada bukti foto"
        await selesaikan_pengaduan(update, context, user_state)

async def handle_pengaduan_flow(update: Update, context: ContextTypes.DEFAULT_TYPE, user_message: str, user_state: dict):
    """Handle flow pengaduan - WEBSITE DARI INPUT CUSTOMER"""
    step = user_state.get("step", "")
    user_id = update.message.from_user.id
    
    if step == "nama_website":
        # Simpan input website dari customer (bebas)
        user_state["data"]["website_input"] = user_message
        user_state["step"] = "nama"
        
        await update.message.reply_text(
            f"✅ <b>Website tercatat: {escape_html(user_message)}</b>\n\n"
            "Silakan kirim <b>Nama Lengkap</b> Anda:\n\n"
            "✍️ <b>Ketik nama lengkap:</b>",
            parse_mode="HTML",
            reply_markup=get_cancel_only_keyboard()
        )
        
    elif step == "nama":
        user_state["data"]["nama"] = user_message
        user_state["data"]["user_id"] = update.message.from_user.id
        user_state["data"]["username_tg"] = update.message.from_user.username or "-"
        user_state["step"] = "username_website"
        
        website_input = user_state["data"]["website_input"]
        
        await update.message.reply_text(
            f"🆔 <b>Masukkan Username / ID Anda di {escape_html(website_input)}:</b>\n\n"
            "✍️ <b>Ketik username atau ID Anda:</b>",
            parse_mode="HTML",
            reply_markup=get_cancel_only_keyboard()
        )
        
    elif step == "username_website":
        user_state["data"]["username_website"] = user_message
        user_state["step"] = "keluhan"
        
        await update.message.reply_text(
            "📋 <b>Jelaskan keluhan Anda secara detail:</b>\n\n"
            "💬 <b>Contoh yang baik:</b>\n"
            "• Kapan masalah terjadi?\n"
            "• Error message apa yang muncul?\n"
            "• Sudah coba apa untuk memperbaiki?\n"
            "• Transaksi tertahan/tidak masuk?\n\n"
            "✍️ <b>Ketik penjelasan keluhan:</b>",
            parse_mode="HTML",
            reply_markup=get_cancel_only_keyboard()
        )
        
    elif step == "keluhan":
        user_state["data"]["keluhan"] = user_message
        user_state["step"] = "bukti"
        
        await update.message.reply_text(
            "📸 <b>Bukti Pendukung (Opsional)</b>\n\n"
            "Pilih opsi untuk bukti:\n\n"
            "• 📸 Kirim Foto Bukti - Unggah foto/screenshot\n"
            "• ⏩ Lewati Tanpa Foto - Lanjut tanpa bukti\n\n"
            "💡 <b>Rekomendasi:</b> Foto bukti membantu proses penyelesaian lebih cepat!",
            parse_mode="HTML",
            reply_markup=get_skip_photo_keyboard()
        )

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle photo untuk bukti"""
    user_id = update.message.from_user.id
    user_state = get_user_state(user_id)
    
    mode = user_state.get("mode")
    step = user_state.get("step")
    
    if mode == "pengaduan" and step == "bukti":
        file_id = update.message.photo[-1].file_id
        file_obj = await context.bot.get_file(file_id)
        user_state["data"]["bukti"] = file_obj.file_path
        
        await update.message.reply_text(
            "✅ <b>Foto bukti berhasil diterima!</b>\n\n"
            "🔄 <b>Menyimpan pengaduan Anda...</b>",
            parse_mode="HTML",
            reply_markup=ReplyKeyboardRemove()
        )
        
        await selesaikan_pengaduan(update, context, user_state)
    else:
        await update.message.reply_text(
            "❌ Foto tidak diperlukan saat ini.\n\nSilakan pilih menu yang sesuai:",
            reply_markup=get_main_menu_keyboard()
        )

async def selesaikan_pengaduan(update: Update, context: ContextTypes.DEFAULT_TYPE, user_state: dict):
    """Selesaikan pengaduan dan simpan ke Google Sheets"""
    user_id = update.message.from_user.id
    data = user_state["data"]
    timestamp = get_jakarta_time()
    
    # Generate ticket number berdasarkan input website customer
    website_input = data["website_input"]
    ticket_id = generate_ticket_number(website_input)
    
    logger.info(f"Processing new complaint from user {user_id}: {ticket_id}")
    
    try:
        # Save to Google Sheets
        worksheet.append_row([
            timestamp,                           # Timestamp
            ticket_id,                           # Ticket ID
            data["website_input"],               # Website Input (dari customer)
            data["nama"],                        # Nama
            data["username_website"],            # Username Website  
            data["keluhan"],                     # Keluhan
            data.get("bukti", "Tidak ada bukti foto"), # Bukti
            data["username_tg"],                 # Username_TG
            data["user_id"],                     # User_ID
            "Sedang diproses"                    # Status
        ])
        logger.info(f"✅ Data saved to Google Sheets: {ticket_id}")
    except Exception as e:
        logger.error(f"❌ Failed to save to Google Sheets: {e}")
        await update.message.reply_text(
            "❌ Maaf, terjadi gangguan sistem. Silakan coba lagi nanti.\n\nSilakan pilih menu:",
            reply_markup=get_main_menu_keyboard()
        )
        clear_user_state(user_id)
        return

    # Success message
    success_message = (
        f"🎉 <b>PENGADUAN BERHASIL DICATAT!</b>\n\n"
        f"✅ <b>Terima kasih, {escape_html(data['nama'])}!</b>\n\n"
        f"📋 <b>DETAIL PENGADUAN:</b>\n"
        f"• 🌐 <b>Website:</b> {escape_html(data['website_input'])}\n"
        f"• 🎫 <b>Nomor Tiket:</b> <code>{ticket_id}</code>\n"
        f"• 📊 <b>Status:</b> Sedang diproses\n"
        f"• ⏰ <b>Waktu:</b> {timestamp}\n\n"
        f"⚠️ <b>PENTING: SIMPAN NOMOR TIKET INI!</b>\n"
        f"Gunakan untuk mengecek status pengaduan Anda.\n\n"
        f"🔍 <b>Cek Status:</b> Pilih <b>🔍 Cek Status Tiket</b>\n\n"
        f"📞 <b>Tim kami akan segera menghubungi Anda!</b>"
    )
    
    await update.message.reply_text(
        success_message,
        parse_mode="HTML",
        reply_markup=get_main_menu_keyboard()
    )

    # Notify admin
    await kirim_notifikasi_admin_with_retry(context, data, ticket_id, timestamp, user_id)
    
    clear_user_state(user_id)

async def kirim_notifikasi_admin_with_retry(context, data, ticket_id, timestamp, user_id, retry_count=3):
    """Kirim notifikasi ke admin dengan retry mechanism"""
    for attempt in range(retry_count):
        try:
            success = await kirim_notifikasi_admin(context, data, ticket_id, timestamp)
            if success:
                logger.info(f"✅ Notifications sent successfully for ticket {ticket_id}")
                return
            else:
                logger.warning(f"⚠️ Some notifications failed for ticket {ticket_id}, attempt {attempt + 1}")
        except Exception as e:
            logger.error(f"❌ Error sending notifications for ticket {ticket_id}, attempt {attempt + 1}: {e}")
        
        if attempt < retry_count - 1:
            await asyncio.sleep(2)
    
    logger.error(f"❌ All notification attempts failed for ticket {ticket_id}")

async def kirim_notifikasi_admin(context, data, ticket_id, timestamp):
    """Send notification to admin"""
    try:
        # Escape data untuk HTML
        nama_escaped = escape_html(data.get("nama", ""))
        username_website_escaped = escape_html(data.get("username_website", ""))
        keluhan_escaped = escape_html(data.get("keluhan", ""))
        username_tg_escaped = escape_html(data.get("username_tg", ""))
        user_id_escaped = escape_html(data.get("user_id", ""))
        website_escaped = escape_html(data.get("website_input", ""))
        
        bukti_text = data.get("bukti", "Tidak ada bukti foto")
        if bukti_text != "Tidak ada bukti foto" and bukti_text.startswith("http"):
            bukti_display = f'<a href="{bukti_text}">📎 Lihat Bukti</a>'
        else:
            bukti_display = escape_html(bukti_text)
        
        # Buat message untuk admin
        message = (
            f"🚨 <b>PENGADUAN BARU DITERIMA</b> 🚨\n\n"
            f"🎫 <b>Ticket ID:</b> <code>{ticket_id}</code>\n"
            f"🌐 <b>Website:</b> {website_escaped}\n"
            f"⏰ <b>Waktu:</b> {timestamp} (WIB)\n\n"
            f"<b>📋 Data Pelapor:</b>\n"
            f"• <b>Nama:</b> {nama_escaped}\n"
            f"• <b>Username Website:</b> {username_website_escaped}\n"
            f"• <b>Telegram:</b> @{username_tg_escaped}\n"
            f"• <b>User ID:</b> <code>{user_id_escaped}</code>\n\n"
            f"<b>📝 Keluhan:</b>\n{keluhan_escaped}\n\n"
            f"<b>📎 Bukti:</b> {bukti_display}\n\n"
            f"⚠️ <b>Segera tindak lanjuti pengaduan ini!</b>"
        )
        
        success_count = 0
        for admin_id in ADMIN_IDS:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=message,
                    parse_mode="HTML",
                    disable_web_page_preview=True
                )
                success_count += 1
                logger.info(f"✅ Notification sent to admin {admin_id}")
            except Exception as e:
                logger.error(f"❌ Failed to send to admin {admin_id}: {e}")
        
        logger.info(f"📊 Notifications sent to {success_count}/{len(ADMIN_IDS)} admins")
        return success_count > 0
        
    except Exception as e:
        logger.error(f"❌ Error in kirim_notifikasi_admin: {e}")
        return False

async def proses_cek_status(update: Update, context: ContextTypes.DEFAULT_TYPE, ticket_id: str, user_state: dict):
    """Proses cek status tiket"""
    current_user_id = update.message.from_user.id
    
    try:
        all_data = worksheet.get_all_records()
        found = False
        user_owns_ticket = False
        ticket_data = None
        
        for row in all_data:
            if row.get('Ticket ID') == ticket_id:
                found = True
                ticket_user_id = row.get('User_ID')
                if str(ticket_user_id) == str(current_user_id):
                    user_owns_ticket = True
                    ticket_data = row
                break
        
        if found and user_owns_ticket and ticket_data:
            status = ticket_data.get('Status', 'Tidak diketahui')
            status_emoji = {
                'Sedang diproses': '🟡',
                'Selesai': '✅',
                'Ditolak': '❌',
                'Menunggu konfirmasi': '🟠'
            }.get(status, '⚪')
            
            nama_escaped = escape_html(ticket_data.get('Nama', 'Tidak ada'))
            username_escaped = escape_html(ticket_data.get('Username Website', 'Tidak ada'))
            keluhan_escaped = escape_html(ticket_data.get('Keluhan', 'Tidak ada'))
            timestamp_escaped = escape_html(ticket_data.get('Timestamp', 'Tidak ada'))
            website_escaped = escape_html(ticket_data.get('Nama Website', 'Tidak ada'))
            
            status_message = (
                f"📋 <b>STATUS PENGADUAN</b>\n\n"
                f"{status_emoji} <b>Status:</b> <b>{status}</b>\n"
                f"🎫 <b>Ticket ID:</b> <code>{ticket_id}</code>\n"
                f"🌐 <b>Website:</b> {website_escaped}\n"
                f"👤 <b>Nama:</b> {nama_escaped}\n"
                f"🆔 <b>Username:</b> {username_escaped}\n"
                f"💬 <b>Keluhan:</b> {keluhan_escaped}\n"
                f"⏰ <b>Waktu:</b> {timestamp_escaped}\n\n"
                f"Terima kasih telah menggunakan layanan kami! 🙏"
            )
            
            await update.message.reply_text(
                status_message,
                parse_mode="HTML",
                reply_markup=get_main_menu_keyboard()
            )
        else:
            await update.message.reply_text(
                "❌ <b>Tiket tidak ditemukan.</b>\n\n"
                "Pastikan:\n"
                "• Nomor tiket benar\n"
                "• Tidak ada typo\n"
                "• Tiket milik Anda sendiri\n\n"
                "Silakan coba lagi:",
                parse_mode="HTML",
                reply_markup=get_main_menu_keyboard()
            )
            
    except Exception as e:
        logger.error(f"Error checking status: {e}")
        await update.message.reply_text(
            "❌ Terjadi error. Silakan coba lagi.\n\nSilakan pilih menu:",
            parse_mode="HTML",
            reply_markup=get_main_menu_keyboard()
        )
    
    clear_user_state(current_user_id)

async def show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Tampilkan menu utama"""
    await update.message.reply_text(
        "🤖 <b>Layanan Pengaduan Customer Service</b>\n\n"
        "Kami siap membantu masalah Anda di berbagai website & platform.\n\n"
        "👇 <b>Silakan pilih menu:</b>",
        parse_mode="HTML",
        reply_markup=get_main_menu_keyboard()
    )

async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel command"""
    await handle_cancel(update, context)

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle error"""
    logger.error(f"Error: {context.error}")
    if update and update.message:
        await update.message.reply_text(
            "❌ Terjadi error, silakan coba lagi.\n\nSilakan pilih menu:",
            reply_markup=get_main_menu_keyboard()
        )

async def post_init(application: Application):
    """Setup setelah bot diinisialisasi"""
    await set_commands_menu(application)
    await setup_menu_button(application)

def main():
    """Main function"""
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN not found!")
        return
    
    if not GOOGLE_CREDENTIALS_JSON:
        logger.error("GOOGLE_CREDENTIALS not found!")
        return

    if not worksheet:
        logger.error("Google Sheets not connected!")
        return

    try:
        application = Application.builder().token(BOT_TOKEN).post_init(post_init).build()
        
        # Command handlers
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("cancel", cancel_command))
        application.add_handler(CommandHandler("help", handle_bantuan))
        application.add_handler(CommandHandler("buat_pengaduan", handle_buat_pengaduan))
        application.add_handler(CommandHandler("cek_status", handle_cek_status))
        application.add_handler(CommandHandler("bantuan", handle_bantuan))
        
        # Message handlers
        application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        
        application.add_error_handler(error_handler)
        
        logger.info("✅ Universal Complaint Bot starting...")
        application.run_polling(
            drop_pending_updates=True,
            allowed_updates=Update.ALL_TYPES
        )
        
    except Exception as e:
        logger.error(f"Fatal error: {e}")

if __name__ == '__main__':
    main()
