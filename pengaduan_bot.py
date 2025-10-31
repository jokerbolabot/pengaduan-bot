import os
import json
import gspread
import asyncio
from telegram import Update, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

BOT_TOKEN = os.environ.get("BOT_TOKEN")
GOOGLE_CREDENTIALS_JSON = os.environ.get("GOOGLE_CREDENTIALS")
GOOGLE_SHEET_NAME = "Pengaduan JokerBola"
ADMIN_IDS = [5704050846, 8388423519]

# Setup Google Sheet
gc = gspread.service_account_from_dict(json.loads(GOOGLE_CREDENTIALS_JSON))
sh = gc.open(GOOGLE_SHEET_NAME)
worksheet = sh.sheet1

# Utility
def escape_markdown_v2(text: str) -> str:
    if not text:
        return ""
    escape_chars = r'\_*[]()~`>#+-=|{}.!'
    return ''.join(f'\\{c}' if c in escape_chars else c for c in text)

async def kirim_notif_admin(pesan: str, bot):
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(chat_id=admin_id, text=pesan, parse_mode="MarkdownV2")
        except Exception as e:
            print(f"Gagal kirim ke admin {admin_id}: {e}")

def simpan_ke_sheet(username_tg: str, pesan: str, link_gambar: str):
    try:
        username_link = f"t.me/{username_tg}" if username_tg else f"user_{username_tg}"
        worksheet.append_row([username_link, pesan, link_gambar])
        print(f"✅ Data tersimpan: {username_link}")
    except Exception as e:
        print(f"❌ Gagal simpan ke sheet: {e}")

# Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 Bot Pengaduan Aktif!\n\n"
        "Kirim pengaduan atau bukti screenshot Anda.\n"
        "Gunakan /cek untuk mengecek status bot.",
        reply_markup=ReplyKeyboardRemove()
    )

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Perintah dibatalkan.", reply_markup=ReplyKeyboardRemove())

async def cek(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Bot online dan siap menerima pengaduan!")

async def handle_pengaduan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user = update.message.from_user
        username = user.username or str(user.id)
        pesan = update.message.text or ""
        
        # Handle photo
        link_gambar = "-"
        if update.message.photo:
            file_id = update.message.photo[-1].file_id
            file_obj = await context.bot.get_file(file_id)
            link_gambar = file_obj.file_path
            print(f"📸 Gambar diterima: {link_gambar}")

        # Simpan ke Google Sheets
        pesan_escaped = escape_markdown_v2(pesan)
        simpan_ke_sheet(username, pesan_escaped, link_gambar)

        # Kirim notifikasi ke admin
        notif = (
            f"📩 *PENGADUAN BARU*\n\n"
            f"👤 Username: `{escape_markdown_v2(str(username))}`\n"
            f"📝 Pesan: {pesan_escaped}\n"
            f"🖼️ Gambar: {escape_markdown_v2(link_gambar)}"
        )
        await kirim_notif_admin(notif, context.bot)
        
        # Konfirmasi ke user
        await update.message.reply_text(
            "✅ Terima kasih! Pengaduan Anda sudah diterima dan akan segera kami proses."
        )
        
    except Exception as e:
        print(f"❌ Error di handle_pengaduan: {e}")
        await update.message.reply_text("❌ Maaf, terjadi error. Silakan coba lagi.")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f"🚨 Error: {context.error}")
    if update and update.message:
        await update.message.reply_text("❌ Terjadi error, silakan coba lagi.")

async def post_init(application: Application):
    print("✅ Bot berhasil diinisialisasi!")
    await kirim_notif_admin("🤖 Bot Pengaduan telah dijalankan!", application.bot)

def main():
    print("🚀 Starting Telegram Bot...")
    
    # Validasi environment variables
    if not BOT_TOKEN:
        print("❌ ERROR: BOT_TOKEN tidak ditemukan!")
        return
    
    if not GOOGLE_CREDENTIALS_JSON:
        print("❌ ERROR: GOOGLE_CREDENTIALS tidak ditemukan!")
        return

    try:
        # Build application
        application = Application.builder().token(BOT_TOKEN).post_init(post_init).build()
        
        # Add handlers
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("cancel", cancel))
        application.add_handler(CommandHandler("cek", cek))
        application.add_handler(MessageHandler(filters.TEXT | filters.PHOTO, handle_pengaduan))
        
        # Error handler
        application.add_error_handler(error_handler)
        
        print("✅ Bot berjalan...")
        print("📡 Starting polling...")
        
        # Run bot dengan error handling
        application.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True
        )
        
    except Exception as e:
        print(f"❌ Fatal error: {e}")

if __name__ == "__main__":
    main()
