import json
import os
from typing import Dict, Any

DATA_DIR = "data"
ACCOUNTS_FILE = os.path.join(DATA_DIR, "accounts.json")
MAILING_SETTINGS_FILE = os.path.join(DATA_DIR, "mailing_settings.json")
MAILING_STATS_FILE = os.path.join(DATA_DIR, "mailing_stats.json")

def ensure_data_dir():
    """Создаёт папку data, если её нет"""
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)

def save_json(data: Dict[Any, Any], filename: str):
    """Сохраняет данные в JSON файл"""
    ensure_data_dir()
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)

def load_json(filename: str) -> Dict[Any, Any]:
    """Загружает данные из JSON файла, если он существует"""
    if os.path.exists(filename):
        with open(filename, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

# Функции для конкретных данных
def save_accounts(accounts: Dict[int, list]):
    save_json(accounts, ACCOUNTS_FILE)

def load_accounts() -> Dict[int, list]:
    return load_json(ACCOUNTS_FILE)

def save_mailing_settings(settings: Dict[int, dict]):
    # Преобразуем timedelta в строку для сохранения
    data = {}
    for uid, s in settings.items():
        data[str(uid)] = s.copy()
        if 'auto_stop_time' in data[str(uid)] and data[str(uid)]['auto_stop_time'] is not None:
            # timedelta -> seconds
            data[str(uid)]['auto_stop_time'] = data[str(uid)]['auto_stop_time'].total_seconds()
        # stop_time - datetime, тоже преобразуем в строку iso
        if 'stop_time' in data[str(uid)] and data[str(uid)]['stop_time'] is not None:
            data[str(uid)]['stop_time'] = data[str(uid)]['stop_time'].isoformat()
        if 'start_time' in data[str(uid)] and data[str(uid)]['start_time'] is not None:
            data[str(uid)]['start_time'] = data[str(uid)]['start_time'].isoformat()
    save_json(data, MAILING_SETTINGS_FILE)

def load_mailing_settings() -> Dict[int, dict]:
    raw = load_json(MAILING_SETTINGS_FILE)
    result = {}
    for uid_str, s in raw.items():
        uid = int(uid_str)
        # Преобразуем обратно
        if 'auto_stop_time' in s and s['auto_stop_time'] is not None:
            from datetime import timedelta
            s['auto_stop_time'] = timedelta(seconds=s['auto_stop_time'])
        if 'stop_time' in s and s['stop_time'] is not None:
            from datetime import datetime
            s['stop_time'] = datetime.fromisoformat(s['stop_time'])
        if 'start_time' in s and s['start_time'] is not None:
            from datetime import datetime
            s['start_time'] = datetime.fromisoformat(s['start_time'])
        result[uid] = s
    return result

def save_mailing_stats(stats: Dict[int, dict]):
    save_json(stats, MAILING_STATS_FILE)

def load_mailing_stats() -> Dict[int, dict]:
    return load_json(MAILING_STATS_FILE)