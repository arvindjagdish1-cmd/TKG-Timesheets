from pathlib import Path
import environ
import os

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DJANGO_DEBUG=(bool, False),
    RECEIPT_REQUIRED_THRESHOLD=(float, 20.0),
    TIME_INCREMENT_MINUTES=(int, 15),
    MIN_WEEKDAY_HOURS=(float, 8.0),
    HIGH_HOURS_THRESHOLD=(float, 10.0),
    HIGH_HOURS_DAYS_PER_WEEK_THRESHOLD=(int, 2),
    AGGREGATION_ROUNDING_TOLERANCE=(float, 0.01),
    PAYROLL_FLAG_CELL_THRESHOLD=(float, 500.0),
    TIMESHEET_UPLOAD_MAX_MB=(int, 25),
)

# Read .env if present (works in Docker too)
if (BASE_DIR / ".env").exists():
    environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("DJANGO_SECRET_KEY", default="unsafe-dev-key")
DEBUG = env("DJANGO_DEBUG", default=False)

ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])
CSRF_TRUSTED_ORIGINS = env.list("DJANGO_CSRF_TRUSTED_ORIGINS", default=["http://localhost:8000"])

INSTALLED_APPS = [
    # Django
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",

    # Third-party
    "whitenoise.runserver_nostatic",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.microsoft",
    "simple_history",
    "django_htmx",

    # Local apps
    "apps.accounts",
    "apps.periods",
    "apps.timesheets",
    "apps.expenses",
    "apps.reviews",
    "apps.exports",
    "apps.notifications",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",

    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",

    # allauth
    "allauth.account.middleware.AccountMiddleware",

    # HTMX
    "django_htmx.middleware.HtmxMiddleware",

    # audit trail
    "simple_history.middleware.HistoryRequestMiddleware",
]

ROOT_URLCONF = "tkg_te.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",  # required by allauth
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "tkg_te.wsgi.application"

DATABASES = {
    "default": env.db("DATABASE_URL", default="sqlite:///db.sqlite3")
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "America/Chicago"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
STORAGES = {
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

MEDIA_URL = "/media/"
MEDIA_ROOT = env("MEDIA_ROOT", default=str(BASE_DIR / "media"))

EXPORT_ROOT = env("EXPORT_ROOT", default=str(BASE_DIR / "exports"))
TIMESHEET_TEMPLATE_PATH = env("TIMESHEET_TEMPLATE_PATH", default=str(BASE_DIR / "apps/exports/templates/Template TIMESHEET.xlsx"))

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# -------------------------
# Custom user model
# -------------------------
AUTH_USER_MODEL = "accounts.User"

# -------------------------
# Allauth configuration
# -------------------------
SITE_ID = 1

AUTHENTICATION_BACKENDS = (
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
)

LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/accounts/login/"

ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_USERNAME_REQUIRED = False
ACCOUNT_AUTHENTICATION_METHOD = "email"
ACCOUNT_EMAIL_VERIFICATION = "none"
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_USER_MODEL_USERNAME_FIELD = None

SOCIALACCOUNT_AUTO_SIGNUP = True
SOCIALACCOUNT_QUERY_EMAIL = True
SOCIALACCOUNT_LOGIN_ON_GET = True

# Microsoft provider config:
MICROSOFT_TENANT = env("MICROSOFT_TENANT", default="common")
MICROSOFT_CLIENT_ID = env("MICROSOFT_CLIENT_ID", default="")
MICROSOFT_CLIENT_SECRET = env("MICROSOFT_CLIENT_SECRET", default="")

# Option A (recommended for infra-as-code): configure app creds in settings
# Option B: create a SocialApp record in Django admin
SOCIALACCOUNT_PROVIDERS = {
    "microsoft": {
        "TENANT": MICROSOFT_TENANT,
        "SCOPE": ["openid", "email", "profile", "User.Read"],
        "AUTH_PARAMS": {"prompt": "select_account"},
        # APP config removed - use Django admin SocialApp instead to avoid conflicts
    }
}

# Enforce domain/tenant restrictions in our adapter
SOCIALACCOUNT_ADAPTER = "apps.accounts.adapters.DomainRestrictedSocialAccountAdapter"
ALLOWED_EMAIL_DOMAINS = env.list("ALLOWED_EMAIL_DOMAINS", default=[])
ALLOWED_TENANT_IDS = env.list("ALLOWED_TENANT_IDS", default=[])

# -------------------------
# App rules
# -------------------------
RECEIPT_REQUIRED_THRESHOLD = env("RECEIPT_REQUIRED_THRESHOLD")
TIME_INCREMENT_MINUTES = env("TIME_INCREMENT_MINUTES")
MIN_WEEKDAY_HOURS = env("MIN_WEEKDAY_HOURS")
HIGH_HOURS_THRESHOLD = env("HIGH_HOURS_THRESHOLD")
HIGH_HOURS_DAYS_PER_WEEK_THRESHOLD = env("HIGH_HOURS_DAYS_PER_WEEK_THRESHOLD")
AGGREGATION_ROUNDING_TOLERANCE = env("AGGREGATION_ROUNDING_TOLERANCE")
PAYROLL_FLAG_CELL_THRESHOLD = env("PAYROLL_FLAG_CELL_THRESHOLD")
TIMESHEET_UPLOAD_MAX_MB = env("TIMESHEET_UPLOAD_MAX_MB")

# -------------------------
# Email
# -------------------------
EMAIL_BACKEND = env("EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend")
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="no-reply@localhost")

# Optional SMTP settings
EMAIL_HOST = env("EMAIL_HOST", default="")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)

# -------------------------
# Celery
# -------------------------
CELERY_BROKER_URL = env("CELERY_BROKER_URL", default=env("REDIS_URL", default="redis://localhost:6379/0"))
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", default=env("REDIS_URL", default="redis://localhost:6379/0"))
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_ALWAYS_EAGER = False  # keep False; set True only for tests

# -------------------------
# Reverse proxy / HTTPS hardening
# -------------------------
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Production security settings (auto-enabled when DEBUG=False)
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000  # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_BROWSER_XSS_FILTER = True
    X_FRAME_OPTIONS = "DENY"

# -------------------------
# Logging
# -------------------------
LOG_LEVEL = env("LOG_LEVEL", default="INFO")
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": LOG_LEVEL,
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": LOG_LEVEL,
            "propagate": False,
        },
        "allauth": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "apps.accounts": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "apps.accounts.adapters": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "apps": {
            "handlers": ["console"],
            "level": "DEBUG" if DEBUG else "INFO",
            "propagate": False,
        },
    },
}
