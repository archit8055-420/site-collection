import os
import django
from django.conf import settings

def init_django():
    if settings.configured:
        return

    DATABASE_URL = os.getenv("DATABASE_URL", "")

    if DATABASE_URL:
        try:
            import dj_database_url
            DATABASES = {
                'default': dj_database_url.parse(DATABASE_URL, conn_max_age=600, ssl_require=True)
            }
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
