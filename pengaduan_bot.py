import os
import json
import gspread
from telegram import Update, ReplyKeyboardRemove
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

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
    escape_chars = r'\_*[]()~`>#+-=|{}.!'
    return ''.join(f'\\{c}' if c in escape_chars else c for c in text)

async def kirim_notif_admin(pesan: str, application):
    for admin_id in ADMIN_IDS:
        try:
            await application.bot.send_message(chat_id=admin_id, text=pesan, parse_mode="MarkdownV2")
        except Exception as e:
            print(f"Gagal kirim ke admin {admin_id}: {e}")

async def simpan_ke_sheet(username_tg: str, pesan: str, link_gambar: str):
    username_link = f"t.me/{username_tg}"
    worksheet.append_row([username_link, pesan, link_gambar])

# Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot aktif. Kirim pengaduan atau bukti.", reply_markup=ReplyKeyboardRemove())

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Perintah dibatalkan.", reply_markup=ReplyKeyboardRemove())

async def cek(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot online dan siap menerima pengaduan.")

async def pengaduan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    username = user.username or str(user.id)
    pesan = update.message.text or ""
    
    link_gambar = "-"
    if update.message.photo:
        file_id = update.message.photo[-1].file_id
        file_obj = await context.bot.get_file(file_id)
        link_gambar = file_obj.file_path

    pesan_escaped = escape_markdown_v2(pesan)
    await simpan_ke_sheet(username, pesan_escaped, link_gambar)

    notif = f"📩 *Pengaduan baru*\nUsername: `{escape_markdown_v2(str(username))}`\nPesan: {pesan_escaped}\nLink gambar: {escape_markdown_v2(link_gambar)}"
    await kirim_notif_admin(notif, context.application)
    await update.message.reply_text("✅ Terima kasih! Pengaduanmu sudah diterima.")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f"Error: {context.error}")

def main():
    if not BOT_TOKEN:
        print("ERROR: BOT_TOKEN tidak ditemukan!")
        return
    
    if not GOOGLE_CREDENTIALS_JSON:
        print("ERROR: GOOGLE_CREDENTIALS tidak ditemukan!")
        return

    try:
        application = ApplicationBuilder().token(BOT_TOKEN).build()
        
        # Add handlers
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("cancel", cancel))
        application.add_handler(CommandHandler("cek", cek))
        application.add_handler(MessageHandler(filters.TEXT | filters.PHOTO, pengaduan))
        
        # Error handler
        application.add_error_handler(error_handler)
        
        print("✅ Bot berjalan...")
        
        # Run bot
        application.run_polling()
        
    except Exception as e:
        print(f"❌ Error starting bot: {e}")

if __name__ == "__main__":
    main()
