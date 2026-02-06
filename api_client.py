import requests
from typing import Optional, Dict, Any, List

BASE_URL = "https://retinoserver.onrender.com"

_timeout = 10
_token: Optional[str] = None


def _headers() -> Dict[str, str]:
    h = {"Content-Type": "application/json"}
    if _token:
        h["Authorization"] = f"Bearer {_token}"
    return h


def register_user(username: str, password: str) -> bool:
    r = requests.post(
        f"{BASE_URL}/auth/register",
        json={"username": username, "password": password},
        headers=_headers(),
        timeout=_timeout,
    )
    if r.status_code == 200:
        return True
    if r.status_code in (400, 409):
        return False
    r.raise_for_status()
    return False


def username_status(username: str) -> str:
    """
    Ожидаемые ответы:
      {"status":"ok"} или {"status":"deleted"} или {"status":"exists"}
    """
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
            headers=_headers(),
            timeout=_timeout,
        )

        if r.status_code == 200:
            data = r.json()
            _token = data.get("token")
            return True

        if r.status_code in (401, 403):
            _token = None
            return False

        _token = None
        return False

    except requests.exceptions.RequestException:
        _token = None
        return False

def logout() -> None:
    global _token
    _token = None

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