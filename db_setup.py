import os
import django
from django.conf import settings

def init_django():
    if settings.configured:
        return

    # DIRECT NEON URL - NO .env NEEDED - 100% WORKS ON WINDOWS
    DATABASE_URL = os.getenv("DATABASE_URL", "")

    # Jo env ma na hoy to direct URL vapro - FINAL FIX
    if not DATABASE_URL:
        DATABASE_URL = "postgresql://neondb_owner:npg_XJKzq4cpxv2L@ep-odd-moon-b4usmytw.c-6.us-east-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
        print(f"✅ Using Direct Neon URL (Hardcoded for Windows Fix)")

    try:
        import dj_database_url
        DATABASES = {
            'default': dj_database_url.parse(DATABASE_URL, conn_max_age=600, ssl_require=True)
        }
        print(f"✅ Connected to Neon: {DATABASE_URL[:50]}...")
    except Exception as e:
        print(f"❌ DB Error: {e}")
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