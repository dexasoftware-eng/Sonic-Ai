import os
import hmac
import hashlib
import base64
import json
import time
from typing import Optional, Dict, Any
from config.settings import settings

SECRET_KEY = settings.SECRET_KEY.encode('utf-8')
ITERATIONS = 100000

def hash_password(password: str) -> str:
    """Hashes a password using PBKDF2-HMAC-SHA256 with a random salt."""
    salt = os.urandom(16)
    key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, ITERATIONS)
    return f"{salt.hex()}${key.hex()}"

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plain password against the stored salt$hash string."""
    try:
        salt_hex, key_hex = hashed_password.split('$')
        salt = bytes.fromhex(salt_hex)
        expected_key = bytes.fromhex(key_hex)
        derived_key = hashlib.pbkdf2_hmac('sha256', plain_password.encode('utf-8'), salt, ITERATIONS)
        return hmac.compare_digest(derived_key, expected_key)
    except Exception:
        return False

def generate_session_token(user_id: str, username: str, role: str, tenant_id: str = "default_org") -> str:
    """Generates an HMAC-signed session token containing user payload."""
    payload = {
        "user_id": user_id,
        "username": username,
        "role": role,
        "tenant_id": tenant_id,
        "iat": int(time.time()),
        "exp": int(time.time()) + (86400 * 7)  # 7 days validity
    }
    payload_bytes = json.dumps(payload, separators=(',', ':')).encode('utf-8')
    payload_b64 = base64.urlsafe_b64encode(payload_bytes).decode('utf-8').rstrip('=')
    
    signature = hmac.new(SECRET_KEY, payload_b64.encode('utf-8'), hashlib.sha256).hexdigest()
    return f"{payload_b64}.{signature}"

def decode_session_token(token: str) -> Optional[Dict[str, Any]]:
    """Decodes and validates HMAC signature of a session token."""
    try:
        parts = token.split('.')
        if len(parts) != 2:
            return None
        payload_b64, signature = parts
        expected_sig = hmac.new(SECRET_KEY, payload_b64.encode('utf-8'), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected_sig):
            return None
        
        # Add padding back if necessary
        padded_b64 = payload_b64 + '=' * (-len(payload_b64) % 4)
        payload_json = base64.urlsafe_b64decode(padded_b64.encode('utf-8')).decode('utf-8')
        payload = json.loads(payload_json)
        
        # Check expiration
        if payload.get("exp", 0) < time.time():
            return None
        return payload
    except Exception:
        return None
