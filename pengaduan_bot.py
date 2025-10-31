import os
import json
import gspread
import logging
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application, CommandHandler, MessageHandler, ContextTypes,
    filters, ConversationHandler
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
def generate_ticket_number():
    try:
        all_data = worksheet.get_all_records()
        today = datetime.now().strftime("%Y%m%d")
        count_today = sum(1 for row in all_data if str(row.get('Timestamp', '')).startswith(datetime.now().strftime("%Y-%m-%d")))
        return f"JB-{today}-{count_today+1:03d}"
    except Exception as e:
        logger.error(f"Error generating ticket: {e}")
        return f"JB-{datetime.now().strftime('%Y%m%d')}-001"

def main_menu_keyboard():
    return ReplyKeyboardMarkup([
        ['Buat Pengaduan', 'Cek Status'],
        ['Bantuan']
    ], resize_keyboard=True)

# ===== SIMPLE HANDLERS (TANPA CONVERSATION COMPLEX) =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command dengan menu sederhana"""
    await update.message.reply_text(
        "🤖 **Selamat datang di Layanan Pengaduan JokerBola**\n\n"
        "Silakan pilih menu di bawah:",
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard()
    )

async def handle_buat_pengaduan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Memulai pengaduan baru - SIMPLE VERSION"""
    context.user_data.clear()
    context.user_data["waiting_for"] = "nama"
    
    await update.message.reply_text(
        "👋 **Membuat Pengaduan Baru**\n\n"
        "Silakan kirim **Nama Lengkap** Anda:",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove()
    )

async def handle_cek_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cek status tiket - SIMPLE VERSION"""
    context.user_data["waiting_for"] = "cek_tiket"
    
    await update.message.reply_text(
        "🔍 **Cek Status Tiket**\n\n"
        "Silakan kirim **Nomor Tiket** Anda:\n"
        "Contoh: JB-20241219-001",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove()
    )

async def handle_bantuan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menu bantuan"""
    await update.message.reply_text(
        "🆘 **Bantuan Penggunaan**\n\n"
        "📝 **Cara Buat Pengaduan:**\n"
        "1. Klik 'Buat Pengaduan'\n"
        "2. Isi nama lengkap\n"
        "3. Isi username JokerBola\n"
        "4. Jelaskan keluhan\n"
        "5. Kirim bukti (opsional)\n\n"
        "🔍 **Cek Status:**\n"
        "1. Klik 'Cek Status'\n"
        "2. Masukkan nomor tiket\n\n"
        "❓ **Butuh bantuan lebih?** Hubungi Admin.",
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard()
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle semua pesan text"""
    user_message = update.message.text
    waiting_for = context.user_data.get("waiting_for")
    
    # Jika tidak dalam proses apapun, tampilkan menu
    if not waiting_for:
        await show_menu(update, context)
        return
    
    # PROSES BUAT PENGADUAN
    if waiting_for == "nama":
        context.user_data["nama"] = user_message
        context.user_data["user_id"] = update.message.from_user.id
        context.user_data["username_tg"] = update.message.from_user.username or "-"
        context.user_data["waiting_for"] = "username_jb"
        
        await update.message.reply_text(
            "🆔 **Masukkan Username / ID JokerBola Anda:**",
            parse_mode="Markdown"
        )
        
    elif waiting_for == "username_jb":
        context.user_data["username_jb"] = user_message
        context.user_data["waiting_for"] = "keluhan"
        
        await update.message.reply_text(
            "📋 **Jelaskan keluhan Anda:**",
            parse_mode="Markdown"
        )
        
    elif waiting_for == "keluhan":
        context.user_data["keluhan"] = user_message
        context.user_data["waiting_for"] = "bukti"
        
        await update.message.reply_text(
            "📸 **Kirim foto bukti (opsional)**\n\n"
            "Kirim foto sekarang atau ketik 'lanjut' untuk melanjutkan tanpa bukti:",
            parse_mode="Markdown"
        )
        
    elif waiting_for == "bukti" and user_message.lower() == "lanjut":
        context.user_data["bukti"] = "Tidak ada"
        await selesaikan_pengaduan(update, context)
        
    # PROSES CEK STATUS
    elif waiting_for == "cek_tiket":
        await proses_cek_status(update, context, user_message)
        
    else:
        # Jika tidak ada yang match, reset ke menu
        context.user_data.clear()
        await show_menu(update, context)

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle photo untuk bukti"""
    waiting_for = context.user_data.get("waiting_for")
    
    if waiting_for == "bukti":
        # Simpan photo
        file_id = update.message.photo[-1].file_id
        file_obj = await context.bot.get_file(file_id)
        context.user_data["bukti"] = file_obj.file_path
        
        await selesaikan_pengaduan(update, context)
    else:
        await update.message.reply_text(
            "❌ Foto tidak diperlukan saat ini.",
            reply_markup=main_menu_keyboard()
        )

async def selesaikan_pengaduan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Selesaikan pengaduan dan simpan ke Google Sheets"""
    data = context.user_data
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ticket_id = generate_ticket_number()
    
    logger.info(f"Processing new complaint: {ticket_id}")
    
    try:
        # Save to Google Sheets
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
        logger.info(f"Data saved to Google Sheets: {ticket_id}")
    except Exception as e:
        logger.error(f"Failed to save to Google Sheets: {e}")
        await update.message.reply_text(
            "❌ Maaf, terjadi gangguan sistem. Silakan coba lagi nanti.",
            reply_markup=main_menu_keyboard()
        )
        context.user_data.clear()
        return

    # Confirm to user
    await update.message.reply_text(
        f"✅ **Terima kasih, {data['nama']}!**\n\n"
        f"Laporan Anda telah diterima.\n\n"
        f"**Nomor Tiket:** `{ticket_id}`\n"
        f"**Status:** Sedang diproses\n\n"
        f"**Simpan nomor tiket ini!**\n"
        f"Gunakan menu 'Cek Status' untuk memantau perkembangan.",
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard()
    )

    # Notify admin
    await kirim_notifikasi_admin(context, data, ticket_id, timestamp)
    
    # Clear user data
    context.user_data.clear()

async def proses_cek_status(update: Update, context: ContextTypes.DEFAULT_TYPE, ticket_id: str):
    """Proses cek status tiket"""
    current_user_id = update.message.from_user.id
    
    # Validasi format tiket
    if not ticket_id.startswith('JB-'):
        await update.message.reply_text(
            "❌ **Format tiket tidak valid!**\n\n"
            "Format: `JB-TANGGAL-NOMOR`\n"
            "Contoh: `JB-20241219-001`\n\n"
            "Silakan masukkan kembali:",
            parse_mode="Markdown"
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
                    
                    status_message = (
                        f"📋 **STATUS PENGADUAN**\n\n"
                        f"{status_emoji} **Status:** **{status}**\n"
                        f"🎫 **Ticket ID:** `{ticket_id}`\n"
                        f"👤 **Nama:** {row.get('Nama', 'Tidak ada')}\n"
                        f"🆔 **Username:** {row.get('Username', 'Tidak ada')}\n"
                        f"💬 **Keluhan:** {row.get('Keluhan', 'Tidak ada')}\n"
                        f"⏰ **Waktu:** {row.get('Timestamp', 'Tidak ada')}\n\n"
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
                "• Format sesuai\n"
                "• Tidak ada typo\n\n"
                "Klik 'Cek Status' untuk mencoba lagi.",
                parse_mode="Markdown",
                reply_markup=main_menu_keyboard()
            )
            
    except Exception as e:
        logger.error(f"Error checking status: {e}")
        await update.message.reply_text(
            "❌ Terjadi error. Silakan coba lagi.",
            reply_markup=main_menu_keyboard()
        )
    
    # Clear user data
    context.user_data.clear()

async def kirim_notifikasi_admin(context, data, ticket_id, timestamp):
    """Send notification to admin"""
    try:
        bukti_text = data.get("bukti", "Tidak ada")
        
        message = (
            f"📩 **PENGADUAN BARU**\n\n"
            f"🎫 **Ticket ID:** {ticket_id}\n"
            f"⏰ **Waktu:** {timestamp}\n\n"
            f"👤 **Nama:** {data['nama']}\n"
            f"🆔 **Username JB:** {data['username_jb']}\n"
            f"💬 **Keluhan:** {data['keluhan']}\n"
            f"📎 **Bukti:** {bukti_text}\n"
            f"🔗 **Telegram:** @{data['username_tg']}\n"
            f"🆔 **User ID:** {data['user_id']}"
        )
        
        for admin_id in ADMIN_IDS:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=message,
                    parse_mode="Markdown"
                )
                logger.info(f"Notification sent to admin {admin_id}")
            except Exception as e:
                logger.error(f"Failed to send to admin {admin_id}: {e}")
        
    except Exception as e:
        logger.error(f"Error in kirim_notifikasi_admin: {e}")

async def show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Tampilkan menu utama"""
    await update.message.reply_text(
        "🤖 **Layanan Pengaduan JokerBola**\n\n"
        "Silakan pilih menu:",
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard()
    )

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel command"""
    context.user_data.clear()
    await update.message.reply_text(
        "❌ Proses dibatalkan.",
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
        application.add_handler(CommandHandler("cancel", cancel))
        application.add_handler(CommandHandler("help", handle_bantuan))
        
        # Message handlers untuk menu
        application.add_handler(MessageHandler(filters.Text(["Buat Pengaduan"]), handle_buat_pengaduan))
        application.add_handler(MessageHandler(filters.Text(["Cek Status"]), handle_cek_status))
        application.add_handler(MessageHandler(filters.Text(["Bantuan"]), handle_bantuan))
        
        # Handler untuk photo
        application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
        
        # Handler untuk semua message text (harus di terakhir)
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        
        # Error handler
        application.add_error_handler(error_handler)
        
        # Start bot
        logger.info("✅ Bot starting...")
        application.run_polling(drop_pending_updates=True)
        
    except Exception as e:
        logger.error(f"Fatal error: {e}")

if __name__ == '__main__':
    main()
