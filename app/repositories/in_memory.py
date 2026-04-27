from threading import Lock

users: dict[str, dict[str, str]] = {}
refresh_tokens: dict[str, str] = {}
users_lock = Lock()
refresh_tokens_lock = Lock()
