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
    "core",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
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
