from config import ALLOWED_USERS, ALLOWED_USERNAMES

def is_authorized(user) -> bool:
    user_id = str(user.id)
    username = user.username.lower() if user.username else None

    return (
        user_id in ALLOWED_USERS or
        (username and username in [u.strip().lower() for u in ALLOWED_USERNAMES])
    )
