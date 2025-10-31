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

# --- Setup Logging ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# --- Konfigurasi ---
BOT_TOKEN = os.environ.get("BOT_TOKEN")
GOOGLE_CREDENTIALS_JSON = os.environ.get("GOOGLE_CREDENTIALS")
GOOGLE_SHEET_NAME = "Pengaduan JokerBola"
ADMIN_IDS = [5704050846, 8388423519]

# --- Tahapan Conversation ---
NAMA, USERNAME, KELUHAN, BUKTI = range(4)

# --- Setup Google Sheets ---
gc = gspread.service_account_from_dict(json.loads(GOOGLE_CREDENTIALS_JSON))
sh = gc.open(GOOGLE_SHEET_NAME)
worksheet = sh.sheet1

# --- Fungsi Generate Ticket ID ---
def generate_ticket_number():
    try:
        all_data = worksheet.get_all_records()
        today = datetime.now().strftime("%Y%m%d")
        count_today = 0
        
        for row in all_data:
            timestamp = row.get('Timestamp', '')
            if isinstance(timestamp, str) and timestamp.startswith(datetime.now().strftime("%Y-%m-%d")):
                count_today += 1
        
        return f"JB-{today}-{count_today+1:03d}"
    except Exception as e:
        logging.error(f"Error generating ticket: {e}")
        return f"JB-{datetime.now().strftime('%Y%m%d')}-001"

# --- Utility: Escape MarkdownV2 ---
def escape_markdown(text: str) -> str:
    if not text:
        return ""
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    return ''.join(f'\\{char}' if char in escape_chars else char for char in text)

# --- Menu Keyboard ---
def main_menu_keyboard():
    return ReplyKeyboardMarkup([
        ['/start', '/cek'],
        ['/cancel', '/help']
    ], resize_keyboard=True, one_time_keyboard=True)

# --- Webhook Disable ---
async def disable_webhook(application: Application):
    """Disable webhook untuk memastikan polling saja"""
    await application.bot.delete_webhook(drop_pending_updates=True)
    logging.info("✅ Webhook disabled, using polling only")

# --- Handlers (sama seperti sebelumnya) ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "👋 Halo\\! Selamat datang di *Layanan Pengaduan JokerBola*\n\n"
        "Silakan isi data berikut untuk melaporkan keluhan Anda\\.\n\n"
        "📝 *Nama lengkap:*",
        parse_mode="MarkdownV2",
        reply_markup=ReplyKeyboardRemove()
    )
    return NAMA

async def nama(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["nama"] = update.message.text
    context.user_data["user_id"] = update.message.from_user.id
    context.user_data["username_tg"] = update.message.from_user.username or "-"
    
    await update.message.reply_text(
        "🆔 *Masukkan ID / Username akun JokerBola Anda:*",
        parse_mode="MarkdownV2"
    )
    return USERNAME

async def username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["username_jb"] = update.message.text
    await update.message.reply_text(
        "📋 *Jelaskan keluhan Anda:*",
        parse_mode="MarkdownV2"
    )
    return KELUHAN

async def keluhan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["keluhan"] = update.message.text
    await update.message.reply_text(
        "📸 *Kirimkan foto bukti \\(opsional\\)*\n\n"
        "Jika tidak ada bukti, ketik: `skip`",
        parse_mode="MarkdownV2"
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
    
    nama_escaped = escape_markdown(data["nama"])
    username_jb_escaped = escape_markdown(data["username_jb"])
    keluhan_escaped = escape_markdown(data["keluhan"])
    
    try:
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
        logging.info(f"Data berhasil disimpan: {ticket_id}")
    except Exception as e:
        logging.error(f"Gagal menyimpan ke Google Sheets: {e}")
        await update.message.reply_text(
            "❌ Maaf, terjadi gangguan sistem\\. Silakan coba lagi nanti\\.",
            parse_mode="MarkdownV2",
            reply_markup=main_menu_keyboard()
        )
        return

    await update.message.reply_text(
        f"✅ *Terima kasih, {nama_escaped}\\!*\n\n"
        f"Laporan Anda telah diterima\\.\n\n"
        f"*Nomor tiket:* `{ticket_id}`\n"
        f"*Status:* Sedang diproses\n\n"
        f"Gunakan perintah `/cek {ticket_id}` untuk memantau status laporan Anda\\.",
        parse_mode="MarkdownV2",
        reply_markup=main_menu_keyboard()
    )

    await kirim_notifikasi_admin(context, data, ticket_id, timestamp)

async def kirim_notifikasi_admin(context, data, ticket_id, timestamp):
    bukti_text = f"[Lihat Bukti]({data['bukti']})" if data["bukti"] != "Tidak ada" else "Tidak ada"
    
    nama_escaped = escape_markdown(data["nama"])
    username_jb_escaped = escape_markdown(data["username_jb"])
    keluhan_escaped = escape_markdown(data["keluhan"])
    
    message = (
        f"📩 *PENGADUAN BARU*\n\n"
        f"🎫 *Ticket ID:* `{ticket_id}`\n"
        f"⏰ *Waktu:* {timestamp}\n\n"
        f"👤 *Nama:* {nama_escaped}\n"
        f"🆔 *Username JB:* {username_jb_escaped}\n"
        f"💬 *Keluhan:* {keluhan_escaped}\n"
        f"📎 *Bukti:* {bukti_text}\n"
        f"🔗 *Telegram:* @{data['username_tg']}\n"
        f"🆔 *User ID:* `{data['user_id']}`"
    )
    
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=message,
                parse_mode="MarkdownV2"
            )
        except Exception as e:
            logging.error(f"Gagal kirim notifikasi ke admin {admin_id}: {e}")

async def cek_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "❗ *Format:* `/cek nomor_tiket`\n"
            "*Contoh:* `/cek JB\\-20241219\\-001`\n\n"
            "Atau klik menu di bawah untuk memulai pengaduan baru:",
            parse_mode="MarkdownV2",
            reply_markup=main_menu_keyboard()
        )
        return
    
    ticket_id = context.args[0].strip()
    
    try:
        all_data = worksheet.get_all_records()
        found = False
        
        for row in all_data:
            if row.get('Ticket ID') == ticket_id:
                found = True
                nama_escaped = escape_markdown(str(row.get('Nama', '')))
                username_escaped = escape_markdown(str(row.get('Username', '')))
                keluhan_escaped = escape_markdown(str(row.get('Keluhan', '')))
                status_escaped = escape_markdown(str(row.get('Status', '')))
                timestamp_escaped = escape_markdown(str(row.get('Timestamp', '')))
                
                status_message = (
                    f"📋 *STATUS PENGADUAN*\n\n"
                    f"🎫 *Ticket ID:* `{ticket_id}`\n"
                    f"👤 *Nama:* {nama_escaped}\n"
                    f"🆔 *Username:* {username_escaped}\n"
                    f"💬 *Keluhan:* {keluhan_escaped}\n"
                    f"⏰ *Waktu:* {timestamp_escaped}\n"
                    f"📊 *Status:* *{status_escaped}*"
                )
                await update.message.reply_text(
                    status_message,
                    parse_mode="MarkdownV2",
                    reply_markup=main_menu_keyboard()
                )
                break
        
        if not found:
            await update.message.reply_text(
                "❌ *Tiket tidak ditemukan*\\.\nPastikan nomor tiket benar\\.",
                parse_mode="MarkdownV2",
                reply_markup=main_menu_keyboard()
            )
            
    except Exception as e:
        logging.error(f"Error cek status: {e}")
        await update.message.reply_text(
            "❌ *Terjadi error saat mencari tiket*\\. Silakan coba lagi\\.",
            parse_mode="MarkdownV2",
            reply_markup=main_menu_keyboard()
        )

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "❌ Pengaduan dibatalkan\\.\n\n"
        "Klik /start untuk memulai pengaduan baru\\.",
        reply_markup=main_menu_keyboard(),
        parse_mode="MarkdownV2"
    )
    return ConversationHandler.END

async def show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 *Selamat datang di Layanan Pengaduan JokerBola*\n\n"
        "📋 *Menu Perintah:*\n"
        "└ /start \\- Mulai pengaduan baru\n"
        "└ /cek \\- Cek status tiket\n"
        "└ /cancel \\- Batalkan pengaduan\n"
        "└ /help \\- Bantuan penggunaan\n\n"
        "Silakan pilih menu di bawah atau ketik perintah yang diinginkan:",
        parse_mode="MarkdownV2",
        reply_markup=main_menu_keyboard()
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🆘 *Bantuan Penggunaan Bot*\n\n"
        "📝 *Cara membuat pengaduan:*\n"
        "1\\. Ketik /start\n"
        "2\\. Isi nama lengkap\n"
        "3\\. Isi username JokerBola\n"
        "4\\. Jelaskan keluhan\n"
        "5\\. Kirim bukti \\(opsional\\)\n\n"
        "🔍 *Cek status tiket:*\n"
        "└ /cek JB\\-20241219\\-001\n\n"
        "❌ *Batalkan pengaduan:*\n"
        "└ /cancel",
        parse_mode="MarkdownV2",
        reply_markup=main_menu_keyboard()
    )

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logging.error(f"Error: {context.error}")
    if update and update.message:
        await update.message.reply_text(
            "❌ Terjadi error, silakan coba lagi\\.\n\n"
            "Gunakan menu di bawah untuk melanjutkan:",
            parse_mode="MarkdownV2",
            reply_markup=main_menu_keyboard()
        )

def main():
    if not BOT_TOKEN:
        logging.error("BOT_TOKEN tidak ditemukan!")
        return
    
    if not GOOGLE_CREDENTIALS_JSON:
        logging.error("GOOGLE_CREDENTIALS tidak ditemukan!")
        return

    try:
        # Build application dengan webhook disabled
        application = (
            Application.builder()
            .token(BOT_TOKEN)
            .post_init(disable_webhook)
            .build()
        )
        
        # Conversation handler
        conv_handler = ConversationHandler(
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

        # Add handlers
        application.add_handler(conv_handler)
        application.add_handler(CommandHandler('cek', cek_status))
        application.add_handler(CommandHandler('cancel', cancel))
        application.add_handler(CommandHandler('help', help_command))
        application.add_handler(CommandHandler('start', show_menu))
        
        application.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND & ~filters.Regex(r'^(skip|Skip|SKIP)$'), 
            show_menu
        ))
        
        application.add_error_handler(error_handler)
        
        logging.info("✅ Bot berjalan...")
        application.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True
        )
        
    except Exception as e:
        logging.error(f"Fatal error: {e}")

if __name__ == '__main__':
    main()
