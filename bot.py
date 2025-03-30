import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import nest_asyncio
import asyncio
import sys
import os
import re

nest_asyncio.apply()
if sys.platform.startswith('win'):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# ==== CONFIG ====
TOKEN = os.environ.get("TOKEN")
ADMINS = [2026933109]
BANK_NUMBER = "7719584860"
CHANNEL_LINK = "https://t.me/+75CaCQXsvqUwMTE6"

PARTNERS = ["Nerdosis", "None"]
referral_counts = {partner: 0 for partner in PARTNERS}

# ==== LOGGING ====
logging.basicConfig(format="%(asctime)s - %(message)s", level=logging.INFO)

# ==== SESSION STORAGE ====
user_sessions = {}

def is_valid_email(email):
    return re.match(r"[^@\s]+@[^@\s]+\.[^@\s]+", email)

# ==== /START ====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    user_sessions[user.id] = {"step": "waiting_for_offer"}

    buttons = [
        [InlineKeyboardButton("🟠 1 Year", callback_data="offer_1year")],
        [InlineKeyboardButton("🔵 6 Months", callback_data="offer_6months")]
    ]
    reply_markup = InlineKeyboardMarkup(buttons)

    await update.message.reply_text("🛍️ Please choose an offer:", reply_markup=reply_markup)

# ==== HANDLE OFFER SELECTION ====
async def handle_offer_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    user_id = user.id

    offer = "1 Year" if query.data == "offer_1year" else "6 Months"
    user_sessions[user_id] = {
        "step": "waiting_for_proof",
        "offer": offer,
        "username": user.username or user.first_name
    }

    await query.edit_message_text(
        f"✅ Offer selected: {offer}\n\n💸 Please send money to:\n🏦 FIB Account: {BANK_NUMBER}\n\n"
        "📸 Then upload a screenshot of your bank transfer here."
    )

# ==== HANDLE PAYMENT ====
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    user_id = user.id

    if user_id not in user_sessions or user_sessions[user_id].get("step") != "waiting_for_proof":
        return await update.message.reply_text("❗ Please start again with /start")

    user_sessions[user_id]["step"] = "waiting_for_email"
    user_sessions[user_id]["proof_file_id"] = update.message.photo[-1].file_id

    await update.message.reply_text(
        "✅ Got the screenshot!\n\n"
        "📧 Now please send the email and password you want us to use.\n"
        "💡 Example: yourname@gmail.com yourPassword123\n\n"
        "🛡️ Don't worry — your data is safe with us.\n"
        "We will use this email to activate access to the medical resources you purchased."
    )


# ==== HANDLE EMAIL + PASSWORD ====
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    user_id = user.id
    text = update.message.text

    if user_sessions.get(user_id, {}).get("step") == "waiting_for_email":
        if not is_valid_email(text.split()[0]):
            return await update.message.reply_text("❌ Please send a **valid email address** followed by your password.")

        user_sessions[user_id]["email_password"] = text
        user_sessions[user_id]["step"] = "waiting_for_referral"

        buttons = [[InlineKeyboardButton(p, callback_data=p)] for p in PARTNERS]
        reply_markup = InlineKeyboardMarkup(buttons)

        await update.message.reply_text("👥 Who referred you to us?", reply_markup=reply_markup)
    else:
        await update.message.reply_text("Please first complete the previous steps.")

# ==== HANDLE REFERRAL CHOICE ====
async def handle_referral(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    user_id = user.id
    username = user.username or user.first_name

    referral = query.data
    referral_counts[referral] += 1

    user_sessions[user_id]["referral"] = referral
    user_sessions[user_id]["step"] = "complete"

    proof = user_sessions[user_id].get("proof_file_id")
    email_pass = user_sessions[user_id].get("email_password")
    offer = user_sessions[user_id].get("offer")

    await query.edit_message_text(
        f"✅ Thank you! An admin will contact you shortly.\n\n👉 [Join Our Channel]({CHANNEL_LINK})",
        parse_mode="Markdown",
        disable_web_page_preview=True
    )

    for admin_id in ADMINS:
        try:
            await context.bot.send_photo(
                chat_id=admin_id,
                photo=proof,
                caption=(
                    f"📥 New Order Received!\n\n"
                    f"👤 Username: @{username}\n🆔 ID: {user_id}\n"
                    f"📦 Offer: {offer}\n"
                    f"📧 Email/Password: {email_pass}\n"
                    f"📣 Referred by: {referral}"
                )
            )
        except Exception as e:
            logging.error(f"❌ Error sending to admin {admin_id}: {e}")

# ==== /referrals command ====
async def show_referral_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMINS:
        return await update.message.reply_text("❌ You're not authorized to use this command.")

    text = "📊 Referral Stats:\n"
    for partner, count in referral_counts.items():
        text += f"🔹 {partner}: {count} user(s)\n"

    await update.message.reply_text(text)

# ==== MAIN ====
def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("zaniary", show_referral_stats))
    app.add_handler(CallbackQueryHandler(handle_offer_selection, pattern="^offer_"))
    app.add_handler(CallbackQueryHandler(handle_referral, pattern="^(?!offer_).*$"))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    print("🤖 Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
