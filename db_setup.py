import os
import django
from django.conf import settings

def init_django():
    if settings.configured:
        return

    DATABASE_URL = os.getenv("DATABASE_URL", "")

    if DATABASE_URL:
        # NEON - Postgres (Live) - FIXED
        try:
            import dj_database_url
            DATABASES = {
                'default': dj_database_url.parse(
                    DATABASE_URL, 
                    conn_max_age=0,  # <-- FIX: 600 hati, have 0 kari - har vaar navo connection
                    conn_health_checks=True,  # <-- FIX: Health check on
                    ssl_require=True
                )
            }
            # Extra keepalive for Neon
            DATABASES['default']['CONN_MAX_AGE'] = 0
            DATABASES['default']['CONN_HEALTH_CHECKS'] = True
            DATABASES['default'].setdefault('OPTIONS', {})
            DATABASES['default']['OPTIONS'].update({
                'keepalives': 1,
                'keepalives_idle': 30,
                'keepalives_interval': 10,
                'keepalives_count': 5,
            })
        except ImportError:
            # Fallback if dj-database-url not installed
            DATABASES = {
                "default": {
                    "ENGINE": "django.db.backends.postgresql",
                    "NAME": os.getenv("PGDATABASE", "neondb"),
                    "USER": os.getenv("PGUSER", "neondb_owner"),
                    "PASSWORD": os.getenv("PGPASSWORD", ""),
                    "HOST": os.getenv("PGHOST", ""),
                    "PORT": os.getenv("PGPORT", "5432"),
                    "CONN_MAX_AGE": 0,  # <-- FIX
                    "CONN_HEALTH_CHECKS": True,  # <-- FIX
                    "OPTIONS": {
                        "sslmode": "require",
                        "keepalives": 1,
                        "keepalives_idle": 30,
                        "keepalives_interval": 10,
                        "keepalives_count": 5,
                    },
                }
            }
    else:
        # LOCAL - SQLite
        BASE_DIR = os.path.dirname(os.path.abspath(__file__))
        DATABASES = {
            "default": {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": os.path.join(BASE_DIR, "db.sqlite3"),
                "CONN_MAX_AGE": 0,
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
    
    # FIX: Close old connections on startup
    try:
        from django.db import close_old_connections
        close_old_connections()
    except:
        pass
