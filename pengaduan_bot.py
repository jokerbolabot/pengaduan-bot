import os
import json
import gspread
from telegram import Update, ReplyKeyboardRemove
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext

BOT_TOKEN = os.environ.get("BOT_TOKEN")
GOOGLE_CREDENTIALS_JSON = os.environ.get("GOOGLE_CREDENTIALS")
GOOGLE_SHEET_NAME = "Pengaduan JokerBola"
ADMIN_IDS = [5704050846]

# Setup Google Sheet
gc = gspread.service_account_from_dict(json.loads(GOOGLE_CREDENTIALS_JSON))
sh = gc.open(GOOGLE_SHEET_NAME)
worksheet = sh.sheet1

# Utility
def escape_markdown_v2(text: str) -> str:
    escape_chars = r'\_*[]()~`>#+-=|{}.!'
    return ''.join(f'\\{c}' if c in escape_chars else c for c in text)

def kirim_notif_admin(pesan: str, context: CallbackContext):
    for admin_id in ADMIN_IDS:
        try:
            context.bot.send_message(chat_id=admin_id, text=pesan, parse_mode="MarkdownV2")
        except Exception as e:
            print(f"Gagal kirim ke admin {admin_id}: {e}")

def simpan_ke_sheet(username_tg: str, pesan: str, link_gambar: str):
    username_link = f"t.me/{username_tg}"
    worksheet.append_row([username_link, pesan, link_gambar])

# Handlers
def start(update: Update, context: CallbackContext):
    update.message.reply_text("Bot aktif. Kirim pengaduan atau bukti.", reply_markup=ReplyKeyboardRemove())

def cancel(update: Update, context: CallbackContext):
    update.message.reply_text("Perintah dibatalkan.", reply_markup=ReplyKeyboardRemove())

def cek(update: Update, context: CallbackContext):
    update.message.reply_text("Bot online dan siap menerima pengaduan.")

def pengaduan(update: Update, context: CallbackContext):
    user = update.message.from_user
    username = user.username or str(user.id)
    pesan = update.message.text or ""
    
    if update.message.photo:
        file_id = update.message.photo[-1].file_id
        file_obj = context.bot.get_file(file_id)
        link_gambar = file_obj.file_path
    else:
        link_gambar = "-"

    pesan_escaped = escape_markdown_v2(pesan)
    simpan_ke_sheet(username, pesan_escaped, link_gambar)

    notif = f"📩 *Pengaduan baru*\nUsername: `{escape_markdown_v2(str(username))}`\nPesan: {pesan_escaped}\nLink gambar: {escape_markdown_v2(link_gambar)}"
    kirim_notif_admin(notif, context)
    update.message.reply_text("✅ Terima kasih! Pengaduanmu sudah diterima.")

def error_handler(update: Update, context: CallbackContext):
    print(f"Error: {context.error}")

def main():
    # Pastikan token tersedia
    if not BOT_TOKEN:
        print("ERROR: BOT_TOKEN tidak ditemukan!")
        return
    
    if not GOOGLE_CREDENTIALS_JSON:
        print("ERROR: GOOGLE_CREDENTIALS tidak ditemukan!")
        return

    try:
        # Gunakan Updater langsung (cara lama yang lebih stabil)
        updater = Updater(BOT_TOKEN, use_context=True)
        dispatcher = updater.dispatcher
        
        # Add handlers
        dispatcher.add_handler(CommandHandler("start", start))
        dispatcher.add_handler(CommandHandler("cancel", cancel))
        dispatcher.add_handler(CommandHandler("cek", cek))
        dispatcher.add_handler(MessageHandler(Filters.text | Filters.photo, pengaduan))
        
        # Error handler
        dispatcher.add_error_handler(error_handler)
        
        print("✅ Bot berjalan...")
        
        # Start polling
        updater.start_polling()
        print("✅ Bot berhasil start polling...")
        updater.idle()
        
    except Exception as e:
        print(f"❌ Error starting bot: {e}")

if __name__ == "__main__":
    main()