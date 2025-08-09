import os
import json
import logging
from datetime import datetime, timedelta

from dotenv import load_dotenv
from telethon import TelegramClient, errors
from telethon.sessions import StringSession
from telethon.tl.functions.channels import JoinChannelRequest

from telegram import (
    Update, ReplyKeyboardMarkup, KeyboardButton
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, filters, ConversationHandler
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
        [KeyboardButton("Login String Session"), KeyboardButton("Login Nomor OTP")],
        [KeyboardButton("Tambah Kata Kunci"), KeyboardButton("Hapus Kata Kunci")],
        [KeyboardButton("Info")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# Conversation states
PHONE, CODE, PASSWORD = range(3)

user_sessions = {}

# Handlers

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
        login_time = data.get("login_time")
        if login_time and is_active(login_time):
            status = "Aktif"
            expire = get_expiration(login_time)
            sisa_hari = (expire - datetime.now()).days
        else:
            status = "Tidak Aktif"
            sisa_hari = 0
        await update.message.reply_text(
            f"Nama pengguna: {update.effective_user.first_name}\nStatus: {status}\nExp: {sisa_hari} hari lagi"
        )
    else:
        await update.message.reply_text("Kamu belum login, silakan login dulu ya.")

async def handle_login_string_session(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Kirim string session kamu sekarang:")
    context.user_data['awaiting_string_session'] = True

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    text = update.message.text.strip()

    # Jika menunggu string session login
    if context.user_data.get('awaiting_string_session'):
        session_str = text
        await process_string_session_login(update, context, session_str)
        context.user_data['awaiting_string_session'] = False
        return

    # Tangani kata kunci auto reply
    if user_id in users_data and "kata_kunci" in users_data[user_id]:
        for key, reply in users_data[user_id]["kata_kunci"].items():
            if key in text.lower():
                await update.message.reply_text(reply)
                return

    # Tombol keyboard
    if text == "Login String Session":
        await handle_login_string_session(update, context)
        return

    elif text == "Login Nomor OTP":
        await update.message.reply_text("Silakan kirim nomor telepon kamu (contoh: +6281234567890)")
        context.user_data['login_stage'] = 'await_phone'
        return

    elif text == "Tambah Kata Kunci":
        await update.message.reply_text("Kirim format: kata_kunci|balasan\nContoh: halo|Hai juga!")
        context.user_data['add_kata_kunci'] = True
        return

    elif context.user_data.get("add_kata_kunci"):
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

    elif text == "Hapus Kata Kunci":
        if user_id in users_data and "kata_kunci" in users_data[user_id] and users_data[user_id]["kata_kunci"]:
            keys = list(users_data[user_id]["kata_kunci"].keys())
            keys_text = "\n".join(keys)
            await update.message.reply_text(f"Kata kunci kamu:\n{keys_text}\nKirim kata kunci yang mau dihapus.")
            context.user_data["delete_kata_kunci"] = True
        else:
            await update.message.reply_text("Kamu belum punya kata kunci.")
        return

    elif context.user_data.get("delete_kata_kunci"):
        key = text.lower()
        if user_id in users_data and "kata_kunci" in users_data[user_id] and key in users_data[user_id]["kata_kunci"]:
            del users_data[user_id]["kata_kunci"][key]
            save_data()
            await update.message.reply_text(f"Kata kunci '{key}' sudah dihapus.")
        else:
            await update.message.reply_text("Kata kunci tidak ditemukan.")
        context.user_data["delete_kata_kunci"] = False
        return

    elif text == "Info":
        await info(update, context)
        return

async def process_string_session_login(update: Update, context: ContextTypes.DEFAULT_TYPE, session_str: str):
    user_id = str(update.effective_user.id)
    user_first = update.effective_user.first_name

    try:
        client = TelegramClient(StringSession(session_str), API_ID, API_HASH)
        await client.start()
        # Join channel owner otomatis
        try:
            await client(JoinChannelRequest(CHANNEL_OWNER))
        except errors.UserAlreadyParticipantError:
            pass
        except Exception as e:
            logger.warning(f"Gagal join channel: {e}")

        # Simpan data login user
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

# Login nomor OTP - ConversationHandler flow

async def login_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Silakan kirim nomor telepon kamu (contoh: +6281234567890)")
    return PHONE

async def phone_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone = update.message.text.strip()
    user_id = update.effective_user.id

    client = TelegramClient(StringSession(), API_ID, API_HASH)
    await client.connect()

    try:
        await client.send_code_request(phone)
    except errors.PhoneNumberInvalidError:
        await update.message.reply_text("Nomor tidak valid, coba lagi.")
        await client.disconnect()
        return ConversationHandler.END
    except Exception as e:
        await update.message.reply_text(f"Error kirim kode: {e}")
        await client.disconnect()
        return ConversationHandler.END

    user_sessions[user_id] = {"client": client, "phone": phone}
    await update.message.reply_text("Kode OTP sudah dikirim, silakan kirim kodenya.")
    return CODE

async def code_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    code = update.message.text.strip()
    user_id = update.effective_user.id
    session = user_sessions.get(user_id)
    if not session:
        await update.message.reply_text("Sesi login tidak ditemukan, mulai ulang login.")
        return ConversationHandler.END

    client = session["client"]
    phone = session["phone"]

    try:
        me = await client.sign_in(phone, code)
        # Login sukses tanpa 2FA
        session_str = client.session.save()

        # Simpan data login user
        if str(user_id) not in users_data:
            users_data[str(user_id)] = {}
        users_data[str(user_id)]["login_time"] = datetime.now().isoformat()
        save_data()

        await update.message.reply_text(f"Login sukses! Session kamu:\n{session_str}")
        await client(JoinChannelRequest(CHANNEL_OWNER))
        await client.disconnect()
        return ConversationHandler.END

    except errors.SessionPasswordNeededError:
        await update.message.reply_text("Masukkan password 2FA kamu.")
        return PASSWORD
    except Exception as e:
        await update.message.reply_text(f"Gagal login: {e}")
        await client.disconnect()
        return ConversationHandler.END

async def password_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    password = update.message.text.strip()
    user_id = update.effective_user.id
    session = user_sessions.get(user_id)
    if not session:
        await update.message.reply_text("Sesi login tidak ditemukan, mulai ulang login.")
        return ConversationHandler.END

    client = session["client"]

    try:
        me = await client.sign_in(password=password)
        session_str = client.session.save()

        # Simpan data login user
        if str(user_id) not in users_data:
            users_data[str(user_id)] = {}
        users_data[str(user_id)]["login_time"] = datetime.now().isoformat()
        save_data()

        await update.message.reply_text(f"Login sukses! Session kamu:\n{session_str}")
        await client(JoinChannelRequest(CHANNEL_OWNER))
        await client.disconnect()
        return ConversationHandler.END

    except Exception as e:
        await update.message.reply_text(f"Gagal login dengan password: {e}")
        await client.disconnect()
        return ConversationHandler.END

# Main function

def main():
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^(Login Nomor OTP)$"), login_start)],
        states={
            PHONE: [MessageHandler(filters.TEXT & (~filters.COMMAND), phone_handler)],
            CODE: [MessageHandler(filters.TEXT & (~filters.COMMAND), code_handler)],
            PASSWORD: [MessageHandler(filters.TEXT & (~filters.COMMAND), password_handler)],
        },
        fallbacks=[],
        allow_reentry=True,
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("info", info))
    application.add_handler(conv_handler)
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text))

    application.run_polling()

if __name__ == "__main__":
    main()
