import os
import time
import hmac
import hashlib
import json
import base64
import random
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, Tuple
import jwt
from fastapi import HTTPException, status

JWT_SECRET = os.getenv("JWT_SECRET", "linli-tool-secret-jwt-key-development-2026")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_DAYS = 7

HMAC_SECRET = os.getenv("HMAC_SECRET", "linli-tool-hmac-invitation-secret-key-2026")
INVITATION_EXPIRE_HOURS = 48

OTP_TTL_SECONDS = 180
MAX_ATTEMPTS = 3
DAILY_LIMIT = 5


class OTPStore:
    """In-Memory OTP Store with TTL and rate limiting."""

    def __init__(self):
        # phone -> {"otp": str, "expires_at": float, "attempts": int}
        self._otps: Dict[str, Dict[str, Any]] = {}
        # phone -> list of timestamps
        self._request_history: Dict[str, list] = {}

    def can_request_otp(self, phone: str) -> Tuple[bool, str]:
        now = time.time()
        # Clean history older than 24 hours
        history = [t for t in self._request_history.get(phone, []) if now - t < 86400]
        self._request_history[phone] = history

        if len(history) >= DAILY_LIMIT:
            return False, "24小時內發送驗證碼已達上限 (5次)，請稍後再試。"
        return True, ""

    def generate_otp(self, phone: str) -> str:
        code = f"{random.randint(100000, 999999)}"
        now = time.time()

        # Update history
        if phone not in self._request_history:
            self._request_history[phone] = []
        self._request_history[phone].append(now)

        # Store OTP
        self._otps[phone] = {
            "otp": code,
            "expires_at": now + OTP_TTL_SECONDS,
            "attempts": 0,
        }
        return code

    def verify_otp(self, phone: str, input_otp: str) -> Tuple[bool, str]:
        now = time.time()
        record = self._otps.get(phone)

        if not record:
            return False, "驗證碼不存在或已失效，請重新發送。"

        if now > record["expires_at"]:
            del self._otps[phone]
            return False, "驗證碼已過期，請重新發送。"

        if record["attempts"] >= MAX_ATTEMPTS:
            del self._otps[phone]
            return False, "驗證碼錯誤次數過多，已失效，請重新發送。"

        if record["otp"] != input_otp:
            record["attempts"] += 1
            remaining = MAX_ATTEMPTS - record["attempts"]
            if remaining <= 0:
                del self._otps[phone]
                return False, "驗證碼輸入錯誤超過3次，已強制失效。"
            return False, f"驗證碼錯誤，剩餘嘗試次數：{remaining} 次。"

        # Verification succeeded
        del self._otps[phone]
        return True, "驗證成功"


otp_store = OTPStore()


class AuthService:
    """Authentication and Social Trust Service."""

    @staticmethod
    def send_otp(phone: str) -> Tuple[str, int]:
        can_send, err = otp_store.can_request_otp(phone)
        if not can_send:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=err)

        code = otp_store.generate_otp(phone)
        return code, OTP_TTL_SECONDS

    @staticmethod
    def verify_otp(phone: str, otp: str) -> bool:
        ok, msg = otp_store.verify_otp(phone, otp)
        if not ok:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)
        return True

    @staticmethod
    def create_access_token(user_id: int, community_id: Optional[int] = None) -> str:
        expire = datetime.now(timezone.utc) + timedelta(days=JWT_EXPIRATION_DAYS)
        payload = {
            "sub": str(user_id),
            "user_id": user_id,
            "community_id": community_id,
            "exp": expire,
        }
        return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

    @staticmethod
    def decode_access_token(token: str) -> Dict[str, Any]:
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            return payload
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token已過期，請重新登入",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except jwt.PyJWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="無效的認證Token",
                headers={"WWW-Authenticate": "Bearer"},
            )

    @staticmethod
    def generate_invitation_token(inviter_id: int, community_id: int) -> Tuple[str, datetime]:
        expires_at = datetime.now(timezone.utc) + timedelta(hours=INVITATION_EXPIRE_HOURS)
        payload = {
            "inviter_id": inviter_id,
            "community_id": community_id,
            "exp": int(expires_at.timestamp()),
        }
        payload_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")
        payload_b64 = base64.urlsafe_b64encode(payload_bytes).decode("utf-8").rstrip("=")

        signature = hmac.new(
            HMAC_SECRET.encode("utf-8"), payload_b64.encode("utf-8"), hashlib.sha256
        ).hexdigest()

        token = f"{payload_b64}.{signature}"
        return token, expires_at

    @staticmethod
    def verify_invitation_token(token: str) -> Dict[str, Any]:
        """Verify invitation token HMAC signature and expiration."""
        parts = token.split(".")
        if len(parts) != 2:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="邀請碼格式無效"
            )

        payload_b64, signature = parts[0], parts[1]

        # Verify signature
        expected_sig = hmac.new(
            HMAC_SECRET.encode("utf-8"), payload_b64.encode("utf-8"), hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(signature, expected_sig):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="邀請碼簽章無效或遭竄改"
            )

        # Decode payload
        try:
            padded_b64 = payload_b64 + "=" * (-len(payload_b64) % 4)
            payload_json = base64.urlsafe_b64decode(padded_b64).decode("utf-8")
            payload = json.loads(payload_json)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="邀請碼資料解析失敗"
            )

        # Check expiration
        now_ts = int(time.time())
        if payload.get("exp", 0) < now_ts:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="邀請碼已過期"
            )

        return payload
