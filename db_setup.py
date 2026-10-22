import os
import django
from django.conf import settings
def init_django():
if settings.configured:
return
DATABASE_URL = os.getenv(&quot;DATABASE_URL&quot;, &quot;&quot;)
if DATABASE_URL:
# NEON - Postgres (Live)
try:
import dj_database_url
DATABASES = {
&#39;default&#39;: dj_database_url.parse(DATABASE_URL, conn_max_age=600, ssl_require=True)
}
except ImportError:
# Fallback if dj-database-url not installed
DATABASES = {
&quot;default&quot;: {
&quot;ENGINE&quot;: &quot;django.db.backends.postgresql&quot;,
&quot;NAME&quot;: os.getenv(&quot;PGDATABASE&quot;, &quot;neondb&quot;),
&quot;USER&quot;: os.getenv(&quot;PGUSER&quot;, &quot;neondb_owner&quot;),
&quot;PASSWORD&quot;: os.getenv(&quot;PGPASSWORD&quot;, &quot;&quot;),
&quot;HOST&quot;: os.getenv(&quot;PGHOST&quot;, &quot;&quot;),
&quot;PORT&quot;: os.getenv(&quot;PGPORT&quot;, &quot;5432&quot;),

&quot;OPTIONS&quot;: {&quot;sslmode&quot;: &quot;require&quot;},
}
}
else:
# LOCAL - SQLite
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASES = {
&quot;default&quot;: {
&quot;ENGINE&quot;: &quot;django.db.backends.sqlite3&quot;,
&quot;NAME&quot;: os.path.join(BASE_DIR, &quot;db.sqlite3&quot;),
}
}
settings.configure(
SECRET_KEY=os.getenv(&quot;SECRET_KEY&quot;, &quot;my-super-secret-django-key-12345&quot;),
INSTALLED_APPS=[
&quot;django.contrib.contenttypes&quot;,
&quot;django.contrib.auth&quot;,
&quot;models_app&quot;,
],
DATABASES=DATABASES,
TIME_ZONE=&quot;Asia/Kolkata&quot;,
USE_TZ=True,
DEFAULT_AUTO_FIELD=&#39;django.db.models.BigAutoField&#39;
)
django.setup()
