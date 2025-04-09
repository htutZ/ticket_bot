import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, filters,
    CallbackQueryHandler, ContextTypes, ConversationHandler
)
from config import BOT_TOKEN, ALLOWED_USERS, ALLOWED_USERNAMES, ISSUE_COLLECTOR_ID
from database import get_ticket_updates, init_db, add_ticket, get_open_tickets, get_ticket, mark_ticket_resolved, add_ticket_update, init_pool

logging.basicConfig(level=logging.INFO)

DESCRIPTION, PHOTO, UPDATE_TICKET = range(3)

def is_allowed(user):
    """Check if user is allowed to use the bot"""
    if isinstance(user, str):
        username = user.lower()
        return username in [u.strip().lower() for u in ALLOWED_USERNAMES]
    else:
        user_id = str(user.id)
        username = user.username.lower() if user.username else None
        return (
            user_id in ALLOWED_USERS or
            (username and username in [u.strip().lower() for u in ALLOWED_USERNAMES])
        )

def is_collector(user_id):
    return user_id == ISSUE_COLLECTOR_ID

# start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update.effective_user):
        return
    await update.message.reply_text("Welcome to htut's ticket bot!")

# get id
async def getid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update.effective_user):
        return

    message = update.message
    if message.reply_to_message:
        user = message.reply_to_message.from_user
        await message.reply_text(
            f"ID for [{user.full_name}](tg://user?id={user.id}): `{user.id}`",
            parse_mode="Markdown"
        )
    else:
        await message.reply_text("Please reply to a user's message to get their Telegram ID!")

# new ticket command that can only be used by the issue collector
async def newticket_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_collector(update.effective_user.id):
        return
    await update.message.reply_text("Please send the ticket's details.")
    return DESCRIPTION

async def ticket_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["description"] = update.message.text
    await update.message.reply_text("Send a photo here or skip with /skip to continue without photo.")
    return PHOTO

async def ticket_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo = update.message.photo[-1]
    file_id = photo.file_id
    description = context.user_data["description"]
    add_ticket(description, photo_file_id=file_id)
    await update.message.reply_text("Ticket is created with photo included ✅")
    return ConversationHandler.END

async def skip_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    description = context.user_data["description"]
    add_ticket(description)
    await update.message.reply_text("Ticket is created without photo ✅")
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Ticket creation is cancelled.")
    return ConversationHandler.END

# View the tickets
async def tickets(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update.effective_user):
        return

    tickets = get_open_tickets()
    if not tickets:
        await update.message.reply_text("Today is quiet! No open tickets!")
        return

    keyboard = [
        [InlineKeyboardButton(f"🎫 Ticket {t[0]}", callback_data=f"ticket_{t[0]}")]
        for t in tickets
    ]
    await update.message.reply_text("📋 Open Tickets:", reply_markup=InlineKeyboardMarkup(keyboard))

# Ticket Viewer
async def ticket_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data
    user = update.effective_user

    if not is_allowed(user):
        await query.answer("You don't have permission to do this ❌")
        return

    if data.startswith("ticket_"):
        ticket_id = int(data.split("_")[1])
        ticket = get_ticket(ticket_id)
        if not ticket:
            await query.edit_message_text("Ticket not found ❌")
            return
        text = f"📝 *Ticket {ticket[0]}*\n\n{ticket[1]}"

        updates = get_ticket_updates(ticket_id)
        if updates:
            text += "\n\n*Updates:*"
            for update_text, username, created_at in updates:
                time_part = created_at.split()[1][:5] 
                text += f"\n\n{time_part} - {username}: {update_text}"

        buttons = []
        if is_allowed(user):
            buttons.append([InlineKeyboardButton("💬 Reply/Update", callback_data=f"update_{ticket_id}")])
        if is_collector(user.id):
            buttons.append([InlineKeyboardButton("Mark as Resolved ✅", callback_data=f"resolve_{ticket_id}")])

        if ticket[2]:
            await query.message.reply_photo(
                photo=ticket[2],
                caption=text,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(buttons) if buttons else None
            )
        else:
            await query.edit_message_text(
                text=text,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(buttons) if buttons else None
            )

    elif data.startswith("resolve_"):
        ticket_id = int(data.split("_")[1])
        if not is_collector(user.id):
            await query.answer("You can't resolve tickets ❌")
            return

        mark_ticket_resolved(ticket_id)
        await query.edit_message_text(f"Ticket {ticket_id} marked as resolved and removed ✅")

    elif data.startswith("update_"):
        ticket_id = int(data.split("_")[1])
        await query.edit_message_text("Please send your update or comment for this ticket.")
        context.user_data["ticket_id"] = ticket_id
        return UPDATE_TICKET

async def update_ticket_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ticket_id = context.user_data.get("ticket_id")
    if not ticket_id:
        await update.message.reply_text("No ticket ID found.")
        return ConversationHandler.END 

    update_text = update.message.text
    username = update.effective_user.username if update.effective_user.username else update.effective_user.first_name
    add_ticket_update(ticket_id, username, update_text)
    await update.message.reply_text("Your update has been added to the ticket! ✅")
    return ConversationHandler.END

# Main
def main():
    init_pool()
    print("🚀 main() is running...")

    app = ApplicationBuilder().token(BOT_TOKEN).build()
    update_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(ticket_callback, pattern="^update_")],
        states={
            UPDATE_TICKET: [MessageHandler(filters.TEXT & ~filters.COMMAND, update_ticket_text)],
        },
        fallbacks=[],
    )

    ticket_creation_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("newticket", newticket_start)],
        states={
            DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, ticket_description)],
            PHOTO: [
                MessageHandler(filters.PHOTO, ticket_photo),
                CommandHandler("skip", skip_photo)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("getid", getid))
    app.add_handler(CommandHandler("tickets", tickets))
    app.add_handler(ticket_creation_conv_handler)
    app.add_handler(update_conv_handler)
    app.add_handler(CallbackQueryHandler(ticket_callback, pattern="^(ticket_|resolve_)"))

    print("🤖 Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()