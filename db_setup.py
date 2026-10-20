import os
import django
from django.conf import settings

def init_django():
    if settings.configured:
        return

    DATABASE_URL = os.getenv("DATABASE_URL", "")

    if not DATABASE_URL:
        try:
            env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
            if os.path.exists(env_path):
                with open(env_path, 'r') as f:
                    for line in f:
                        if line.strip().startswith("DATABASE_URL="):
                            DATABASE_URL = line.strip().split("=", 1)[1].strip().strip('"').strip("'")
                            break
        except Exception:
            pass

    if DATABASE_URL:
        try:
            import dj_database_url
            DATABASES = {
                'default': dj_database_url.parse(DATABASE_URL, conn_max_age=600, ssl_require=True)
            }
            print(f"✅ DATABASE: NEON POSTGRES (Production) - Data Permanent", flush=True)
        except ImportError:
            DATABASES = {
                "default": {
                    "ENGINE": "django.db.backends.postgresql",
                    "NAME": os.getenv("PGDATABASE", "neondb"),
                    "USER": os.getenv("PGUSER", "neondb_owner"),
                    "PASSWORD": os.getenv("PGPASSWORD", ""),
                    "HOST": os.getenv("PGHOST", ""),
                    "PORT": os.getenv("PGPORT", "5432"),
                    "OPTIONS": {"sslmode": "require"},
                }
            }
    else:
        BASE_DIR = os.path.dirname(os.path.abspath(__file__))
        DATABASES = {
            "default": {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": os.path.join(BASE_DIR, "db.sqlite3"),
            }
        }
        print(f"⚠  DATABASE: LOCAL SQLite", flush=True)

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
