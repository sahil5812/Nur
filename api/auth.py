# api/auth.py
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
import jwt
from datetime import datetime, timedelta
import os
import sys
import re
import requests
from pathlib import Path
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

import shared_state

# Add project root to path for database imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from database.db import get_user_by_email, create_user, verify_password, update_last_login

SECRET_KEY = os.getenv("JWT_SECRET", "nur-secret-key-change-this")
ALGORITHM = "HS256"

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/api/auth/google/callback")

router = APIRouter()

class LoginRequest(BaseModel):
    email: str
    password: str
    remember_me: bool = False

class RegisterRequest(BaseModel):
    email: str
    password: str
    display_name: str
    mt5_login: int
    mt5_password: str
    mt5_server: str = "MetaQuotes-Demo"

@router.get("/api/auth/check-email")
def check_email(email: str):
    email = email.lower().strip()
    # 1. Validate email format
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(pattern, email):
        return {"available": False, "reason": "invalid_format"}
    
    # Check domain TLD
    valid_tlds = ['com', 'net', 'org', 'in', 'io', 'co', 'edu', 'gov']
    tld = email.split('.')[-1]
    if tld not in valid_tlds:
        return {"available": False, "reason": "invalid_format"}
        
    # 2. Check if already registered
    user = get_user_by_email(email)
    if user:
        return {"available": False, "reason": "already_registered"}
    
    return {"available": True, "reason": None}

@router.post("/api/auth/register")
def register(request: RegisterRequest):
    # 1. Validate email format
    email = request.email.lower().strip()
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_pattern, email):
        raise HTTPException(status_code=400, detail="invalid_email")
        
    # Check domain TLD
    valid_tlds = ['com', 'net', 'org', 'in', 'io', 'co', 'edu', 'gov']
    tld = email.split('.')[-1]
    if tld not in valid_tlds:
        raise HTTPException(status_code=400, detail="invalid_email")
        
    # 2. Validate password strength
    pwd = request.password
    if len(pwd) < 8 or not re.search(r'[A-Z]', pwd) or not re.search(r'[0-9]', pwd) or not re.search(r'[!@#$%^&*]', pwd):
        raise HTTPException(status_code=400, detail="weak_password")
        
    # 3. Check if email already exists
    if get_user_by_email(email):
        raise HTTPException(status_code=400, detail="email_taken")
    
    try:
        user_id = create_user(
            email=email,
            password=request.password,
            display_name=request.display_name,
            mt5_login=request.mt5_login,
            mt5_password=request.mt5_password,
            mt5_server=request.mt5_server
        )
        return {"message": "Account created", "user_id": user_id}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to create account: {exc}")

@router.post("/api/auth/login")
def login(request: LoginRequest):
    email = request.email.lower().strip()
    # 1. Get user by email
    user = get_user_by_email(email)
    if not user:
        raise HTTPException(status_code=401, detail="account_not_found")
    
    # Check auth provider mismatch
    if user.get("auth_provider") == "google":
        raise HTTPException(status_code=400, detail="google_only_login")
        
    # 2. Verify password
    if not verify_password(request.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="wrong_password")
    
    # 3. Generate JWT token
    expire_hours = 24 * 30 if request.remember_me else 24
    expire = datetime.utcnow() + timedelta(hours=expire_hours)
    
    payload = {
        "sub": user["email"],
        "id": user["id"],
        "exp": expire
    }
    
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    
    # 4. Update last_login
    update_last_login(user["id"])
    
    # 5. Signal authentication to bot engine
    shared_state.authenticated = True
    
    # 6. Return token + user metadata
    return {
        "token": token,
        "user": {
            "email": user["email"],
            "display_name": user["display_name"],
            "mt5_login": user["mt5_login"],
            "auth_provider": "email",
            "avatar_url": None
        }
    }

@router.get("/api/auth/google")
def google_login(request: Request):
    if not GOOGLE_CLIENT_ID or GOOGLE_CLIENT_ID.startswith("your_"):
        raise HTTPException(
            status_code=503,
            detail="Google OAuth not configured. Add GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET to .env"
        )

    google_auth_url = (
        "https://accounts.google.com/o/oauth2/auth?"
        f"client_id={GOOGLE_CLIENT_ID}&"
        "response_type=code&"
        f"redirect_uri={GOOGLE_REDIRECT_URI}&"
        "scope=openid email profile&"
        "access_type=offline&"
        "prompt=select_account"
    )
    return {"auth_url": google_auth_url}

@router.get("/api/auth/google/callback")
async def google_callback(code: str, request: Request):
    # Determine redirect base
    referer = request.headers.get("referer", "")
    if "5173" in referer:
        redirect_base = "http://localhost:5173"
    else:
        redirect_base = str(request.base_url).rstrip("/")

    # Block if Google credentials not configured
    if not GOOGLE_CLIENT_ID or GOOGLE_CLIENT_ID.startswith("your_"):
        return RedirectResponse(
            f"{redirect_base}/auth/callback?error=google_not_configured"
        )

    try:
        # Exchange code for token
        token_response = requests.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "redirect_uri": GOOGLE_REDIRECT_URI,
                "grant_type": "authorization_code"
            },
            timeout=10
        )
        token_json = token_response.json()

        if "error" in token_json:
            return RedirectResponse(
                f"{redirect_base}/auth/callback?error=google_token_failed"
            )

        if "access_token" not in token_json:
            return RedirectResponse(
                f"{redirect_base}/auth/callback?error=google_error"
            )

        # Get user info from Google
        google_token = token_json["access_token"]
        user_info_response = requests.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {google_token}"},
            timeout=10
        )
        user_info = user_info_response.json()

        email = user_info.get("email", "").lower().strip()
        name = user_info.get("name", "Google User")
        picture = user_info.get("picture", "")
        google_id = user_info.get("id", "")

        if not email:
            return RedirectResponse(
                f"{redirect_base}/auth/callback?error=google_no_email"
            )

        # Check if user exists
        existing_user = get_user_by_email(email)
        if existing_user:
            # Block if this email uses password login
            if existing_user.get("auth_provider") == "email":
                return RedirectResponse(
                    f"{redirect_base}/auth/callback?error=email_uses_password"
                )
            update_last_login(existing_user["id"])
            user_id = existing_user["id"]
            display_name = existing_user["display_name"]
            mt5_login = existing_user["mt5_login"]
            avatar_url = existing_user.get("avatar_url") or picture
        else:
            # New Google user - auto register
            from database.db import create_google_user
            user_id = create_google_user(
                email=email,
                display_name=name,
                google_id=google_id,
                avatar_url=picture
            )
            display_name = name
            mt5_login = None
            avatar_url = picture

        # Generate JWT (30 day token for Google users)
        expire = datetime.utcnow() + timedelta(hours=24 * 30)
        payload = {
            "sub": email,
            "id": user_id,
            "exp": expire
        }
        jwt_token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
        shared_state.authenticated = True

        return RedirectResponse(
            f"{redirect_base}/auth/callback"
            f"?token={jwt_token}"
            f"&email={email}"
            f"&name={display_name}"
            f"&mt5_login={mt5_login or ''}"
            f"&avatar_url={avatar_url or ''}"
            f"&auth_provider=google"
        )

    except requests.exceptions.Timeout:
        return RedirectResponse(
            f"{redirect_base}/auth/callback?error=google_timeout"
        )
    except Exception as exc:
        return RedirectResponse(
            f"{redirect_base}/auth/callback?error=server_error"
        )

@router.post("/api/auth/google/onetap")
async def google_onetap(request: Request):
    body = await request.json()
    credential = body.get("credential")
    
    if not credential:
        raise HTTPException(status_code=400, detail="No credential provided")
    
    if not GOOGLE_CLIENT_ID or GOOGLE_CLIENT_ID.startswith("your_"):
        raise HTTPException(status_code=503, detail="Google OAuth not configured")
    
    try:
        # Verify the Google ID token
        id_info = id_token.verify_oauth2_token(
            credential,
            google_requests.Request(),
            GOOGLE_CLIENT_ID
        )
        
        email = id_info.get("email", "").lower().strip()
        name = id_info.get("name", "Google User")
        picture = id_info.get("picture", "")
        google_id = id_info.get("sub", "")
        
        if not email:
            raise HTTPException(status_code=400, detail="No email from Google")
        
        # Check if user exists or create new
        existing_user = get_user_by_email(email)
        if existing_user:
            if existing_user.get("auth_provider") == "email":
                raise HTTPException(
                    status_code=400, 
                    detail="email_uses_password"
                )
            update_last_login(existing_user["id"])
            user_id = existing_user["id"]
            display_name = existing_user["display_name"]
            mt5_login = existing_user["mt5_login"]
            avatar_url = existing_user.get("avatar_url") or picture
        else:
            from database.db import create_google_user
            user_id = create_google_user(
                email=email,
                display_name=name,
                google_id=google_id,
                avatar_url=picture
            )
            display_name = name
            mt5_login = None
            avatar_url = picture
        
        # Generate JWT (30 days)
        expire = datetime.utcnow() + timedelta(hours=24 * 30)
        payload = {
            "sub": email,
            "id": user_id,
            "exp": expire
        }
        jwt_token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
        shared_state.authenticated = True
        
        return {
            "token": jwt_token,
            "user": {
                "email": email,
                "display_name": display_name,
                "mt5_login": mt5_login,
                "avatar_url": avatar_url,
                "auth_provider": "google"
            }
        }
        
    except ValueError as e:
        raise HTTPException(status_code=401, detail=f"Invalid Google token: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

security = HTTPBearer()

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        user_id: int = payload.get("id")
        if email is None or user_id is None:
            raise HTTPException(status_code=401, detail="Invalid authentication token")
        
        # Get user details
        user = get_user_by_email(email)
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        # Signal authentication to bot engine on every validated request
        shared_state.authenticated = True
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Authentication token has expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid authentication token")

@router.get("/api/auth/validate")
def validate_token(current_user: dict = Depends(get_current_user)):
    return {
        "valid": True,
        "user": {
            "email": current_user["email"],
            "display_name": current_user["display_name"],
            "mt5_login": current_user["mt5_login"],
            "auth_provider": current_user.get("auth_provider", "email"),
            "avatar_url": current_user.get("avatar_url")
        }
    }

@router.post("/api/auth/refresh")
def refresh_token(current_user: dict = Depends(get_current_user)):
    expire = datetime.utcnow() + timedelta(hours=24 * 30)
    payload = {
        "sub": current_user["email"],
        "id": current_user["id"],
        "exp": expire
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return {
        "token": token,
        "user": {
            "email": current_user["email"],
            "display_name": current_user["display_name"],
            "mt5_login": current_user["mt5_login"]
        }
    }

@router.post("/api/auth/logout")
def logout():
    """De-authenticate the session and signal bot engine to go dormant."""
    shared_state.authenticated = False
    return {"status": "ok", "message": "Logged out. Bot engine entering dormant state."}
