"""Django settings.

Every environment-specific or secret value comes from environment variables
(see backend/.env.example). Nothing secret lives in this file.
"""

from pathlib import Path

from config import env

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = env.required("DJANGO_SECRET_KEY")
DEBUG = env.flag("DJANGO_DEBUG")
ALLOWED_HOSTS = env.listed("DJANGO_ALLOWED_HOSTS")

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.sessions",
    "rest_framework",
    "core",
    "audit",
    "identity",
    "catalogue",
    "positions",
    "licensing",
    "reasons",
    "stock",
    "transactions",
    "alerts",
    "oversight",
    "governance",
]

AUTH_USER_MODEL = "identity.User"
PASSWORD_HASHERS = ["django.contrib.auth.hashers.Argon2PasswordHasher"]
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 12},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "core.middleware.SessionMiddleware",  # background refreshes do not extend the session
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "core.middleware.DbContextMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env.required("DB_NAME"),
        "USER": env.required("DB_USER"),
        "PASSWORD": env.required("DB_PASSWORD"),
        "HOST": env.required("DB_HOST"),
        "PORT": env.optional("DB_PORT", "5432"),
        "CONN_MAX_AGE": 60,
        # Production must use "verify-full".
        "OPTIONS": {"sslmode": env.optional("DB_SSLMODE", "verify-full")},
    }
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LANGUAGE_CODE = "en-in"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = False
USE_TZ = True

# --- Transport and browser security ---------------------------------------
SECURE_SSL_REDIRECT = env.flag("DJANGO_SSL_REDIRECT", default=True)
SECURE_HSTS_SECONDS = 0 if DEBUG else 31_536_000
SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
# HSTS preload is a go-live decision for the production domain (roadmap Phase 6).
SILENCED_SYSTEM_CHECKS = ["security.W021"]

# --- Field-level encryption (keys come from the secrets vault in production) ----
FIELD_ENCRYPTION_KEY = env.required("FIELD_ENCRYPTION_KEY")  # Fernet key
BLIND_INDEX_KEY = env.required("BLIND_INDEX_KEY")

# --- One-time passcodes ----------------------------------------------------------
OTP_HMAC_KEY = env.required("OTP_HMAC_KEY")
# Production sender (India-resident SMS/email provider) is chosen in Phase 2.
OTP_SENDER = env.required("OTP_SENDER")

# --- Sessions: server-side, short-lived, never readable by JavaScript --------------
SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_COOKIE_AGE = 15 * 60  # 15 minutes of inactivity
SESSION_SAVE_EVERY_REQUEST = True  # each request extends the idle timeout, except a
# background refresh (header X-Background-Refresh: 1, core.middleware.SessionMiddleware)
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Strict"
CSRF_COOKIE_SAMESITE = "Strict"

# Shared across app servers so rate limits hold behind a load balancer.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.db.DatabaseCache",
        "LOCATION": "gj_cache",
    }
}

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework.authentication.SessionAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
    "DEFAULT_THROTTLE_RATES": {
        "login": "10/min",
        "otp": "10/min",
        "enrolment": "10/min",
        "lookup": "30/min",
    },
    # Set to the number of trusted proxies in production; 0 = use REMOTE_ADDR, never client headers.
    "NUM_PROXIES": 0,
    "EXCEPTION_HANDLER": "core.exceptions.rollback_on_exception",
}
