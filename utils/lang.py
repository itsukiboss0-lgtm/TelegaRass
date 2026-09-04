# Поддержка языков (базовая)
LANGUAGES = {
    "ru": {
        "start": "🌟 Добро пожаловать в <b>Mail Pulse</b>!",
        "profile_added": "✅ Профиль добавлен",
    }
}

def get_text(user_id: int, key: str) -> str:
    return LANGUAGES.get("ru", {}).get(key, key)