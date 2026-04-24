import requests
from typing import Optional, Dict, Any, List
import os
import json

BASE_URL = "https://retinoserver.vercel.app"

_timeout = 10
_token: Optional[str] = None

_TOKEN_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "auth_token.json")


def _load_token() -> Optional[str]:
    try:
        if not os.path.exists(_TOKEN_FILE):
            return None
        with open(_TOKEN_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("token")
    except Exception:
        return None


def _save_token(token: str) -> None:
    try:
        with open(_TOKEN_FILE, "w", encoding="utf-8") as f:
            json.dump({"token": token}, f, ensure_ascii=False)
    except Exception:
        pass


def _clear_token() -> None:
    try:
        if os.path.exists(_TOKEN_FILE):
            os.remove(_TOKEN_FILE)
    except Exception:
        pass


_token = _load_token()


def _headers() -> Dict[str, str]:
    h = {"Content-Type": "application/json"}
    if _token:
        h["Authorization"] = f"Bearer {_token}"
    return h


def register_user(username: str, password: str):
    r = requests.post(
        f"{BASE_URL}/auth/register",
        json={"username": username, "password": password},
        headers=_headers(),
        timeout=_timeout,
    )

    if r.status_code == 200:
        return True, ""

    try:
        detail = r.json().get("detail", "")
    except Exception:
        detail = ""

    if detail == "Invalid username":
        return False, "Логин должен должен содержать от 3 до 64 символов. Разрешены английские буквы (A-Z), цифры (1-9), дефис (-) или нижнее подчёркивание (_)"

    if detail == "Invalid password length":
        return False, "Пароль должен содержать от 4 до 256 символов"

    if detail == "User already exists":
        return False, "Этот логин уже используется\nПожалуйста, выберите другой, чтобы зарегистрироваться"

    if detail == "User is deleted":
        return False, "Этот логин уже был использован ранее\nПожалуйста, выберите другой, чтобы зарегистрироваться"

    return False, "Не удалось зарегистрироваться\nПопробуйте другой логин или повторите позже"


def username_status(username: str) -> str:
    r = requests.post(
        f"{BASE_URL}/auth/username_status",
        json={"username": username},
        headers=_headers(),
        timeout=_timeout,
    )
    if r.status_code == 200:
        data = r.json()
        return data.get("status", "ok")
    if r.status_code == 404:
        return "unknown"
    r.raise_for_status()
    return "unknown"


def authenticate_user(username: str, password: str) -> bool:
    global _token
    try:
        r = requests.post(
            f"{BASE_URL}/auth/login",
            json={"username": username, "password": password},
            headers={"Content-Type": "application/json"},
            timeout=_timeout,
        )

        if r.status_code == 200:
            data = r.json()
            _token = data.get("token")
            if _token:
                _save_token(_token)
                return True

        if r.status_code in (401, 403):
            _token = None
            _clear_token()
            return False

        _token = None
        _clear_token()
        return False

    except requests.exceptions.RequestException:
        _token = None
        _clear_token()
        return False

def logout() -> None:
    global _token
    try:
        requests.post(
            f"{BASE_URL}/auth/logout",
            headers=_headers(),
            timeout=_timeout,
        )
    except Exception:
        pass

    _token = None
    _clear_token()

def change_password(username: str, old_password: str, new_password: str) -> bool:
    r = requests.post(
        f"{BASE_URL}/auth/change_password",
        json={"username": username, "old_password": old_password, "new_password": new_password},
        headers=_headers(),
        timeout=_timeout,
    )
    return r.status_code == 200


def delete_user_soft(confirm_phrase: str = "delete my account") -> bool:
    r = requests.post(
        f"{BASE_URL}/auth/delete_user",
        json={"confirm": confirm_phrase},
        headers=_headers(),
        timeout=_timeout,
    )
    return r.status_code == 200

def get_updates() -> List[Dict[str, Any]]:
    r = requests.get(f"{BASE_URL}/public/updates", headers=_headers(), timeout=_timeout)
    r.raise_for_status()
    data = r.json()
    if isinstance(data, list):
        return data
    return []

def save_training_record(user_stage: int, ai_stage: int, score: int, dice: float, p_max: float, ts: Optional[str] = None) -> bool:
    payload = {
        "user_stage": int(user_stage),
        "ai_stage": int(ai_stage),
        "score": int(score),
        "dice": float(dice),
        "p_max": float(p_max),
    }
    if ts:
        payload["ts"] = ts

    r = requests.post(
        f"{BASE_URL}/training/record",
        json=payload,
        headers=_headers(),
        timeout=_timeout,
    )
    return r.status_code == 200

def get_training_history(limit: int = 2000) -> List[Dict[str, Any]]:
    r = requests.get(
        f"{BASE_URL}/training/history",
        params={"limit": int(limit)},
        headers=_headers(),
        timeout=_timeout,
    )
    r.raise_for_status()
    data = r.json()
    return data if isinstance(data, list) else []


def get_maintenance_status() -> Dict[str, Any]:
    r = requests.get(f"{BASE_URL}/status/maintenance", headers=_headers(), timeout=_timeout)
    r.raise_for_status()
    data = r.json()
    if isinstance(data, dict):
        return data
    return {"enabled": False, "message": ""}

def reset_training_history() -> bool:
    r = requests.post(
        f"{BASE_URL}/training/reset",
        headers=_headers(),
        timeout=_timeout,
    )
    return r.status_code == 200

def get_profile():
    r = requests.get(
        f"{BASE_URL}/auth/profile",
        headers=_headers(),
        timeout=_timeout,
    )
    return r.json() if r.status_code == 200 else None