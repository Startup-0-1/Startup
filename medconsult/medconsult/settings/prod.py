from .base import *  # noqa

DEBUG = False

# In prod, DATABASE_URL must be set to Postgres
if DATABASES["default"]["ENGINE"].endswith("sqlite3"):
    raise RuntimeError("DATABASE_URL must be set to Postgres in production.")

# Secure defaults
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = True

# If you use a reverse proxy (Nginx), keep this:
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
