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

# Conversation states
NAMA, USERNAME, KELUHAN, BUKTI, CEK_TIKET = range(5)

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
        ['/start', '/cek'],
        ['/help']
    ], resize_keyboard=True)

# ===== PENGADUAN HANDLERS =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "👋 Halo! Selamat datang di Layanan Pengaduan JokerBola\n\n"
        "Silakan isi data berikut untuk melaporkan keluhan Anda.\n\n"
        "📝 **Nama lengkap:**",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove()
    )
    return NAMA

async def nama(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["nama"] = update.message.text
    context.user_data["user_id"] = update.message.from_user.id
    context.user_data["username_tg"] = update.message.from_user.username or "-"
    
    await update.message.reply_text(
        "🆔 **Masukkan ID / Username akun JokerBola Anda:**",
        parse_mode="Markdown"
    )
    return USERNAME

async def username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["username_jb"] = update.message.text
    await update.message.reply_text(
        "📋 **Jelaskan keluhan Anda:**",
        parse_mode="Markdown"
    )
    return KELUHAN

async def keluhan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["keluhan"] = update.message.text
    await update.message.reply_text(
        "📸 **Kirimkan foto bukti (opsional)**\n\n"
        "Jika tidak ada bukti, ketik: skip",
        parse_mode="Markdown"
    )
    return BUKTI

async def bukti(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.photo:
        file_id = update.message.photo[-1].file_id
        file_obj = await context.bot.get_file(file_id)
        context.user_data["bukti"] = file_obj.file_path
    else:
        context.user_data["bukti"] = "Tidak ada"
    
    await selesaikan_pengaduan(update, context)
    return ConversationHandler.END

async def skip_bukti(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["bukti"] = "Tidak ada"
    await selesaikan_pengaduan(update, context)
    return ConversationHandler.END

async def selesaikan_pengaduan(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
            data["bukti"],
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
        return

    # Confirm to user
    await update.message.reply_text(
        f"✅ **Terima kasih, {data['nama']}!**\n\n"
        f"Laporan Anda telah diterima.\n\n"
        f"**Nomor tiket:** `{ticket_id}`\n"
        f"**Status:** Sedang diproses\n\n"
        f"**Simpan nomor tiket ini untuk pengecekan status!**\n"
        f"Gunakan perintah /cek untuk memantau status laporan Anda.",
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard()
    )

    # Notify admin
    await kirim_notifikasi_admin(context, data, ticket_id, timestamp)

async def kirim_notifikasi_admin(context, data, ticket_id, timestamp):
    """Send notification to admin"""
    try:
        bukti_text = data["bukti"] if data["bukti"] != "Tidak ada" else "Tidak ada"
        
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
        
        success_count = 0
        for admin_id in ADMIN_IDS:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=message,
                    parse_mode="Markdown"
                )
                success_count += 1
                logger.info(f"Notification sent to admin {admin_id}")
            except Exception as e:
                logger.error(f"Failed to send to admin {admin_id}: {e}")
        
        logger.info(f"Notifications sent to {success_count}/{len(ADMIN_IDS)} admins")
        
    except Exception as e:
        logger.error(f"Error in kirim_notifikasi_admin: {e}")

# ===== CEK STATUS HANDLERS =====
async def cek_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Memulai proses pengecekan tiket"""
    await update.message.reply_text(
        "🔍 **Pengecekan Status Tiket**\n\n"
        "Silakan masukkan **nomor tiket** Anda:\n"
        "Contoh: `JB-20241219-001`\n\n"
        "Ketik /cancel untuk membatalkan",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove()
    )
    return CEK_TIKET

async def cek_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Memproses pengecekan tiket dengan validasi kepemilikan"""
    ticket_id = update.message.text.strip()
    current_user_id = update.message.from_user.id
    
    # Validasi format tiket
    if not ticket_id.startswith('JB-'):
        await update.message.reply_text(
            "❌ **Format tiket tidak valid!**\n\n"
            "Format tiket harus: `JB-TANGGAL-NOMOR`\n"
            "Contoh: `JB-20241219-001`\n\n"
            "Silakan masukkan kembali nomor tiket Anda:",
            parse_mode="Markdown"
        )
        return CEK_TIKET
    
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
                    
                    # Format status dengan emoji
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
                        f"Terima kasih telah menggunakan layanan kami! 🙏"
                    )
                    
                    await update.message.reply_text(
                        status_message,
                        parse_mode="Markdown",
                        reply_markup=main_menu_keyboard()
                    )
                break
        
        if not found:
            # Tiket tidak ditemukan di database
            await update.message.reply_text(
                "❌ **Tiket tidak ditemukan.**\n\n"
                "Pastikan:\n"
                "• Nomor tiket benar\n"
                "• Format sesuai: `JB-TANGGAL-NOMOR`\n"
                "• Tidak ada typo\n\n"
                "Silakan masukkan kembali nomor tiket Anda:",
                parse_mode="Markdown"
            )
            return CEK_TIKET
        elif found and not user_owns_ticket:
            # Tiket ditemukan tapi bukan milik user ini
            await update.message.reply_text(
                "❌ **Tiket tidak ditemukan.**\n\n"
                "Pastikan:\n"
                "• Nomor tiket benar\n"
                "• Format sesuai: `JB-TANGGAL-NOMOR`\n"
                "• Tidak ada typo\n\n"
                "Silakan masukkan kembali nomor tiket Anda:",
                parse_mode="Markdown"
            )
            return CEK_TIKET
            
    except Exception as e:
        logger.error(f"Error checking status: {e}")
        await update.message.reply_text(
            "❌ **Terjadi error saat mencari tiket.**\n\n"
            "Silakan coba lagi atau hubungi admin.\n\n"
            "Masukkan kembali nomor tiket Anda:",
            parse_mode="Markdown"
        )
        return CEK_TIKET
    
    return ConversationHandler.END

async def cek_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Membatalkan pengecekan tiket"""
    await update.message.reply_text(
        "❌ Pengecekan tiket dibatalkan.\n\n"
        "Klik /cek untuk memulai pengecekan lagi.",
        reply_markup=main_menu_keyboard()
    )
    return ConversationHandler.END

# ===== OTHER HANDLERS =====
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "❌ Pengaduan dibatalkan.\n\nKlik /start untuk memulai pengaduan baru.",
        reply_markup=main_menu_keyboard()
    )
    return ConversationHandler.END

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🆘 **Bantuan Penggunaan Bot**\n\n"
        "📝 **Cara membuat pengaduan:**\n"
        "1. Ketik /start\n"
        "2. Isi nama lengkap\n"
        "3. Isi username JokerBola\n"
        "4. Jelaskan keluhan\n"
        "5. Kirim bukti (opsional)\n\n"
        "🔍 **Cek status tiket:**\n"
        "1. Ketik /cek\n"
        "2. Masukkan nomor tiket\n"
        "3. Lihat status pengaduan\n\n"
        "💡 **Tips:**\n"
        "• Simpan nomor tiket yang diberikan\n"
        "• Hanya pemilik tiket yang bisa cek status\n"
        "• Status update real-time\n\n"
        "❌ **Batalkan proses:**\n"
        "/cancel - Batalkan pengaduan/pengecekan",
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard()
    )

async def show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 **Selamat datang di Layanan Pengaduan JokerBola**\n\n"
        "📋 **Menu Perintah:**\n"
        "• /start - Mulai pengaduan baru\n"
        "• /cek - Cek status tiket\n"
        "• /help - Bantuan penggunaan\n\n"
        "Silakan pilih menu di bawah:",
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard()
    )

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Error: {context.error}")
    if update and update.message:
        await update.message.reply_text(
            "❌ Terjadi error, silakan coba lagi.",
            reply_markup=main_menu_keyboard()
        )

def main():
    # Validate environment variables
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
        
        # Conversation handler untuk PENGADUAN
        pengaduan_conv_handler = ConversationHandler(
            entry_points=[CommandHandler('start', start)],
            states={
                NAMA: [MessageHandler(filters.TEXT & ~filters.COMMAND, nama)],
                USERNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, username)],
                KELUHAN: [MessageHandler(filters.TEXT & ~filters.COMMAND, keluhan)],
                BUKTI: [
                    MessageHandler(filters.PHOTO, bukti),
                    MessageHandler(filters.TEXT & filters.Regex(r'^(skip|Skip|SKIP)$'), skip_bukti),
                ],
            },
            fallbacks=[CommandHandler('cancel', cancel)],
        )
        
        # Conversation handler untuk CEK STATUS
        cek_conv_handler = ConversationHandler(
            entry_points=[CommandHandler('cek', cek_start)],
            states={
                CEK_TIKET: [MessageHandler(filters.TEXT & ~filters.COMMAND, cek_process)],
            },
            fallbacks=[CommandHandler('cancel', cek_cancel)],
        )

        # Add handlers
        application.add_handler(pengaduan_conv_handler)
        application.add_handler(cek_conv_handler)
        application.add_handler(CommandHandler('help', help_command))
        application.add_handler(CommandHandler('start', show_menu))
        
        # Handler for messages outside conversation
        application.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND & ~filters.Regex(r'^(skip|Skip|SKIP)$'), 
            show_menu
        ))
        
        # Error handler
        application.add_error_handler(error_handler)
        
        # Start bot
        logger.info("✅ Bot starting...")
        application.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True
        )
        
    except Exception as e:
        logger.error(f"Fatal error: {e}")

if __name__ == '__main__':
    main()
