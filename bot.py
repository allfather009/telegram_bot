import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import nest_asyncio
import asyncio
import os
nest_asyncio.apply()
asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# ==== CONFIG ====

TOKEN = os.environ.get("TOKEN")
ADMINS = [2026933109]
BANK_NUMBER = "7719584860"

# ✅ Add/remove your advertisers here
PARTNERS = ["Nerdosis", "None"]
referral_counts = {partner: 0 for partner in PARTNERS}

# ==== LOGGING ====
logging.basicConfig(format="%(asctime)s - %(message)s", level=logging.INFO)

# ==== SESSION STORAGE ====
user_sessions = {}

# ==== /START ====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    user_sessions[user.id] = {"step": "waiting_for_proof"}

    await update.message.reply_text(
        f"👋 Welcome!\n\n💸 Please send money to:\n🏦 FIB Account: {BANK_NUMBER}\n\n"
        f"📸 Then upload a screenshot of your bank transfer here."
    )

# ==== HANDLE PAYMENT ====
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    user_id = user.id
    username = user.username or user.first_name

    user_sessions[user_id] = {
        "step": "waiting_for_email",
        "proof_file_id": update.message.photo[-1].file_id,
        "username": username
    }

    await update.message.reply_text("✅ Got the screenshot!\nNow send your **email and password**.")

# ==== HANDLE EMAIL + PASSWORD ====
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    user_id = user.id
    text = update.message.text

    if user_sessions.get(user_id, {}).get("step") == "waiting_for_email":
        user_sessions[user_id]["email_password"] = text
        user_sessions[user_id]["step"] = "waiting_for_referral"

        # Show referral buttons
        buttons = [[InlineKeyboardButton(p, callback_data=p)] for p in PARTNERS]
        reply_markup = InlineKeyboardMarkup(buttons)

        await update.message.reply_text("👥 Who referred you to us?", reply_markup=reply_markup)
    else:
        await update.message.reply_text("Please first send your payment screenshot.")

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

    await query.edit_message_text("✅ Thank you! An admin will contact you shortly.")

    for admin_id in ADMINS:
        try:
            await context.bot.send_photo(
                chat_id=admin_id,
                photo=proof,
                caption=(
                    f"📥 New Order Received!\n\n"
                    f"👤 Username: @{username}\n🆔 ID: {user_id}\n\n"
                    f"📧 Email/Password:\n{email_pass}\n"
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
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(CallbackQueryHandler(handle_referral))

    print("🤖 Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
