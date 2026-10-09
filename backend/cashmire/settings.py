import os
import socket
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR.parent / ".env")


def _resolve_postgres_host(default_port: str) -> str:
    # No explicit POSTGRES_HOST: probe the Compose hostname `db` (only
    # resolvable inside the `api` container) and fall back to `localhost`,
    # so the same .env works unmodified in Compose and in a local venv run.
    configured_host = os.environ.get("POSTGRES_HOST")
    if configured_host:
        return configured_host

    port = int(os.environ.get("POSTGRES_PORT", default_port))
    try:
        with socket.create_connection(("db", port), timeout=0.5):
            return "db"
    except OSError:
        return "localhost"


SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-insecure-secret-key")

DEBUG = os.environ.get("DJANGO_DEBUG", "false").lower() == "true"

ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "*").split(",")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "drf_spectacular",
    "corsheaders",
    "api.apps.ApiConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "cashmire.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "cashmire.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("POSTGRES_DB", "cashmire"),
        "USER": os.environ.get("POSTGRES_USER", "cashmire"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD", "cashmire"),
        "HOST": _resolve_postgres_host(default_port="5432"),
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Custom user model (docs/erd.md USER entity, issue #20): Django's default
# `auth.User` does not make `email` unique, and this project logs in by
# email. This must be set before the migration that creates the user table
# runs — and that migration must be `api`'s `__first__` migration, because
# every other app's own migrations that reference `AUTH_USER_MODEL` (e.g.
# `admin.0001_initial`) resolve it via `swappable_dependency`, which always
# points at app `api`'s first migration by name, not by which one actually
# creates the model. That's why `api/migrations/0001_initial.py` creates
# `User` directly rather than staying empty with a later migration doing it.
AUTH_USER_MODEL = "api.User"

CORS_ALLOWED_ORIGINS = os.environ.get(
    "DJANGO_CORS_ALLOWED_ORIGINS", "http://localhost:5173"
).split(",")

# Required for the session-cookie auth strategy (see
# docs/decisions/0003-session-cookie-auth-strategy.md): the frontend's
# `apiFetch` calls already send `credentials: "include"` on login/register,
# which only works if the browser is told the response may be read for a
# credentialed cross-origin request. django-cors-headers defaults this to
# False; without it the browser discards any `Set-Cookie` from the API.
CORS_ALLOW_CREDENTIALS = True

# Independent of the two CORS settings above, which only control whether
# the *browser* is allowed to read a cross-origin response. Django's own
# `CsrfViewMiddleware` does a separate `Origin` header check on every
# cross-origin unsafe-method request once a session user is authenticated
# (docs/decisions/0003-session-cookie-auth-strategy.md point 5) — without
# the frontend's origin listed here, every such request is rejected with
# "CSRF Failed: Origin checking failed", regardless of how correct the
# `X-CSRFToken` header and session cookie are. Reuses the same env var and
# default as CORS_ALLOWED_ORIGINS above since both describe "the frontend's
# origin(s)" and have never had a reason to differ in this project.
CSRF_TRUSTED_ORIGINS = os.environ.get(
    "DJANGO_CORS_ALLOWED_ORIGINS", "http://localhost:5173"
).split(",")

REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "api.exceptions.sanitized_exception_handler",
    # "login" scope used by LoginView's ScopedRateThrottle (issue #23,
    # AC-3) — per-IP, intentionally minimal. See
    # docs/decisions/0004-login-rate-limiting.md.
    "DEFAULT_THROTTLE_RATES": {
        "login": "5/min",
    },
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Cashmire API",
    "DESCRIPTION": "REST API for the Cashmire personal finance app.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

# Production behind the reverse proxy (compose.prod.yml): TLS is terminated
# upstream, so trust X-Forwarded-Proto and mark the cookies Secure. Left off
# in DEBUG so local HTTP development keeps working.
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
