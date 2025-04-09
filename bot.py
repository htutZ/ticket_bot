import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, filters,
    CallbackQueryHandler, ContextTypes, ConversationHandler
)
from config import BOT_TOKEN, ALLOWED_USERS, ALLOWED_USERNAMES, ISSUE_COLLECTOR_ID
from database import get_ticket_updates, init_db, add_ticket, get_open_tickets, get_ticket, mark_ticket_resolved, add_ticket_update, init_pool

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Conversation states
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
    """Check if user is the issue collector"""
    return str(user_id) == str(ISSUE_COLLECTOR_ID)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send welcome message"""
    if not is_allowed(update.effective_user):
        return
    await update.message.reply_text("Welcome to the Ticket Bot!")

async def getid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get user ID"""
    if not is_allowed(update.effective_user):
        return

    if update.message.reply_to_message:
        user = update.message.reply_to_message.from_user
        await update.message.reply_text(
            f"ID for [{user.full_name}](tg://user?id={user.id}): `{user.id}`",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text("Please reply to a user's message to get their Telegram ID!")

async def newticket_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start new ticket creation"""
    if not is_collector(update.effective_user.id):
        await update.message.reply_text("You're not authorized to create tickets.")
        return ConversationHandler.END
        
    await update.message.reply_text("Please send the ticket's details.")
    return DESCRIPTION

async def ticket_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Store ticket description and ask for photo"""
    context.user_data["description"] = update.message.text
    await update.message.reply_text(
        "Send a photo for this ticket or /skip to continue without photo."
    )
    return PHOTO

async def ticket_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle ticket photo"""
    try:
        photo = update.message.photo[-1]
        description = context.user_data["description"]
        ticket_id = add_ticket(description, photo_file_id=photo.file_id)
        await update.message.reply_text(
            f"Ticket #{ticket_id} created with photo ✅"
        )
    except Exception as e:
        logger.error(f"Error creating ticket with photo: {e}")
        await update.message.reply_text("Failed to create ticket. Please try again.")
    finally:
        return ConversationHandler.END

async def skip_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle skipping photo"""
    try:
        description = context.user_data["description"]
        ticket_id = add_ticket(description)
        await update.message.reply_text(
            f"Ticket #{ticket_id} created without photo ✅"
        )
    except Exception as e:
        logger.error(f"Error creating ticket without photo: {e}")
        await update.message.reply_text("Failed to create ticket. Please try again.")
    finally:
        return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel ticket creation"""
    await update.message.reply_text("Ticket creation cancelled.")
    return ConversationHandler.END

async def tickets(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all open tickets"""
    if not is_allowed(update.effective_user):
        return

    try:
        tickets = get_open_tickets()
        if not tickets:
            await update.message.reply_text("No open tickets found!")
            return

        keyboard = [
            [InlineKeyboardButton(
                f"🎫 Ticket {t['id'] if isinstance(t, dict) else t[0]}", 
                callback_data=f"ticket_{t['id'] if isinstance(t, dict) else t[0]}"
            )]
            for t in tickets
        ]

        await update.message.reply_text(
            "📋 Open Tickets:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception as e:
        logger.error(f"Error listing tickets: {e}")
        await update.message.reply_text("Failed to load tickets. Please try again.")

async def ticket_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle ticket interaction"""
    query = update.callback_query
    await query.answer()

    try:
        data = query.data
        user = update.effective_user

        if not is_allowed(user):
            await query.edit_message_text("❌ Unauthorized access")
            return

        if data.startswith("ticket_"):
            ticket_id = int(data.split("_")[1])
            ticket = get_ticket(ticket_id)
            
            if not ticket:
                await query.edit_message_text("Ticket not found ❌")
                return

            # Safely access ticket data
            ticket_id = ticket['id'] if isinstance(ticket, dict) else ticket[0]
            description = ticket['description'] if isinstance(ticket, dict) else ticket[1]
            photo_file_id = ticket.get('photo_file_id') if isinstance(ticket, dict) else ticket[2] if len(ticket) > 2 else None

            text = f"📝 *Ticket {ticket_id}*\n\n{description}"

            # Add updates if any
            updates = get_ticket_updates(ticket_id)
            if updates:
                text += "\n\n*Updates:*"
                for update in updates:
                    update_text = update['update_text'] if isinstance(update, dict) else update[0]
                    username = update['username'] if isinstance(update, dict) else update[1]
                    timestamp = update['created_at'] if isinstance(update, dict) else update[2]
                    time_part = timestamp.split()[1][:5] if timestamp else ""
                    text += f"\n\n{time_part} - {username}:\n{update_text}"

            # Prepare buttons
            buttons = []
            if is_allowed(user):
                buttons.append([InlineKeyboardButton("💬 Reply/Update", callback_data=f"update_{ticket_id}")])
            if is_collector(user.id):
                buttons.append([InlineKeyboardButton("✅ Mark Resolved", callback_data=f"resolve_{ticket_id}")])

            # Send response
            if photo_file_id:
                await query.message.reply_photo(
                    photo=photo_file_id,
                    caption=text,
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup(buttons)
                )
            else:
                await query.edit_message_text(
                    text=text,
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup(buttons)
                )

        elif data.startswith("resolve_"):
            ticket_id = int(data.split("_")[1])
            if not is_collector(user.id):
                await query.answer("❌ Unauthorized")
                return

            if mark_ticket_resolved(ticket_id):
                await query.edit_message_text(f"Ticket {ticket_id} resolved ✅")
            else:
                await query.edit_message_text(f"Failed to resolve ticket {ticket_id}")

        elif data.startswith("update_"):
            ticket_id = int(data.split("_")[1])
            context.user_data["ticket_id"] = ticket_id
            await query.edit_message_text("Please send your update:")
            return UPDATE_TICKET

    except Exception as e:
        logger.error(f"Error in ticket callback: {e}")
        await query.edit_message_text("An error occurred. Please try again.")

async def update_ticket_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle ticket updates"""
    try:
        ticket_id = context.user_data.get("ticket_id")
        if not ticket_id:
            await update.message.reply_text("Session expired. Please start over.")
            return ConversationHandler.END

        username = update.effective_user.username or update.effective_user.first_name
        add_ticket_update(ticket_id, username, update.message.text)
        await update.message.reply_text("Update added successfully ✅")
        
    except Exception as e:
        logger.error(f"Error adding update: {e}")
        await update.message.reply_text("Failed to add update. Please try again.")
    finally:
        return ConversationHandler.END

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors"""
    logger.error(f"Update {update} caused error {context.error}")
    if isinstance(update, Update):
        await update.message.reply_text("An error occurred. Please try again later.")

def main():
    """Start the bot"""
    try:
        init_pool()
        logger.info("🚀 Starting bot...")

        app = ApplicationBuilder().token(BOT_TOKEN).build()
        
        # Conversation handlers
        ticket_creation_handler = ConversationHandler(
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

        update_handler = ConversationHandler(
            entry_points=[CallbackQueryHandler(ticket_callback, pattern="^update_")],
            states={
                UPDATE_TICKET: [MessageHandler(filters.TEXT & ~filters.COMMAND, update_ticket_text)],
            },
            fallbacks=[],
        )

        # Add handlers
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("getid", getid))
        app.add_handler(CommandHandler("tickets", tickets))
        app.add_handler(ticket_creation_handler)
        app.add_handler(update_handler)
        app.add_handler(CallbackQueryHandler(ticket_callback, pattern="^(ticket_|resolve_)"))
        app.add_error_handler(error_handler)

        logger.info("🤖 Bot is running...")
        app.run_polling()

    except Exception as e:
        logger.critical(f"Failed to start bot: {e}")

if __name__ == "__main__":
    main()