from dotenv import load_dotenv
import os

load_dotenv()

BOT_TOKEN = os.environ.get("BOT_TOKEN")
ALLOWED_USERS = os.environ.get("ALLOWED_USERS", "").split(",")
ALLOWED_USERNAMES = os.environ.get("ALLOWED_USERNAMES", "").split(",")
ISSUE_COLLECTOR_ID = int(os.environ.get("ISSUE_COLLECTOR_ID", "0"))
