from .base import *  # noqa

DEBUG = True
ALLOWED_HOSTS = ["*"]

# Dev-friendly cookies (HTTPS not required locally)
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SECURE_SSL_REDIRECT = False
