import json
import json
import os
import random
import re
from datetime import datetime, timezone
from urllib import error as urlerror
from urllib import request as urlrequest

from werkzeug.security import check_password_hash, generate_password_hash


DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
USERS_FILE = os.path.join(DATA_DIR, "registered_users.json")

OTP_TTL_SECONDS = 300
OTP_MAX_ATTEMPTS = 5
MIN_PASSWORD_LENGTH = 8
BREVO_EMAIL_API_URL = "https://api.brevo.com/v3/smtp/email"

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_]{3,32}$")


def load_env_file():
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")

    if not os.path.isfile(env_path):
        return

    with open(env_path, "r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()

            if not line or line.startswith("#") or "=" not in line:
                continue

            if line.lower().startswith("export "):
                line = line[7:].strip()

            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")

            if key:
                # Values configured by Render (or another host) must take
                # precedence over a local .env file.
                os.environ.setdefault(key, value)


load_env_file()


def _empty_store():
    return {"users": []}


def load_users():
    os.makedirs(DATA_DIR, exist_ok=True)

    if not os.path.isfile(USERS_FILE):
        return _empty_store()

    try:
        with open(USERS_FILE, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return _empty_store()

    if not isinstance(data, dict) or not isinstance(data.get("users"), list):
        return _empty_store()

    return data


def save_users(store):
    os.makedirs(DATA_DIR, exist_ok=True)

    with open(USERS_FILE, "w", encoding="utf-8") as handle:
        json.dump(store, handle, indent=2)


def normalize_email(value):
    return (value or "").strip().lower()


def validate_email(value):
    email = normalize_email(value)

    if not EMAIL_PATTERN.match(email):
        return None, "Enter a valid email address."

    return email, None


def validate_username(value):
    username = (value or "").strip()

    if not USERNAME_PATTERN.match(username):
        return None, "Username must be 3–32 characters (letters, numbers, underscore)."

    return username, None


def validate_password(password, confirm_password):
    password = password or ""

    if len(password) < MIN_PASSWORD_LENGTH:
        return "Password must be at least 8 characters."

    if password != (confirm_password or ""):
        return "Password and confirm password do not match."

    return None


def find_user(store, username=None, email=None, phone=None):
    for user in store.get("users", []):
        if username and user.get("username", "").lower() == username.lower():
            return user

        if email and user.get("email") == email:
            return user

        if phone and user.get("phone") == phone:
            return user

    return None


def create_user(username, password, email=None, phone=None):
    store = load_users()

    user = {
        "username": username,
        "password_hash": generate_password_hash(password),
        "email": email,
        "phone": phone,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    store["users"].append(user)
    save_users(store)
    return user


def verify_registered_user(username, password):
    user = find_user(load_users(), username=username)

    if not user:
        return False

    return check_password_hash(user.get("password_hash", ""), password or "")


def generate_otp():
    return f"{random.SystemRandom().randint(0, 999999):06d}"


def hash_otp(code):
    return generate_password_hash(code)


def otp_matches(otp_hash, code):
    if not otp_hash or not code:
        return False

    return check_password_hash(otp_hash, code)


def _env(name, default=""):
    load_env_file()
    return (os.environ.get(name) or default).strip()


def _looks_like_placeholder(value):
    text = (value or "").strip().lower()
    return (
        (not text)
        or ("your-" in text)
        or ("example.com" in text)
    )


def brevo_configured():
    api_key = _env("BREVO_API_KEY")
    sender = _env("BREVO_FROM_EMAIL")

    if _looks_like_placeholder(api_key) or _looks_like_placeholder(sender):
        return False

    return True


def _brevo_error_message(error):
    """Extract Brevo's safe, human-readable error message."""
    try:
        payload = json.loads(error.read().decode("utf-8"))
        return payload.get("message") or payload.get("code") or "Request rejected by Brevo."
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, AttributeError):
        return "Request rejected by Brevo."


def send_email_otp(email, code):
    """Send a signup OTP with Brevo's HTTPS transactional-email API."""
    api_key = _env("BREVO_API_KEY")
    sender_email = _env("BREVO_FROM_EMAIL")
    sender_name = _env("BREVO_FROM_NAME", "StudentAnalytics")

    payload = {
        "sender": {"name": sender_name, "email": sender_email},
        "to": [{"email": email}],
        "subject": "Your StudentAnalytics signup code",
        "textContent": (
            f"Your StudentAnalytics verification code is {code}.\n"
            f"It expires in {OTP_TTL_SECONDS // 60} minutes.\n"
            "If you did not request this, you can ignore this email."
        ),
        "tags": ["signup-otp"],
    }
    request = urlrequest.Request(
        BREVO_EMAIL_API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "accept": "application/json",
            "api-key": api_key,
            "content-type": "application/json",
        },
        method="POST",
    )

    try:
        with urlrequest.urlopen(request, timeout=20) as response:
            if response.status not in (200, 201, 202):
                raise RuntimeError("Brevo did not accept the verification email.")
    except urlerror.HTTPError as error:
        detail = _brevo_error_message(error)
        if error.code in (401, 403):
            raise RuntimeError(
                "Brevo rejected the API key or sender email. Confirm BREVO_API_KEY "
                "and verify BREVO_FROM_EMAIL in your Brevo account."
            ) from error
        raise RuntimeError(f"Brevo could not send the verification code: {detail}") from error
    except urlerror.URLError as error:
        raise RuntimeError(
            "Could not connect to Brevo. Please try again shortly."
        ) from error
    except Exception as error:
        raise RuntimeError(
            "Could not send the verification code through Brevo."
        ) from error


def deliver_otp(email, code):
    """
    Send OTP by email when Brevo is configured.
    Otherwise keep a local/dev fallback so signup still works.
    """

    if brevo_configured():
        send_email_otp(email, code)
        return "sent", None

    print(f"[StudentAnalytics OTP] email {email}: {code}")
    return "preview", code
