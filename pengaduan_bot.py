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

# Website configuration dengan kode yang FIXED
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
        [KeyboardButton("📝 Buat Pengaduan"), KeyboardButton("🔍 Cek Status")],
        [KeyboardButton("ℹ️ Bantuan"), KeyboardButton("❌ Batalkan")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, input_field_placeholder="Pilih menu...")

def get_website_selection_keyboard():
    """Keyboard untuk pemilihan website"""
    websites = list(WEBSITES.values())
    keyboard = []
    
    # Buat 2 kolom untuk tombol website
    for i in range(0, len(websites), 2):
        row = []
        if i < len(websites):
            row.append(KeyboardButton(f"🌐 {websites[i]['name']}"))
        if i + 1 < len(websites):
            row.append(KeyboardButton(f"🌐 {websites[i + 1]['name']}"))
        keyboard.append(row)
    
    keyboard.append([KeyboardButton("🔙 Kembali")])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, input_field_placeholder="Pilih website...")

def get_cancel_only_keyboard():
    """Keyboard dengan hanya tombol cancel"""
    keyboard = [[KeyboardButton("🔙 Kembali")]]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, input_field_placeholder="Ketik pesan atau kembali...")

def get_confirmation_keyboard():
    """Keyboard untuk konfirmasi bukti"""
    keyboard = [
        [KeyboardButton("📸 Kirim Foto"), KeyboardButton("➡️ Lanjut Tanpa Bukti")],
        [KeyboardButton("🔙 Kembali")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, input_field_placeholder="Pilih opsi...")

# Helper functions
def get_jakarta_time():
    """Dapatkan waktu Jakarta sekarang"""
    return datetime.now(JAKARTA_TZ).strftime("%d/%m/%Y %H:%M:%S")

def generate_ticket_number(website_code):
    """Generate ticket number dengan format: CODE-DDMMYYYY-NOMOR"""
    try:
        all_data = worksheet.get_all_records()
        today = datetime.now(JAKARTA_TZ).strftime("%d%m%Y")  # DDMMYYYY
        
        # Hitung tiket hari ini untuk website tertentu
        count_today = sum(1 for row in all_data 
                         if str(row.get('Ticket ID', '')).startswith(f"{website_code}-{today}"))
        
        return f"{website_code}-{today}-{count_today+1:03d}"
    except Exception as e:
        logger.error(f"Error generating ticket: {e}")
        return f"{website_code}-{datetime.now(JAKARTA_TZ).strftime('%d%m%Y')}-001"

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
user_website_history = {}  # Untuk melacak website yang pernah digunakan user

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

def update_user_website_history(user_id, website_name):
    """Update history website user"""
    user_website_history[user_id] = website_name

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
        "🎉 <b>Selamat datang di Layanan Pengaduan Premium!</b>\n\n"
        "🚀 Kami siap memberikan pelayanan terbaik untuk pengaduan Anda.\n\n"
        "📱 <b>Gunakan tombol di bawah untuk navigasi cepat!</b>\n\n"
        "💡 <b>Tips:</b> Simpan nomor tiket dengan baik untuk pengecekan status."
    )
    
    await update.message.reply_text(
        welcome_text,
        parse_mode="HTML",
        reply_markup=get_main_menu_keyboard()
    )

async def handle_buat_pengaduan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Memulai pengaduan baru - dengan tombol website"""
    user_id = update.message.from_user.id
    clear_user_state(user_id)
    user_state = get_user_state(user_id)
    user_state["mode"] = "pengaduan"
    user_state["step"] = "nama_website"
    
    await update.message.reply_text(
        "📝 <b>Membuat Pengaduan Baru</b>\n\n"
        "Silakan pilih <b>website</b> yang ingin Anda laporkan:\n\n"
        "👇 <b>Gunakan tombol di bawah:</b>",
        parse_mode="HTML",
        reply_markup=get_website_selection_keyboard()
    )

async def handle_cek_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cek status tiket"""
    user_id = update.message.from_user.id
    clear_user_state(user_id)
    user_state = get_user_state(user_id)
    user_state["mode"] = "cek_status"
    user_state["step"] = "input_tiket"
    
    # Berikan contoh tiket berdasarkan website history user jika ada
    example_ticket = ""
    if user_id in user_website_history:
        website_name = user_website_history[user_id]
        website_code = None
        for key, info in WEBSITES.items():
            if info['name'] == website_name:
                website_code = info['code']
                break
        
        if website_code:
            example_ticket = f"\n<b>Contoh:</b> <code>{website_code}-31102025-001</code>"
    
    await update.message.reply_text(
        f"🔍 <b>Cek Status Tiket</b>\n\n"
        f"Silakan kirim <b>Nomor Tiket</b> Anda:{example_ticket}\n\n"
        "✍️ <b>Ketik nomor tiket Anda:</b>",
        parse_mode="HTML",
        reply_markup=get_cancel_only_keyboard()
    )

async def handle_bantuan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menu bantuan dengan tampilan yang lebih baik"""
    help_text = (
        "ℹ️ <b>Pusat Bantuan & Panduan</b>\n\n"
        
        "📋 <b>CARA PENGGUNAAN:</b>\n"
        "1. Pilih <b>📝 Buat Pengaduan</b>\n"
        "2. Pilih website dari tombol yang tersedia\n"
        "3. Isi data sesuai permintaan\n"
        "4. Dapatkan nomor tiket\n\n"
        
        "🔍 <b>CEK STATUS:</b>\n"
        "1. Pilih <b>🔍 Cek Status</b>\n"
        "2. Masukkan nomor tiket\n"
        "3. Lihat status pengaduan\n\n"
        
        "💡 <b>TIPS PENTING:</b>\n"
        "• Simpan nomor tiket dengan baik\n"
        "• Berikan informasi yang jelas dan lengkap\n"
        "• Siapkan bukti pendukung jika ada\n"
        "• Bisa buat pengaduan berkali-kali\n\n"
        
        "🆘 <b>BUTUH BANTUAN?</b>\n"
        "Gunakan tombol <b>🔙 Kembali</b> untuk kembali ke menu utama"
    )
    
    await update.message.reply_text(
        help_text,
        parse_mode="HTML",
        reply_markup=get_cancel_only_keyboard()
    )

async def handle_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle cancel dari command atau tombol"""
    user_id = update.message.from_user.id
    clear_user_state(user_id)
    
    await update.message.reply_text(
        "❌ <b>Operasi dibatalkan</b>\n\n"
        "Kembali ke menu utama.\n\n"
        "Silakan pilih menu yang diinginkan:",
        parse_mode="HTML",
        reply_markup=get_main_menu_keyboard()
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle semua pesan text dengan state management yang lebih baik"""
    user_message = update.message.text.strip()
    user_id = update.message.from_user.id
    
    user_state = get_user_state(user_id)
    logger.info(f"User {user_id} message: {user_message}, state: {user_state}")
    
    # Handle tombol navigasi utama
    if user_message in ["📝 Buat Pengaduan", "/buat_pengaduan"]:
        await handle_buat_pengaduan(update, context)
        return
    elif user_message in ["🔍 Cek Status", "/cek_status"]:
        await handle_cek_status(update, context)
        return
    elif user_message in ["ℹ️ Bantuan", "/bantuan", "/help"]:
        await handle_bantuan(update, context)
        return
    elif user_message in ["❌ Batalkan", "🔙 Kembali", "/cancel", "cancel", "batal"]:
        await handle_cancel(update, context)
        return
    
    # Handle tombol website
    if user_message.startswith("🌐 "):
        website_name = user_message[2:]  # Hapus emoji
        await handle_website_selection(update, context, website_name)
        return
    
    # Handle tombol konfirmasi bukti
    if user_message in ["📸 Kirim Foto", "➡️ Lanjut Tanpa Bukti"]:
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

async def handle_website_selection(update: Update, context: ContextTypes.DEFAULT_TYPE, website_name: str):
    """Handle pemilihan website dari tombol"""
    user_id = update.message.from_user.id
    user_state = get_user_state(user_id)
    
    # Cari website berdasarkan nama
    website_found = None
    website_code = None
    
    for key, info in WEBSITES.items():
        if info['name'] == website_name:
            website_found = info['name']
            website_code = info['code']
            break
    
    if website_found:
        # Update website history
        update_user_website_history(user_id, website_found)
        
        user_state["data"]["website_name"] = website_found
        user_state["data"]["website_code"] = website_code
        user_state["step"] = "nama"
        
        await update.message.reply_text(
            f"✅ <b>{website_found} Dipilih!</b>\n\n"
            "Silakan kirim <b>Nama Lengkap</b> Anda:\n\n"
            "✍️ <b>Ketik nama lengkap Anda:</b>",
            parse_mode="HTML",
            reply_markup=get_cancel_only_keyboard()
        )
    else:
        await update.message.reply_text(
            "❌ <b>Website tidak dikenali!</b>\n\n"
            "Silakan pilih website dari tombol yang tersedia:",
            parse_mode="HTML",
            reply_markup=get_website_selection_keyboard()
        )

async def handle_bukti_selection(update: Update, context: ContextTypes.DEFAULT_TYPE, selection: str):
    """Handle pemilihan opsi bukti"""
    user_id = update.message.from_user.id
    user_state = get_user_state(user_id)
    
    if selection == "📸 Kirim Foto":
        await update.message.reply_text(
            "📸 <b>Silakan kirim foto bukti sekarang:</b>\n\n"
            "📎 Unggah foto dari galeri Anda...",
            parse_mode="HTML",
            reply_markup=get_cancel_only_keyboard()
        )
    elif selection == "➡️ Lanjut Tanpa Bukti":
        user_state["data"]["bukti"] = "Tidak ada"
        await selesaikan_pengaduan(update, context, user_state)

async def handle_pengaduan_flow(update: Update, context: ContextTypes.DEFAULT_TYPE, user_message: str, user_state: dict):
    """Handle flow pengaduan yang lebih robust"""
    step = user_state.get("step", "")
    user_id = update.message.from_user.id
    
    if step == "nama":
        user_state["data"]["nama"] = user_message
        user_state["data"]["user_id"] = update.message.from_user.id
        user_state["data"]["username_tg"] = update.message.from_user.username or "-"
        user_state["step"] = "username_website"
        
        website_name = user_state["data"]["website_name"]
        
        await update.message.reply_text(
            f"🆔 <b>Masukkan Username / ID {website_name} Anda:</b>\n\n"
            "✍️ <b>Ketik username/ID Anda:</b>",
            parse_mode="HTML",
            reply_markup=get_cancel_only_keyboard()
        )
        
    elif step == "username_website":
        user_state["data"]["username_website"] = user_message
        user_state["step"] = "keluhan"
        
        await update.message.reply_text(
            "📋 <b>Jelaskan keluhan Anda secara detail:</b>\n\n"
            "✍️ <b>Ketik penjelasan keluhan:</b>\n"
            "• Masalah apa yang terjadi?\n"
            "• Kapan terjadi?\n"
            "• Bagaimana kronologinya?",
            parse_mode="HTML",
            reply_markup=get_cancel_only_keyboard()
        )
        
    elif step == "keluhan":
        user_state["data"]["keluhan"] = user_message
        user_state["step"] = "bukti"
        
        await update.message.reply_text(
            "📸 <b>Bukti Pendukung</b>\n\n"
            "Pilih opsi untuk bukti:\n\n"
            "• 📸 Kirim Foto - Unggah foto bukti\n"
            "• ➡️ Lanjut Tanpa Bukti - Lanjut tanpa bukti\n\n"
            "👇 <b>Pilih salah satu:</b>",
            parse_mode="HTML",
            reply_markup=get_confirmation_keyboard()
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
            "🔄 <b>Menyimpan pengaduan...</b>",
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
    website_code = data["website_code"]
    ticket_id = generate_ticket_number(website_code)
    
    logger.info(f"Processing new complaint from user {user_id}: {ticket_id}")
    
    try:
        # Save to Google Sheets dengan kolom tambahan
        worksheet.append_row([
            timestamp,                           # Timestamp (DD/MM/YYYY HH:MM:SS)
            ticket_id,                           # Ticket ID (CODE-DDMMYYYY-NOMOR)
            data["website_name"],                # Nama Website
            data["nama"],                        # Nama
            data["username_website"],            # Username Website  
            data["keluhan"],                     # Keluhan
            data.get("bukti", "Tidak ada"),      # Bukti
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

    website_name = data["website_name"]
    
    success_message = (
        f"🎉 <b>PENGADUAN BERHASIL DICATAT!</b>\n\n"
        f"✅ <b>Terima kasih, {escape_html(data['nama'])}!</b>\n\n"
        f"📋 <b>DETAIL PENGADUAN:</b>\n"
        f"• 🌐 <b>Website:</b> {website_name}\n"
        f"• 🎫 <b>Nomor Tiket:</b> <code>{ticket_id}</code>\n"
        f"• 📊 <b>Status:</b> Sedang diproses\n"
        f"• ⏰ <b>Waktu:</b> {timestamp}\n\n"
        f"💡 <b>SIMPAN NOMOR TIKET INI!</b>\n"
        f"Gunakan untuk cek status pengaduan.\n\n"
        f"🔄 <b>Ingin buat pengaduan lagi?</b>\n"
        f"Pilih <b>📝 Buat Pengaduan</b>"
    )
    
    await update.message.reply_text(
        success_message,
        parse_mode="HTML",
        reply_markup=get_main_menu_keyboard()
    )

    # Notify admin dengan HTML parsing yang lebih aman
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
    """Send notification to admin - FIXED VERSION WITH HTML"""
    try:
        # Escape data untuk HTML
        nama_escaped = escape_html(data.get("nama", ""))
        username_website_escaped = escape_html(data.get("username_website", ""))
        keluhan_escaped = escape_html(data.get("keluhan", ""))
        username_tg_escaped = escape_html(data.get("username_tg", ""))
        user_id_escaped = escape_html(data.get("user_id", ""))
        website_name_escaped = escape_html(data.get("website_name", ""))
        
        bukti_text = data.get("bukti", "Tidak ada")
        if bukti_text != "Tidak ada" and bukti_text.startswith("http"):
            bukti_display = f'<a href="{bukti_text}">📎 Lihat Bukti</a>'
        else:
            bukti_display = escape_html(bukti_text)
        
        # Buat message dengan HTML parsing yang lebih aman
        message = (
            f"🚨 <b>PENGADUAN BARU DITERIMA</b> 🚨\n\n"
            f"🎫 <b>Ticket ID:</b> <code>{ticket_id}</code>\n"
            f"🌐 <b>Website:</b> {website_name_escaped}\n"
            f"⏰ <b>Waktu:</b> {timestamp} (WIB)\n\n"
            f"<b>📋 Data Pelapor:</b>\n"
            f"• <b>Nama:</b> {nama_escaped}\n"
            f"• <b>Username {website_name_escaped}:</b> {username_website_escaped}\n"
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
    """Proses cek status tiket - DIPERBAIKI UNTUK WEBSITE"""
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
        "🤖 <b>Layanan Pengaduan Premium</b>\n\n"
        "🚀 Kami siap melayani pengaduan Anda dengan cepat dan profesional.\n\n"
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
        
        logger.info("✅ Complaint Bot with Buttons starting...")
        application.run_polling(
            drop_pending_updates=True,
            allowed_updates=Update.ALL_TYPES
        )
        
    except Exception as e:
        logger.error(f"Fatal error: {e}")

if __name__ == '__main__':
    main()
