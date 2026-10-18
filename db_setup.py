import os
import sys
print("🚀 Starting initialization...", flush=True)

import django
from django.conf import settings

def init_django():
    if settings.configured:
        print("⚠️ Django already configured", flush=True)
        return

    # ULTRA FAST: Local ma SQLite = 0.01s, Render par Neon
    USE_SQLITE = os.getenv("USE_SQLITE", "1")  # Default 1 = LOCAL FAST
    DATABASE_URL = os.getenv("DATABASE_URL", "")

    # Agar USE_SQLITE=1 hoy ya DATABASE_URL na hoy to SQLite vapro - 0.01s
    if USE_SQLITE == "1" or not DATABASE_URL:
        print("⚡ Using SQLite LOCAL - 0.01s ULTRA FAST MODE!", flush=True)
        BASE_DIR = os.path.dirname(os.path.abspath(__file__))
        DATABASES = {
            "default": {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": os.path.join(BASE_DIR, "db.sqlite3"),
            }
        }
    else:
        # Render / Production par Neon
        if not DATABASE_URL:
            DATABASE_URL = "postgresql://neondb_owner:npg_XJKzq4cpxv2L@ep-odd-moon-b4usmytw.c-6.us-east-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
            print(f"✅ Using Direct Neon URL (Hardcoded)", flush=True)

        try:
            import dj_database_url
            DATABASES = {
                'default': dj_database_url.parse(DATABASE_URL, conn_max_age=600, ssl_require=True)
            }
            print(f"✅ Parsed Neon URL: {DATABASE_URL[:60]}...", flush=True)
        except Exception as e:
            print(f"❌ DB Parse Error: {e} - Falling back to SQLite", flush=True)
            BASE_DIR = os.path.dirname(os.path.abspath(__file__))
            DATABASES = {
                "default": {
                    "ENGINE": "django.db.backends.sqlite3",
                    "NAME": os.path.join(BASE_DIR, "db.sqlite3"),
                }
            }

    settings.configure(
        SECRET_KEY=os.getenv("SECRET_KEY", "my-super-secret-django-key-12345"),
        INSTALLED_APPS=[
            "django.contrib.contenttypes",
            "django.contrib.auth",
            "models_app",
        ],
        DATABASES=DATABASES,
        TIME_ZONE="Asia/Kolkata",
        USE_TZ=True,
        DEFAULT_AUTO_FIELD='django.db.models.BigAutoField'
    )
    django.setup()
    print("✅ Django setup done", flush=True)

    # Auto create tables if SQLite (for 0.01s fast)
    if os.getenv("USE_SQLITE", "1") == "1":
        try:
            from django.core.management import call_command
            print("🔧 Creating tables if needed...", flush=True)
            call_command('migrate', '--run-syncdb', verbosity=0)
            print("✅ Tables ready", flush=True)
        except Exception as e:
            print(f"⚠️ Migrate warning: {e}", flush=True)
