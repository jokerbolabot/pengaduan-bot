import os
import json
import gspread
import logging
import pytz
import asyncio
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
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
GOOGLE_SHEET_NAME = "Pengaduan JokerBola"
ADMIN_IDS = [5704050846, 8388423519]

# Timezone Jakarta
JAKARTA_TZ = pytz.timezone('Asia/Jakarta')

# Setup Google Sheets
try:
    gc = gspread.service_account_from_dict(json.loads(GOOGLE_CREDENTIALS_JSON))
    sh = gc.open(GOOGLE_SHEET_NAME)
    worksheet = sh.sheet1
    logger.info("✅ Google Sheets connected successfully")
except Exception as e:
    logger.error(f"❌ Google Sheets connection failed: {e}")
    worksheet = None

# Helper functions
def get_jakarta_time():
    """Dapatkan waktu Jakarta sekarang"""
    return datetime.now(JAKARTA_TZ).strftime("%Y-%m-%d %H:%M:%S")

def generate_ticket_number():
    try:
        all_data = worksheet.get_all_records()
        today = datetime.now(JAKARTA_TZ).strftime("%Y%m%d")
        count_today = sum(1 for row in all_data if str(row.get('Timestamp', '')).startswith(datetime.now(JAKARTA_TZ).strftime("%Y-%m-%d")))
        return f"JB-{today}-{count_today+1:03d}"
    except Exception as e:
        logger.error(f"Error generating ticket: {e}")
        return f"JB-{datetime.now(JAKARTA_TZ).strftime('%Y%m%d')}-001"

def escape_markdown(text):
    """Escape karakter khusus MarkdownV2"""
    if not text:
        return ""
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    return ''.join(f'\\{char}' if char in escape_chars else char for char in str(text))

def main_menu_keyboard():
    return ReplyKeyboardMarkup([
        ['📝 Buat Pengaduan', '🔍 Cek Status'],
        ['ℹ️ Bantuan']
    ], resize_keyboard=True)

def cancel_keyboard():
    return ReplyKeyboardMarkup([
        ['❌ Batalkan']
    ], resize_keyboard=True)

# ===== IMPROVED STATE MANAGEMENT WITH USER LOCK =====
# Dictionary untuk menyimpan state setiap user
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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command - reset semua state dan tampilkan menu"""
    user_id = update.message.from_user.id
    
    # Reset semua state user
    clear_user_state(user_id)
    
    await update.message.reply_text(
        "🤖 **Selamat datang di Layanan Pengaduan JokerBola**\n\n"
        "Silakan pilih menu di bawah:",
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard()
    )

async def handle_buat_pengaduan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Memulai pengaduan baru"""
    user_id = update.message.from_user.id
    
    # Reset state dan mulai fresh
    clear_user_state(user_id)
    user_state = get_user_state(user_id)
    user_state["mode"] = "pengaduan"
    user_state["step"] = "nama"
    
    await update.message.reply_text(
        "📝 **Membuat Pengaduan Baru**\n\n"
        "Silakan kirim **Nama Lengkap** Anda:\n\n"
        "Ketik ❌ Batalkan untuk membatalkan",
        parse_mode="Markdown",
        reply_markup=cancel_keyboard()
    )

async def handle_cek_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cek status tiket"""
    user_id = update.message.from_user.id
    
    # Reset state dan mulai fresh
    clear_user_state(user_id)
    user_state = get_user_state(user_id)
    user_state["mode"] = "cek_status"
    user_state["step"] = "input_tiket"
    
    await update.message.reply_text(
        "🔍 **Cek Status Tiket**\n\n"
        "Silakan kirim **Nomor Tiket** Anda:\n"
        "Contoh: `JB-20251219-001`\n\n"
        "Ketik ❌ Batalkan untuk membatalkan",
        parse_mode="Markdown",
        reply_markup=cancel_keyboard()
    )

async def handle_bantuan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menu bantuan"""
    await update.message.reply_text(
        "ℹ️ **Bantuan Penggunaan**\n\n"
        "📝 **Cara Buat Pengaduan:**\n"
        "1. Klik '📝 Buat Pengaduan'\n"
        "2. Isi nama lengkap\n"
        "3. Isi username JokerBola\n"
        "4. Jelaskan keluhan\n"
        "5. Kirim bukti (opsional)\n\n"
        "🔍 **Cek Status:**\n"
        "1. Klik '🔍 Cek Status'\n"
        "2. Masukkan nomor tiket\n\n"
        "💡 **Tips:**\n"
        "• Simpan nomor tiket dengan baik\n"
        "• Bisa buat pengaduan berkali-kali\n"
        "• Setiap pengaduan punya nomor unik\n\n"
        "❌ **Batalkan proses kapan saja** dengan klik '❌ Batalkan'",
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard()
    )

async def handle_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle cancel dari button"""
    user_id = update.message.from_user.id
    clear_user_state(user_id)
    
    await update.message.reply_text(
        "❌ **Proses dibatalkan**\n\n"
        "Kembali ke menu utama.",
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard()
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle semua pesan text dengan state management yang lebih baik"""
    user_message = update.message.text.strip()
    user_id = update.message.from_user.id
    
    user_state = get_user_state(user_id)
    logger.info(f"User {user_id} message: {user_message}, state: {user_state}")
    
    # Handle cancel command
    if user_message == "❌ Batalkan":
        await handle_cancel(update, context)
        return
    
    # Handle menu commands ketika tidak dalam state
    if not user_state["mode"]:
        if user_message == "📝 Buat Pengaduan":
            await handle_buat_pengaduan(update, context)
            return
        elif user_message == "🔍 Cek Status":
            await handle_cek_status(update, context)
            return
        elif user_message == "ℹ️ Bantuan":
            await handle_bantuan(update, context)
            return
        else:
            # Jika random text, tetap di menu
            await show_menu(update, context)
            return
    
    mode = user_state["mode"]
    step = user_state.get("step", "")
    
    # PROSES BUAT PENGADUAN
    if mode == "pengaduan":
        await handle_pengaduan_flow(update, context, user_message, user_state)
    
    # PROSES CEK STATUS
    elif mode == "cek_status" and step == "input_tiket":
        await proses_cek_status(update, context, user_message, user_state)
    
    else:
        # Jika state tidak jelas, reset ke menu
        logger.warning(f"Unknown state for user {user_id}: {user_state}")
        clear_user_state(user_id)
        await show_menu(update, context)

async def handle_pengaduan_flow(update: Update, context: ContextTypes.DEFAULT_TYPE, user_message: str, user_state: dict):
    """Handle flow pengaduan yang lebih robust"""
    step = user_state.get("step", "")
    
    if step == "nama":
        user_state["data"]["nama"] = user_message
        user_state["data"]["user_id"] = update.message.from_user.id
        user_state["data"]["username_tg"] = update.message.from_user.username or "-"
        user_state["step"] = "username_jb"
        
        await update.message.reply_text(
            "🆔 **Masukkan Username / ID JokerBola Anda:**\n\n"
            "Ketik ❌ Batalkan untuk membatalkan",
            parse_mode="Markdown",
            reply_markup=cancel_keyboard()
        )
        
    elif step == "username_jb":
        user_state["data"]["username_jb"] = user_message
        user_state["step"] = "keluhan"
        
        await update.message.reply_text(
            "📋 **Jelaskan keluhan Anda:**\n\n"
            "Ketik ❌ Batalkan untuk membatalkan",
            parse_mode="Markdown",
            reply_markup=cancel_keyboard()
        )
        
    elif step == "keluhan":
        user_state["data"]["keluhan"] = user_message
        user_state["step"] = "bukti"
        
        await update.message.reply_text(
            "📸 **Kirim foto bukti (opsional)**\n\n"
            "Kirim foto sekarang atau ketik 'lanjut' untuk melanjutkan tanpa bukti.\n\n"
            "Ketik ❌ Batalkan untuk membatalkan",
            parse_mode="Markdown",
            reply_markup=cancel_keyboard()
        )
        
    elif step == "bukti" and user_message.lower() == "lanjut":
        user_state["data"]["bukti"] = "Tidak ada"
        await selesaikan_pengaduan(update, context, user_state)
        
    elif step == "bukti":
        # Jika di step bukti tapi bukan 'lanjut', minta konfirmasi
        await update.message.reply_text(
            "❌ **Perintah tidak dikenali**\n\n"
            "Untuk melanjutkan tanpa bukti, ketik: **lanjut**\n"
            "Atau kirim foto sebagai bukti.\n\n"
            "Ketik ❌ Batalkan untuk membatalkan",
            parse_mode="Markdown",
            reply_markup=cancel_keyboard()
        )

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle photo untuk bukti"""
    user_id = update.message.from_user.id
    user_state = get_user_state(user_id)
    
    mode = user_state.get("mode")
    step = user_state.get("step")
    
    if mode == "pengaduan" and step == "bukti":
        # Simpan photo
        file_id = update.message.photo[-1].file_id
        file_obj = await context.bot.get_file(file_id)
        user_state["data"]["bukti"] = file_obj.file_path
        
        await update.message.reply_text(
            "Sedang menyimpan pengaduan...",
            parse_mode="Markdown"
        )
        
        await selesaikan_pengaduan(update, context, user_state)
    else:
        await update.message.reply_text(
            "❌ Foto tidak diperlukan saat ini.",
            reply_markup=main_menu_keyboard()
        )

async def selesaikan_pengaduan(update: Update, context: ContextTypes.DEFAULT_TYPE, user_state: dict):
    """Selesaikan pengaduan dan simpan ke Google Sheets"""
    user_id = update.message.from_user.id
    data = user_state["data"]
    timestamp = get_jakarta_time()
    ticket_id = generate_ticket_number()
    
    logger.info(f"Processing new complaint from user {user_id}: {ticket_id}")
    
    try:
        # Save to Google Sheets dengan error handling
        worksheet.append_row([
            timestamp,
            ticket_id,
            data["nama"],
            data["username_jb"],
            data["keluhan"],
            data.get("bukti", "Tidak ada"),
            data["username_tg"],
            data["user_id"],
            "Sedang diproses"
        ])
        logger.info(f"✅ Data saved to Google Sheets: {ticket_id}")
    except Exception as e:
        logger.error(f"❌ Failed to save to Google Sheets: {e}")
        await update.message.reply_text(
            "❌ Maaf, terjadi gangguan sistem. Silakan coba lagi nanti.",
            reply_markup=main_menu_keyboard()
        )
        clear_user_state(user_id)
        return

    # Confirm to user
    await update.message.reply_text(
        f"🎉 **Pengaduan Berhasil Dikirim!**\n\n"
        f"✅ **Terima kasih, {data['nama']}!**\n\n"
        f"**📋 Detail Pengaduan:**\n"
        f"• **Nomor Tiket:** `{ticket_id}`\n"
        f"• **Status:** Sedang diproses\n"
        f"• **Waktu:** {timestamp}\n\n"
        f"**💡 Simpan nomor tiket ini!**\n"
        f"Gunakan menu '🔍 Cek Status' untuk memantau perkembangan pengaduan.\n\n"
        f"**🔄 Ingin buat pengaduan lagi?** Klik '📝 Buat Pengaduan'",
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard()
    )

    # Notify admin dengan retry mechanism
    await kirim_notifikasi_admin_with_retry(context, data, ticket_id, timestamp, user_id)
    
    # Clear user data - BISA BUAT PENGADUAN LAGI
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
            await asyncio.sleep(2)  # Tunggu 2 detik sebelum retry
    
    logger.error(f"❌ All notification attempts failed for ticket {ticket_id}")

async def kirim_notifikasi_admin(context, data, ticket_id, timestamp):
    """Send notification to admin - FIXED VERSION"""
    try:
        # Escape semua data user untuk menghindari Markdown error
        nama_escaped = escape_markdown(data.get("nama", ""))
        username_jb_escaped = escape_markdown(data.get("username_jb", ""))
        keluhan_escaped = escape_markdown(data.get("keluhan", ""))
        username_tg_escaped = escape_markdown(data.get("username_tg", ""))
        user_id_escaped = escape_markdown(data.get("user_id", ""))
        
        bukti_text = data.get("bukti", "Tidak ada")
        if bukti_text != "Tidak ada" and bukti_text.startswith("http"):
            bukti_display = f"[📎 Lihat Bukti]({bukti_text})"
        else:
            bukti_display = escape_markdown(bukti_text)
        
        # Buat message yang sederhana dan aman
        message = (
            f"🚨 *PENGADUAN BARU DITERIMA* 🚨\\n\\n"
            f"🎫 *Ticket ID:* `{ticket_id}`\\n"
            f"⏰ *Waktu:* {timestamp} \\(WIB\\)\\n\\n"
            f"*Data Pelapor:*\\n"
            f"• *Nama:* {nama_escaped}\\n"
            f"• *Username JB:* {username_jb_escaped}\\n"
            f"• *Telegram:* @{username_tg_escaped}\\n"
            f"• *User ID:* `{user_id_escaped}`\\n\\n"
            f"*Keluhan:*\\n{keluhan_escaped}\\n\\n"
            f"*Bukti:* {bukti_display}\\n\\n"
            f"⚠️ *Segera tindak lanjuti pengaduan ini\\!*"
        )
        
        success_count = 0
        for admin_id in ADMIN_IDS:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=message,
                    parse_mode="MarkdownV2",
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
    
    # Validasi format tiket
    if not ticket_id.startswith('JB-'):
        await update.message.reply_text(
            "❌ **Format tiket tidak valid!**\n\n"
            "Format: `JB-TANGGAL-NOMOR`\n"
            "Contoh: `JB-20251219-001`\n\n"
            "Silakan masukkan kembali:",
            parse_mode="Markdown",
            reply_markup=cancel_keyboard()
        )
        return
    
    try:
        # Cari data di Google Sheets
        all_data = worksheet.get_all_records()
        found = False
        user_owns_ticket = False
        
        for row in all_data:
            if row.get('Ticket ID') == ticket_id:
                found = True
                # Cek apakah user ini yang membuat tiket
                ticket_user_id = row.get('User_ID')
                if str(ticket_user_id) == str(current_user_id):
                    user_owns_ticket = True
                    
                    # Format status
                    status = row.get('Status', 'Tidak diketahui')
                    status_emoji = {
                        'Sedang diproses': '🟡',
                        'Selesai': '✅',
                        'Ditolak': '❌',
                        'Menunggu konfirmasi': '🟠'
                    }.get(status, '⚪')
                    
                    # Escape data untuk Markdown
                    nama_escaped = escape_markdown(row.get('Nama', 'Tidak ada'))
                    username_escaped = escape_markdown(row.get('Username', 'Tidak ada'))
                    keluhan_escaped = escape_markdown(row.get('Keluhan', 'Tidak ada'))
                    timestamp_escaped = escape_markdown(row.get('Timestamp', 'Tidak ada'))
                    
                    status_message = (
                        f"📋 **STATUS PENGADUAN**\n\n"
                        f"{status_emoji} **Status:** **{status}**\n"
                        f"🎫 **Ticket ID:** `{ticket_id}`\n"
                        f"👤 **Nama:** {nama_escaped}\n"
                        f"🆔 **Username:** {username_escaped}\n"
                        f"💬 **Keluhan:** {keluhan_escaped}\n"
                        f"⏰ **Waktu:** {timestamp_escaped}\n\n"
                        f"Terima kasih! 🙏"
                    )
                    
                    await update.message.reply_text(
                        status_message,
                        parse_mode="Markdown",
                        reply_markup=main_menu_keyboard()
                    )
                break
        
        if not found or not user_owns_ticket:
            # Tiket tidak ditemukan atau bukan milik user
            await update.message.reply_text(
                "❌ **Tiket tidak ditemukan.**\n\n"
                "Pastikan:\n"
                "• Nomor tiket benar\n"
                "• Format sesuai: JB-TANGGAL-NOMOR\n"
                "• Tidak ada typo\n\n"
                "Klik '🔍 Cek Status' untuk mencoba lagi.",
                parse_mode="Markdown",
                reply_markup=main_menu_keyboard()
            )
            
    except Exception as e:
        logger.error(f"Error checking status: {e}")
        await update.message.reply_text(
            "❌ Terjadi error. Silakan coba lagi.",
            reply_markup=main_menu_keyboard()
        )
    
    # Clear user data - BISA CEK LAGI
    clear_user_state(current_user_id)

async def show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Tampilkan menu utama"""
    await update.message.reply_text(
        "🤖 **Layanan Pengaduan JokerBola**\n\n"
        "Silakan pilih menu:",
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard()
    )

async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel command"""
    user_id = update.message.from_user.id
    clear_user_state(user_id)
    
    await update.message.reply_text(
        "❌ **Semua proses dibatalkan**\n\n"
        "Kembali ke menu utama.",
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard()
    )

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle error"""
    logger.error(f"Error: {context.error}")
    if update and update.message:
        await update.message.reply_text(
            "❌ Terjadi error, silakan coba lagi.",
            reply_markup=main_menu_keyboard()
        )

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
        # Build application
        application = Application.builder().token(BOT_TOKEN).build()
        
        # Command handlers
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("cancel", cancel_command))
        application.add_handler(CommandHandler("help", handle_bantuan))
        
        # Message handlers untuk menu button
        application.add_handler(MessageHandler(filters.Text(["📝 Buat Pengaduan"]), handle_buat_pengaduan))
        application.add_handler(MessageHandler(filters.Text(["🔍 Cek Status"]), handle_cek_status))
        application.add_handler(MessageHandler(filters.Text(["ℹ️ Bantuan"]), handle_bantuan))
        application.add_handler(MessageHandler(filters.Text(["❌ Batalkan"]), handle_cancel))
        
        # Handler untuk photo
        application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
        
        # Handler untuk semua message text (harus di terakhir)
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        
        # Error handler
        application.add_error_handler(error_handler)
        
        # Start bot
        logger.info("✅ Bot starting dengan improved state management...")
        application.run_polling(
            drop_pending_updates=True,
            allowed_updates=Update.ALL_TYPES
        )
        
    except Exception as e:
        logger.error(f"Fatal error: {e}")

if __name__ == '__main__':
    main()
