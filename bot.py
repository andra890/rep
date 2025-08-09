import os
import json
import logging
from datetime import datetime, timedelta

from dotenv import load_dotenv
from telethon import TelegramClient, errors
from telethon.tl.functions.channels import JoinChannelRequest
from telegram import (
    Update, ReplyKeyboardMarkup, KeyboardButton
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, filters
)

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
CHANNEL_OWNER = os.getenv("CHANNEL_OWNER")

logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

logger = logging.getLogger(__name__)

DATA_FILE = "userdata.json"

if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r") as f:
        users_data = json.load(f)
else:
    users_data = {}

def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump(users_data, f, indent=2)

def get_expiration(login_time_str):
    login_time = datetime.fromisoformat(login_time_str)
    return login_time + timedelta(days=30)

def is_active(login_time_str):
    return datetime.now() < get_expiration(login_time_str)

def create_main_keyboard():
    keyboard = [
        [KeyboardButton("Login")],
        [KeyboardButton("Tambah Kata Kunci"), KeyboardButton("Tambah Balasan")],
        [KeyboardButton("Hapus Kata Kunci"), KeyboardButton("Hapus Balasan")],
        [KeyboardButton("Info")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(
        f"Hai, {user.first_name}! aku @bou yg bantu kamu promosi, semoga setiap hari orderan kamu selalu rame ya 💗✨",
        reply_markup=create_main_keyboard()
    )

async def info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if user_id in users_data:
        data = users_data[user_id]
        nama = update.effective_user.first_name
        login_time = data.get("login_time")
        if login_time and is_active(login_time):
            status = "Aktif"
            expire = get_expiration(login_time)
            sisa_hari = (expire - datetime.now()).days
        else:
            status = "Tidak Aktif"
            sisa_hari = 0
        await update.message.reply_text(
            f"Nama pengguna: {nama}\nStatus: {status}\nExp: {sisa_hari} hari lagi"
        )
    else:
        await update.message.reply_text("Kamu belum login, silakan klik Login dulu ya.")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    user_id = str(update.effective_user.id)

    if context.user_data.get("login_mode"):
        await handle_login(update, context, text)
        context.user_data["login_mode"] = False
        return

    if context.user_data.get("add_kata_kunci"):
        parts = text.split("|")
        if len(parts) != 2:
            await update.message.reply_text("Format salah! Kirim: kata_kunci|balasan")
        else:
            key = parts[0].strip().lower()
            balas = parts[1].strip()
            if user_id not in users_data:
                users_data[user_id] = {}
            if "kata_kunci" not in users_data[user_id]:
                users_data[user_id]["kata_kunci"] = {}
            users_data[user_id]["kata_kunci"][key] = balas
            save_data()
            await update.message.reply_text(f"Kata kunci '{key}' dan balasan sudah tersimpan.")
        context.user_data["add_kata_kunci"] = False
        return

    if context.user_data.get("add_balasan"):
        await update.message.reply_text("Fitur tambah balasan akan menyatu dengan kata kunci ya, nanti aku update.")
        context.user_data["add_balasan"] = False
        return

    if context.user_data.get("delete_kata_kunci"):
        key = text.lower()
        if user_id in users_data and "kata_kunci" in users_data[user_id] and key in users_data[user_id]["kata_kunci"]:
            del users_data[user_id]["kata_kunci"][key]
            save_data()
            await update.message.reply_text(f"Kata kunci '{key}' sudah dihapus.")
        else:
            await update.message.reply_text("Kata kunci tidak ditemukan.")
        context.user_data["delete_kata_kunci"] = False
        return

    if context.user_data.get("delete_balasan"):
        await update.message.reply_text("Fitur hapus balasan akan menyatu dengan kata kunci ya, nanti aku update.")
        context.user_data["delete_balasan"] = False
        return

    if user_id in users_data and "kata_kunci" in users_data[user_id]:
        for key, reply in users_data[user_id]["kata_kunci"].items():
            if key in text.lower():
                await update.message.reply_text(reply)
                return

    if text == "Login":
        await update.message.reply_text("Kirim string session kamu sekarang.")
        context.user_data["login_mode"] = True
        return

    if text == "Tambah Kata Kunci":
        await update.message.reply_text("Kirim format: kata_kunci|balasan\nContoh: halo|Hai juga!")
        context.user_data["add_kata_kunci"] = True
        return

    if text == "Tambah Balasan":
        await update.message.reply_text("Fitur ini dalam pengembangan ya, nanti aku update.")
        return

    if text == "Hapus Kata Kunci":
        if user_id in users_data and "kata_kunci" in users_data[user_id] and users_data[user_id]["kata_kunci"]:
            keys = list(users_data[user_id]["kata_kunci"].keys())
            keys_text = "\n".join(keys)
            await update.message.reply_text(f"Kata kunci kamu:\n{keys_text}\nKirim kata kunci yang mau dihapus.")
            context.user_data["delete_kata_kunci"] = True
        else:
            await update.message.reply_text("Kamu belum punya kata kunci.")
        return

    if text == "Hapus Balasan":
        await update.message.reply_text("Fitur hapus balasan akan menyatu dengan kata kunci ya, nanti aku update.")
        return

    if text == "Info":
        await info(update, context)
        return

async def handle_login(update: Update, context: ContextTypes.DEFAULT_TYPE, session_str: str):
    user_id = str(update.effective_user.id)
    user_first = update.effective_user.first_name

    session_path = f"sessions/{user_id}.session"

    if not os.path.exists("sessions"):
        os.mkdir("sessions")

    try:
        # Simpan session string ke file, harus sesuai format Telethon
        with open(session_path, "w") as f:
            f.write(session_str)

        client = TelegramClient(session_path, API_ID, API_HASH)
        await client.start()
        try:
            await client(JoinChannelRequest(CHANNEL_OWNER))
        except errors.UserAlreadyParticipantError:
            pass
        except Exception as e:
            logger.warning(f"Gagal join channel: {e}")

        if user_id not in users_data:
            users_data[user_id] = {}
        users_data[user_id]["login_time"] = datetime.now().isoformat()
        save_data()

        await update.message.reply_text(f"Halo {user_first}, login sukses! Kamu aktif 30 hari.")
        await update.message.reply_text("Sekarang kamu bisa tambah kata kunci dan balasan lewat tombol ya.")
        await client.disconnect()

    except Exception as e:
        logger.error(f"Login error: {e}")
        await update.message.reply_text("Gagal login, pastikan string session kamu benar dan valid.")

def main():
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("info", info))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text))
    application.run_polling()

if __name__ == "__main__":
    main()
