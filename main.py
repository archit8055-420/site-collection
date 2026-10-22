import os, datetime, csv, io, secrets, hashlib, traceback, requests, asyncio
print(&quot;�� FINAL VERAVAL TRACKER Loading...&quot;, flush=True)
os.environ[&quot;DJANGO_ALLOW_ASYNC_UNSAFE&quot;] = &quot;true&quot;
from nicegui import ui, app, run
CACHE = {&quot;users&quot;: {}, &quot;areas&quot;: {}, &quot;pwd_verified&quot;: {}}
from db_setup import init_django
init_django()
from zoneinfo import ZoneInfo
IST = ZoneInfo(&quot;Asia/Kolkata&quot;)
def today_ist(): return datetime.datetime.now(IST).date()
from models_app.models import AppUser, SavedArea, DailyReport
try:
from models_app.models import SavedLabour
HAS_LABOUR_MODEL = True
except:
HAS_LABOUR_MODEL = False
from django.db import connection
def ensure_neon_fast():
# SAFE VERSION - Works for both Postgres (Neon) and SQLite (Local)
try:
with connection.cursor() as cursor:
# Check if tables exist - Compatible with both DBs
try:
# Postgres (Neon) way
cursor.execute(&quot;SELECT to_regclass(&#39;models_app_dailyreport&#39;);&quot;)
table_exists = cursor.fetchone()[0] is not None
except Exception:
# SQLite way - check sqlite_master
try:
cursor.execute(&quot;SELECT name FROM sqlite_master WHERE type=&#39;table&#39; AND
name=&#39;models_app_dailyreport&#39;;&quot;)
table_exists = cursor.fetchone() is not None
except Exception:
table_exists = True # Assume exists, let Django handle
if not table_exists:
print(&quot;⏳ Tables not yet created - skipping ALTER, will be created by Django&quot;, flush=True)
return
# Indexes - work on both
try:
cursor.execute(&quot;CREATE INDEX IF NOT EXISTS idx_fast_email ON models_app_appuser (email);&quot;)
except Exception:
pass
try:
cursor.execute(&quot;CREATE INDEX IF NOT EXISTS idx_fast_user_date ON models_app_dailyreport (user_id,
report_date);&quot;)
except Exception:
pass
try:
cursor.execute(&quot;CREATE INDEX IF NOT EXISTS idx_fast_date ON models_app_dailyreport
(report_date);&quot;)
# Ensure ConnectionEntry table exists (for old Neon DB without migration)
try:
# Postgres
cursor.execute(&quot;&quot;&quot;
CREATE TABLE IF NOT EXISTS models_app_connectionentry (
id BIGSERIAL PRIMARY KEY,
report_date DATE NOT NULL,
connection_no VARCHAR(100) NOT NULL DEFAULT &#39;&#39;,
name VARCHAR(150) NOT NULL DEFAULT &#39;&#39;,
mobile VARCHAR(20) NOT NULL DEFAULT &#39;&#39;,
area_name VARCHAR(100) NOT NULL DEFAULT &#39;&#39;,
created_at TIMESTAMPTZ DEFAULT NOW(),
user_id BIGINT NOT NULL REFERENCES models_app_appuser (id) ON DELETE CASCADE,

report_id BIGINT REFERENCES models_app_dailyreport (id) ON DELETE CASCADE
);
&quot;&quot;&quot;)
except Exception as e:
print(f&quot;Conn table create (pg) skip: {e}&quot;)
try:
# SQLite fallback
cursor.execute(&quot;&quot;&quot;
CREATE TABLE IF NOT EXISTS models_app_connectionentry (
id INTEGER PRIMARY KEY AUTOINCREMENT,
report_date DATE NOT NULL,
connection_no VARCHAR(100) NOT NULL DEFAULT &#39;&#39;,
name VARCHAR(150) NOT NULL DEFAULT &#39;&#39;,
mobile VARCHAR(20) NOT NULL DEFAULT &#39;&#39;,
area_name VARCHAR(100) NOT NULL DEFAULT &#39;&#39;,
created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
user_id INTEGER NOT NULL,
report_id INTEGER
);
&quot;&quot;&quot;)
except Exception as e:
print(f&quot;Conn table create (sqlite) skip: {e}&quot;)
except Exception:
pass
try:
cursor.execute(&quot;CREATE INDEX IF NOT EXISTS idx_fast_area ON models_app_savedarea (user_id);&quot;)
except Exception:
pass
# Add columns - Postgres uses ADD COLUMN IF NOT EXISTS, SQLite doesn&#39;t support IF NOT EXISTS for
column
is_sqlite = connection.vendor == &#39;sqlite&#39;
if is_sqlite:
# SQLite - try to add, ignore if exists - ALL MISSING COLUMNS
for sql in [
&quot;ALTER TABLE models_app_appuser ADD COLUMN created_at DATETIME DEFAULT CURRENT_TIMESTAMP;&quot;,
&quot;ALTER TABLE models_app_savedarea ADD COLUMN created_at DATETIME DEFAULT CURRENT_TIMESTAMP;&quot;,
&quot;ALTER TABLE models_app_dailyreport ADD COLUMN labour_name VARCHAR(150) DEFAULT &#39;&#39;;&quot;,
&quot;ALTER TABLE models_app_dailyreport ADD COLUMN connection VARCHAR(100) DEFAULT &#39;&#39;;&quot;,
&quot;ALTER TABLE models_app_appuser ADD COLUMN default_area_name VARCHAR(255) DEFAULT &#39;&#39;;&quot;,
&quot;ALTER TABLE models_app_appuser ADD COLUMN default_labour_name VARCHAR(255) DEFAULT &#39;&#39;;&quot;,
&quot;ALTER TABLE models_app_appuser ADD COLUMN default_connection VARCHAR(100) DEFAULT &#39;&#39;;&quot;,
&quot;ALTER TABLE models_app_dailyreport ADD COLUMN qty_150mm REAL DEFAULT 0;&quot;,
&quot;ALTER TABLE models_app_dailyreport ADD COLUMN total_pvc REAL DEFAULT 0;&quot;,
&quot;ALTER TABLE models_app_dailyreport ADD COLUMN total_di REAL DEFAULT 0;&quot;,
&quot;ALTER TABLE models_app_dailyreport ADD COLUMN extra_63mm REAL DEFAULT 0;&quot;,
&quot;ALTER TABLE models_app_dailyreport ADD COLUMN extra_90mm REAL DEFAULT 0;&quot;,
&quot;ALTER TABLE models_app_dailyreport ADD COLUMN extra_110mm REAL DEFAULT 0;&quot;,
&quot;ALTER TABLE models_app_dailyreport ADD COLUMN extra_150mm REAL DEFAULT 0;&quot;,
&quot;ALTER TABLE models_app_dailyreport ADD COLUMN total_mtr REAL DEFAULT 0;&quot;,
&quot;ALTER TABLE models_app_dailyreport ADD COLUMN count_63mm INTEGER DEFAULT 0;&quot;,
&quot;ALTER TABLE models_app_dailyreport ADD COLUMN count_90mm INTEGER DEFAULT 0;&quot;,
&quot;ALTER TABLE models_app_dailyreport ADD COLUMN count_110mm INTEGER DEFAULT 0;&quot;,
&quot;ALTER TABLE models_app_dailyreport ADD COLUMN count_150mm INTEGER DEFAULT 0;&quot;,
&quot;ALTER TABLE models_app_dailyreport ADD COLUMN created_at DATETIME DEFAULT
CURRENT_TIMESTAMP;&quot;,
&quot;ALTER TABLE models_app_savedlabour ADD COLUMN created_at DATETIME DEFAULT
CURRENT_TIMESTAMP;&quot;,
]:
try:
cursor.execute(sql)
except Exception:
pass
# Create labour table for SQLite
try:

cursor.execute(&quot;&quot;&quot;
CREATE TABLE IF NOT EXISTS models_app_savedlabour (
id INTEGER PRIMARY KEY AUTOINCREMENT,
user_id INTEGER NOT NULL,
labour_name VARCHAR(150) NOT NULL,
created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
UNIQUE(user_id, labour_name)
);
&quot;&quot;&quot;)
except Exception as e:
print(f&quot;Labour table create skip: {e}&quot;)
else:
# Postgres (Neon) - Fix created_at missing + all extra columns
# AppUser table
cursor.execute(&quot;ALTER TABLE models_app_appuser ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ
DEFAULT NOW();&quot;)
cursor.execute(&quot;ALTER TABLE models_app_appuser ADD COLUMN IF NOT EXISTS default_report_title
VARCHAR(255) DEFAULT &#39;Veraval site&#39;;&quot;)
cursor.execute(&quot;ALTER TABLE models_app_appuser ADD COLUMN IF NOT EXISTS default_area_name
VARCHAR(255) DEFAULT &#39;&#39;;&quot;)
cursor.execute(&quot;ALTER TABLE models_app_appuser ADD COLUMN IF NOT EXISTS default_labour_name
VARCHAR(255) DEFAULT &#39;&#39;;&quot;)
cursor.execute(&quot;ALTER TABLE models_app_appuser ADD COLUMN IF NOT EXISTS default_connection
VARCHAR(100) DEFAULT &#39;&#39;;&quot;)
cursor.execute(&quot;ALTER TABLE models_app_dailyreport ADD COLUMN IF NOT EXISTS connection
VARCHAR(100) DEFAULT &#39;&#39;;&quot;)
cursor.execute(&quot;ALTER TABLE models_app_dailyreport ADD COLUMN IF NOT EXISTS labour_name
VARCHAR(150) DEFAULT &#39;&#39;;&quot;)
cursor.execute(&quot;ALTER TABLE models_app_appuser ADD COLUMN IF NOT EXISTS default_area_name
VARCHAR(255) DEFAULT &#39;&#39;;&quot;)
cursor.execute(&quot;ALTER TABLE models_app_appuser ADD COLUMN IF NOT EXISTS default_labour_name
VARCHAR(255) DEFAULT &#39;&#39;;&quot;)
cursor.execute(&quot;ALTER TABLE models_app_appuser ADD COLUMN IF NOT EXISTS default_connection
VARCHAR(100) DEFAULT &#39;&#39;;&quot;)
cursor.execute(&quot;ALTER TABLE models_app_dailyreport ADD COLUMN IF NOT EXISTS connection
VARCHAR(100) DEFAULT &#39;&#39;;&quot;)
cursor.execute(&quot;ALTER TABLE models_app_dailyreport ADD COLUMN IF NOT EXISTS labour_name
VARCHAR(150) DEFAULT &#39;&#39;;&quot;)
# SavedArea
cursor.execute(&quot;ALTER TABLE models_app_savedarea ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ
DEFAULT NOW();&quot;)
# SavedLabour
cursor.execute(&quot;ALTER TABLE models_app_savedlabour ADD COLUMN IF NOT EXISTS created_at
TIMESTAMPTZ DEFAULT NOW();&quot;)
# DailyReport
cursor.execute(&quot;ALTER TABLE models_app_dailyreport ADD COLUMN IF NOT EXISTS labour_name
VARCHAR(150) DEFAULT &#39;&#39;;&quot;)
cursor.execute(&quot;ALTER TABLE models_app_dailyreport ADD COLUMN IF NOT EXISTS qty_150mm DOUBLE
PRECISION DEFAULT 0;&quot;)
cursor.execute(&quot;ALTER TABLE models_app_dailyreport ADD COLUMN IF NOT EXISTS total_pvc DOUBLE
PRECISION DEFAULT 0;&quot;)
cursor.execute(&quot;ALTER TABLE models_app_dailyreport ADD COLUMN IF NOT EXISTS total_di DOUBLE
PRECISION DEFAULT 0;&quot;)
cursor.execute(&quot;ALTER TABLE models_app_dailyreport ADD COLUMN IF NOT EXISTS extra_63mm DOUBLE
PRECISION DEFAULT 0;&quot;)
cursor.execute(&quot;ALTER TABLE models_app_dailyreport ADD COLUMN IF NOT EXISTS extra_90mm DOUBLE
PRECISION DEFAULT 0;&quot;)
cursor.execute(&quot;ALTER TABLE models_app_dailyreport ADD COLUMN IF NOT EXISTS extra_110mm DOUBLE
PRECISION DEFAULT 0;&quot;)
cursor.execute(&quot;ALTER TABLE models_app_dailyreport ADD COLUMN IF NOT EXISTS extra_150mm DOUBLE
PRECISION DEFAULT 0;&quot;)
cursor.execute(&quot;ALTER TABLE models_app_dailyreport ADD COLUMN IF NOT EXISTS total_mtr DOUBLE
PRECISION DEFAULT 0;&quot;)
cursor.execute(&quot;ALTER TABLE models_app_dailyreport ADD COLUMN IF NOT EXISTS count_63mm INTEGER

DEFAULT 0;&quot;)
cursor.execute(&quot;ALTER TABLE models_app_dailyreport ADD COLUMN IF NOT EXISTS count_90mm INTEGER
DEFAULT 0;&quot;)
cursor.execute(&quot;ALTER TABLE models_app_dailyreport ADD COLUMN IF NOT EXISTS count_110mm INTEGER
DEFAULT 0;&quot;)
cursor.execute(&quot;ALTER TABLE models_app_dailyreport ADD COLUMN IF NOT EXISTS count_150mm INTEGER
DEFAULT 0;&quot;)
cursor.execute(&quot;ALTER TABLE models_app_dailyreport ADD COLUMN IF NOT EXISTS created_at
TIMESTAMPTZ DEFAULT NOW();&quot;)
cursor.execute(&quot;&quot;&quot;
CREATE TABLE IF NOT EXISTS models_app_savedlabour (
id BIGSERIAL PRIMARY KEY,
user_id BIGINT NOT NULL REFERENCES models_app_appuser(id) ON DELETE CASCADE,
labour_name VARCHAR(150) NOT NULL,
created_at TIMESTAMPTZ DEFAULT NOW(),
UNIQUE(user_id, labour_name)
);
&quot;&quot;&quot;)
# Fix savedlabour created_at if table existed before
cursor.execute(&quot;ALTER TABLE models_app_savedlabour ADD COLUMN IF NOT EXISTS created_at
TIMESTAMPTZ DEFAULT NOW();&quot;)
print(&quot;✅ FAST INDEX OK - Point values handled by FloatField&quot;, flush=True)
except Exception as e:
print(f&quot;Index skip (safe): {e}&quot;, flush=True)
ensure_neon_fast()
try:
from models_app.models import PasswordResetToken
HAS_TOKEN_MODEL = True
except:
HAS_TOKEN_MODEL = False
from django.contrib.auth.hashers import make_password, check_password
from django.db.models import Sum
from django.utils import timezone
PORT = int(os.getenv(&quot;PORT&quot;, &quot;8080&quot;))
STORAGE_SECRET = os.getenv(&quot;STORAGE_SECRET&quot;, &quot;my_persistent_secret_key_123&quot;)
def is_valid_6digit(pwd):
return isinstance(pwd, str) and len(pwd)==6 and pwd.isdigit()
@app.get(&quot;/health&quot;)
def health_check():
return {&quot;status&quot;:&quot;ok&quot;,&quot;mode&quot;:&quot;VERAVAL TRACKER - 63,90,110,150&quot;}
def get_q(report, field, default=0):
try:
return getattr(report, field, default) or 0
except:
return default
def generate_single_csv(report):
output = io.StringIO()
writer = csv.writer(output)
writer.writerow([report.report_title])
conn = get_q(report, &#39;connection&#39;, &#39;&#39;)
writer.writerow([f&quot;Date: {report.report_date.strftime(&#39;%d-%m-%Y&#39;)}&quot;, f&quot;Area: {report.area_name}&quot;, f&quot;Labour:
{get_q(report, &#39;labour_name&#39;, &#39;&#39;)}&quot;, f&quot;Connection: {conn}&quot;])
writer.writerow([])
ex63 = get_q(report,&#39;extra_63mm&#39;,0); ex90 = get_q(report,&#39;extra_90mm&#39;,0); ex110 =
get_q(report,&#39;extra_110mm&#39;,0); ex150 = get_q(report,&#39;extra_150mm&#39;,0)
writer.writerow([&quot;PVC PIPES&quot;])
writer.writerow([&quot;Sr.No&quot;, &quot;Pipe Dia&quot;, &quot;Quantity&quot;, &quot;UNIT&quot;, &quot;Pipe MTR&quot;, &quot;Extra MTR&quot;, &quot;Total MTR&quot;])
m63 = get_q(report,&#39;qty_63mm&#39;)*6; m90 = get_q(report,&#39;qty_90mm&#39;)*6; m110 = get_q(report,&#39;qty_110mm&#39;)*6

writer.writerow([1, &quot;63MM PVC&quot;, get_q(report,&#39;qty_63mm&#39;), &quot;6MTR per PIPES&quot;, f&quot;{m63} MTR&quot;, f&quot;{ex63} MTR&quot;,
f&quot;{m63+ex63} MTR&quot;])
writer.writerow([2, &quot;90MM PVC&quot;, get_q(report,&#39;qty_90mm&#39;), &quot;6MTR per PIPES&quot;, f&quot;{m90} MTR&quot;, f&quot;{ex90} MTR&quot;,
f&quot;{m90+ex90} MTR&quot;])
writer.writerow([3, &quot;110MM PVC&quot;, get_q(report,&#39;qty_110mm&#39;), &quot;6MTR per PIPES&quot;, f&quot;{m110} MTR&quot;, f&quot;{ex110} MTR&quot;,
f&quot;{m110+ex110} MTR&quot;])
pvc = get_q(report,&#39;qty_63mm&#39;)+get_q(report,&#39;qty_90mm&#39;)+get_q(report,&#39;qty_110mm&#39;)
pvc_mtr = m63+m90+m110
pvc_extra = ex63+ex90+ex110
writer.writerow([f&quot;PVC Total: {pvc} Qty | Pipe:{pvc_mtr} + Extra:{pvc_extra} = Total:{pvc_mtr+pvc_extra}
MTR&quot;])
writer.writerow([])
writer.writerow([&quot;DI PIPES&quot;])
writer.writerow([&quot;Sr.No&quot;, &quot;Pipe Dia&quot;, &quot;Quantity&quot;, &quot;UNIT&quot;, &quot;Pipe MTR&quot;, &quot;Extra MTR&quot;, &quot;Total MTR&quot;])
di = get_q(report,&#39;qty_150mm&#39;)
di_mtr = di*5.5
writer.writerow([1, &quot;150MM DI&quot;, di, &quot;5.5MTR&quot;, f&quot;{di_mtr} MTR&quot;, f&quot;{ex150} MTR&quot;, f&quot;{di_mtr+ex150} MTR&quot;])
writer.writerow([f&quot;DI Total: {di} Qty | Pipe:{di_mtr} + Extra:{ex150} = Total:{di_mtr+ex150} MTR&quot;])
writer.writerow([])
grand_mtr = get_q(report,&#39;total_mtr&#39;, pvc_mtr+di_mtr+pvc_extra+ex150)
writer.writerow([f&quot;GRAND TOTAL MTR: {grand_mtr} MTR (Pipe + Extra)&quot;])
return output.getvalue().encode(&quot;utf-8&quot;)
def generate_single_excel(report):
try:
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
wb = Workbook(); ws = wb.active; ws.title = &quot;Report&quot;
thin = Border(left=Side(style=&#39;thin&#39;), right=Side(style=&#39;thin&#39;), top=Side(style=&#39;thin&#39;),
bottom=Side(style=&#39;thin&#39;))
hdr_fill = PatternFill(start_color=&quot;10B981&quot;, end_color=&quot;10B981&quot;, fill_type=&quot;solid&quot;)
hdr_font = Font(bold=True, color=&quot;FFFFFF&quot;, size=11)
ex63 = get_q(report,&#39;extra_63mm&#39;,0); ex90 = get_q(report,&#39;extra_90mm&#39;,0); ex110 =
get_q(report,&#39;extra_110mm&#39;,0); ex150 = get_q(report,&#39;extra_150mm&#39;,0)
ws.merge_cells(&#39;A1:G1&#39;); ws[&#39;A1&#39;] = report.report_title; ws[&#39;A1&#39;].font = Font(bold=True, size=14);
ws[&#39;A1&#39;].alignment = Alignment(horizontal=&#39;center&#39;)
ws.merge_cells(&#39;A2:G2&#39;); ws[&#39;A2&#39;] = f&quot;Date: {report.report_date.strftime(&#39;%d-%m-%Y&#39;)} | Area:
{report.area_name} | Labour: {get_q(report,&#39;labour_name&#39;,&#39;&#39;)} | Connection: {get_q(report,&#39;connection&#39;,&#39;&#39;)}&quot;;
ws[&#39;A2&#39;].alignment = Alignment(horizontal=&#39;center&#39;)
ws.append([]); ws.append([&quot;Sr.No&quot;, &quot;Pipe Dia&quot;, &quot;Quantity&quot;, &quot;UNIT&quot;, &quot;Pipe MTR&quot;, &quot;Extra MTR&quot;, &quot;Total MTR&quot;])
r = ws.max_row
for col in range(1,8): cell = ws.cell(row=r, column=col); cell.fill = hdr_fill; cell.font = hdr_font;
cell.alignment = Alignment(horizontal=&#39;center&#39;); cell.border = thin
for idx, (dia, qty, unit, pipe_mtr, extra) in enumerate([
(&quot;63MM PVC&quot;, get_q(report,&#39;qty_63mm&#39;), &quot;6MTR&quot;, get_q(report,&#39;qty_63mm&#39;)*6, ex63),
(&quot;90MM PVC&quot;, get_q(report,&#39;qty_90mm&#39;), &quot;6MTR&quot;, get_q(report,&#39;qty_90mm&#39;)*6, ex90),
(&quot;110MM PVC&quot;, get_q(report,&#39;qty_110mm&#39;), &quot;6MTR&quot;, get_q(report,&#39;qty_110mm&#39;)*6, ex110),
(&quot;150MM DI&quot;, get_q(report,&#39;qty_150mm&#39;), &quot;5.5MTR&quot;, get_q(report,&#39;qty_150mm&#39;)*5.5, ex150)
], start=1):
total = pipe_mtr + extra
ws.append([idx, dia, qty, unit, f&quot;{pipe_mtr} MTR&quot;, f&quot;{extra} MTR&quot;, f&quot;{total} MTR&quot;])
rr = ws.max_row
for c in range(1,8): ws.cell(row=rr, column=c).alignment = Alignment(horizontal=&#39;center&#39;);
ws.cell(row=rr, column=c).border = thin
ws.append([])
pvc = get_q(report,&#39;qty_63mm&#39;)+get_q(report,&#39;qty_90mm&#39;)+get_q(report,&#39;qty_110mm&#39;)
pvc_mtr = get_q(report,&#39;qty_63mm&#39;)*6 + get_q(report,&#39;qty_90mm&#39;)*6 + get_q(report,&#39;qty_110mm&#39;)*6
pvc_extra = ex63+ex90+ex110
di = get_q(report,&#39;qty_150mm&#39;); di_mtr = di*5.5
ws.append([&quot;&quot;, &quot;Total PVC&quot;, f&quot;{pvc} Qty&quot;, &quot;&quot;, f&quot;{pvc_mtr} MTR&quot;, f&quot;{pvc_extra} MTR&quot;, f&quot;{pvc_mtr+pvc_extra}
MTR&quot;])
ws.append([&quot;&quot;, &quot;Total DI&quot;, f&quot;{di} Qty&quot;, &quot;&quot;, f&quot;{di_mtr} MTR&quot;, f&quot;{ex150} MTR&quot;, f&quot;{di_mtr+ex150} MTR&quot;])
grand = get_q(report,&#39;total_mtr&#39;, pvc_mtr+pvc_extra+di_mtr+ex150)
ws.append([&quot;&quot;, &quot;GRAND TOTAL MTR&quot;, &quot;&quot;, &quot;&quot;, &quot;&quot;, &quot;&quot;, f&quot;{grand} MTR&quot;])

for rr in [ws.max_row-2, ws.max_row-1, ws.max_row]:
for c in range(1,8): ws.cell(row=rr, column=c).font = Font(bold=True); ws.cell(row=rr,
column=c).alignment = Alignment(horizontal=&#39;center&#39;); ws.cell(row=rr, column=c).border = thin
ws.column_dimensions[&#39;A&#39;].width = 10; ws.column_dimensions[&#39;B&#39;].width = 15;
ws.column_dimensions[&#39;C&#39;].width = 12; ws.column_dimensions[&#39;D&#39;].width = 10; ws.column_dimensions[&#39;E&#39;].width = 14;
ws.column_dimensions[&#39;F&#39;].width = 14; ws.column_dimensions[&#39;G&#39;].width = 14
out = io.BytesIO(); wb.save(out); return out.getvalue()
except Exception as e:
print(f&quot;Excel error: {e}&quot;)
return generate_single_csv(report)
def generate_single_pdf(report):
try:
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors
output = io.BytesIO(); c = canvas.Canvas(output, pagesize=A4); width, height = A4
c.setFillColor(colors.black)
c.setFont(&quot;Helvetica-Bold&quot;, 16)
c.drawCentredString(width/2, height-40, report.report_title)
c.setFont(&quot;Helvetica&quot;, 11)
c.setFillColor(colors.black)
conn = get_q(report, &#39;connection&#39;, &#39;&#39;)
c.drawCentredString(width/2, height-60, f&quot;Area: {report.area_name or &#39;No Area&#39;} | Labour:
{get_q(report,&#39;labour_name&#39;,&#39;&#39;) or &#39;No Labour&#39;} | Connection: {conn or &#39;-&#39;}&quot;)
c.drawCentredString(width/2, height-75, f&quot;Date: {report.report_date.strftime(&#39;%d-%m-%Y&#39;)}&quot;)
y = height - 110
# Extra values
ex63 = get_q(report,&#39;extra_63mm&#39;,0); ex90 = get_q(report,&#39;extra_90mm&#39;,0); ex110 =
get_q(report,&#39;extra_110mm&#39;,0); ex150 = get_q(report,&#39;extra_150mm&#39;,0)
total_mtr_field = get_q(report,&#39;total_mtr&#39;,0)
# PVC PIPES
y -= 10
c.setFillColor(colors.HexColor(&quot;#DC2626&quot;))
c.setFont(&quot;Helvetica-Bold&quot;, 14)
c.drawCentredString(width/2, y, &quot;PVC PIPES&quot;)
y -= 25
c.setFillColor(colors.HexColor(&quot;#059669&quot;)); c.rect(30, y-5, 540, 25, fill=1, stroke=0)
c.setFillColor(colors.white); c.setFont(&quot;Helvetica-Bold&quot;, 10)
c.drawString(35, y+2, &quot;Sr.No&quot;); c.drawString(70, y+2, &quot;Pipe Dia&quot;); c.drawString(135, y+2, &quot;Qty&quot;);
c.drawString(175, y+2, &quot;UNIT&quot;); c.drawString(220, y+2, &quot;Pipe MTR&quot;); c.drawString(300, y+2, &quot;Extra MTR&quot;);
c.drawString(380, y+2, &quot;Total MTR&quot;)
y -= 30; c.setFont(&quot;Helvetica&quot;, 11)
pvc_total = 0; pvc_mtr_total = 0; pvc_extra_total = 0
data = [
(&quot;63MM PVC&quot;, get_q(report,&#39;qty_63mm&#39;), &quot;6MTR&quot;, get_q(report,&#39;qty_63mm&#39;)*6, ex63),
(&quot;90MM PVC&quot;, get_q(report,&#39;qty_90mm&#39;), &quot;6MTR&quot;, get_q(report,&#39;qty_90mm&#39;)*6, ex90),
(&quot;110MM PVC&quot;, get_q(report,&#39;qty_110mm&#39;), &quot;6MTR&quot;, get_q(report,&#39;qty_110mm&#39;)*6, ex110),
]
for idx, (dia, qty, unit, mtr, extra) in enumerate(data, start=1):
if idx % 2 == 0: c.setFillColor(colors.HexColor(&quot;#ECFDF5&quot;)); c.rect(30, y-5, 540, 22, fill=1,
stroke=0)
c.setFillColor(colors.black)
total = mtr + extra
c.drawString(40, y, str(idx)); c.drawString(70, y, dia); c.drawString(135, y, str(qty));
c.drawString(175, y, unit);
c.drawString(220, y, f&quot;{mtr} MTR&quot;); c.drawString(290, y, f&quot;{extra} MTR&quot;); c.drawString(360, y,
f&quot;{total} MTR&quot;)
y -= 22
pvc_total += qty; pvc_mtr_total += mtr; pvc_extra_total += extra
y -= 5
c.setFillColor(colors.HexColor(&quot;#D1FAE5&quot;)); c.rect(30, y-5, 540, 22, fill=1, stroke=0)
c.setFillColor(colors.HexColor(&quot;#059669&quot;)); c.setFont(&quot;Helvetica-Bold&quot;, 10)
c.drawString(35, y+2, f&quot;PVC Total: {pvc_total} Qty | Pipe:{pvc_mtr_total} + Extra:{pvc_extra_total} =

{pvc_mtr_total+pvc_extra_total} MTR&quot;)
y -= 30
# DI PIPES
y -= 15
c.setFillColor(colors.HexColor(&quot;#DC2626&quot;))
c.setFont(&quot;Helvetica-Bold&quot;, 14)
c.drawCentredString(width/2, y, &quot;DI PIPES&quot;)
y -= 25
c.setFillColor(colors.HexColor(&quot;#059669&quot;)); c.rect(30, y-5, 540, 25, fill=1, stroke=0)
c.setFillColor(colors.white); c.setFont(&quot;Helvetica-Bold&quot;, 10)
c.drawString(35, y+2, &quot;Sr.No&quot;); c.drawString(70, y+2, &quot;Pipe Dia&quot;); c.drawString(135, y+2, &quot;Qty&quot;);
c.drawString(175, y+2, &quot;UNIT&quot;); c.drawString(220, y+2, &quot;Pipe MTR&quot;); c.drawString(300, y+2, &quot;Extra MTR&quot;);
c.drawString(380, y+2, &quot;Total MTR&quot;)
y -= 30; c.setFont(&quot;Helvetica&quot;, 11)
di_qty = get_q(report,&#39;qty_150mm&#39;)
di_mtr = di_qty * 5.5
di_total = di_mtr + ex150
c.setFillColor(colors.HexColor(&quot;#ECFDF5&quot;)); c.rect(30, y-5, 540, 22, fill=1, stroke=0)
c.setFillColor(colors.black)
c.drawString(40, y, &quot;1&quot;); c.drawString(70, y, &quot;150MM DI&quot;); c.drawString(135, y, str(di_qty));
c.drawString(175, y, &quot;5.5MTR&quot;);
c.drawString(220, y, f&quot;{di_mtr} MTR&quot;); c.drawString(290, y, f&quot;{ex150} MTR&quot;); c.drawString(360, y,
f&quot;{di_total} MTR&quot;)
y -= 22
y -= 5
c.setFillColor(colors.HexColor(&quot;#D1FAE5&quot;)); c.rect(30, y-5, 540, 22, fill=1, stroke=0)
c.setFillColor(colors.HexColor(&quot;#059669&quot;)); c.setFont(&quot;Helvetica-Bold&quot;, 10)
c.drawString(35, y+2, f&quot;DI Total: {di_qty} Qty | Pipe:{di_mtr} + Extra:{ex150} = {di_total} MTR&quot;)
y -= 25
# Connection info
conn_val = get_q(report, &#39;connection&#39;, &#39;&#39;)
if conn_val:
y -= 8
c.setFillColor(colors.HexColor(&quot;#FEF3C7&quot;)); c.rect(30, y-5, 540, 22, fill=1, stroke=0)
c.setFillColor(colors.HexColor(&quot;#92400E&quot;)); c.setFont(&quot;Helvetica-Bold&quot;, 11)
c.drawString(35, y+2, f&quot;Connection: {conn_val} - Total Connections: {conn_val}&quot;)
# Grand total MTR
grand_mtr = total_mtr_field if total_mtr_field&gt;0 else (pvc_mtr_total+pvc_extra_total+di_total)
c.setFillColor(colors.HexColor(&quot;#1F2937&quot;)); c.rect(30, y-5, 540, 25, fill=1, stroke=0)
c.setFillColor(colors.white); c.setFont(&quot;Helvetica-Bold&quot;, 12)
c.drawCentredString(width/2, y+2, f&quot;GRAND TOTAL MTR: {grand_mtr} MTR&quot;)
# Connection summary footer
if conn_val:
y -= 30
c.setFillColor(colors.HexColor(&quot;#F59E0B&quot;)); c.rect(30, y-5, 540, 22, fill=1, stroke=0)
c.setFillColor(colors.white); c.setFont(&quot;Helvetica-Bold&quot;, 11)
c.drawCentredString(width/2, y+2, f&quot;Total Connections in this report: {conn_val}&quot;)
c.showPage(); c.save(); return output.getvalue()
except Exception as e:
print(f&quot;PDF error: {e}&quot;)
import traceback; traceback.print_exc()
return generate_single_csv(report)
def generate_month_csv(title, period_text, t63, t90, t110, t150=0, te63=0, te90=0, te110=0, te150=0,
total_connections=0):
output = io.StringIO(); writer = csv.writer(output)
writer.writerow([title]); writer.writerow([period_text]); writer.writerow([])
writer.writerow([&quot;Sr.No&quot;, &quot;Pipe Dia&quot;, &quot;Qty&quot;, &quot;Extra&quot;, &quot;UNIT&quot;, &quot;Total MTR&quot;])
tm63 = t63*6 + te63; tm90 = t90*6 + te90; tm110 = t110*6 + te110; tm150 = t150*5.5 + te150
writer.writerow([1, &quot;63MM PVC&quot;, t63, te63, &quot;6MTR per PIPES&quot;, tm63]); writer.writerow([2, &quot;90MM PVC&quot;, t90,
te90, &quot;6MTR per PIPES&quot;, tm90]); writer.writerow([3, &quot;110MM PVC&quot;, t110, te110, &quot;6MTR per PIPES&quot;, tm110]);
writer.writerow([4, &quot;150MM DI&quot;, t150, te150, &quot;5.5MTR&quot;, tm150]); writer.writerow([])
writer.writerow([f&quot;Total PVC: {t63+t90+t110} Qty | Extra: {te63+te90+te110} MTR | Total MTR:
{tm63+tm90+tm110} MTR&quot;])

writer.writerow([f&quot;Total DI: {t150} Qty | Extra: {te150} MTR | Total MTR: {tm150} MTR&quot;])
writer.writerow([f&quot;Grand Extra: {te63+te90+te110+te150} MTR | Grand Total MTR: {tm63+tm90+tm110+tm150} MTR&quot;])
writer.writerow([f&quot;Grand Total Qty: {t63+t90+t110+t150} Qty&quot;])
writer.writerow([f&quot;Total Connections: {total_connections}&quot;])
return output.getvalue().encode(&quot;utf-8&quot;)
def generate_month_excel(title, period_text, t63, t90, t110, t150=0, te63=0, te90=0, te110=0, te150=0,
total_connections=0):
try:
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
wb = Workbook(); ws = wb.active; ws.title = &quot;Monthly&quot;
thin = Border(left=Side(style=&#39;thin&#39;), right=Side(style=&#39;thin&#39;), top=Side(style=&#39;thin&#39;),
bottom=Side(style=&#39;thin&#39;))
hdr_fill = PatternFill(start_color=&quot;10B981&quot;, end_color=&quot;10B981&quot;, fill_type=&quot;solid&quot;)
hdr_font = Font(bold=True, color=&quot;FFFFFF&quot;, size=11)
ws.merge_cells(&#39;A1:F1&#39;); ws[&#39;A1&#39;] = title; ws[&#39;A1&#39;].font = Font(bold=True, size=14); ws[&#39;A1&#39;].alignment =
Alignment(horizontal=&#39;center&#39;)
ws.merge_cells(&#39;A2:F2&#39;); ws[&#39;A2&#39;] = period_text; ws[&#39;A2&#39;].alignment = Alignment(horizontal=&#39;center&#39;)
ws.append([]); ws.append([&quot;Sr.No&quot;, &quot;Pipe Dia&quot;, &quot;Qty&quot;, &quot;Extra&quot;, &quot;UNIT&quot;, &quot;Total MTR&quot;])
r = ws.max_row
for col in range(1,7): cell = ws.cell(row=r, column=col); cell.fill = hdr_fill; cell.font = hdr_font;
cell.alignment = Alignment(horizontal=&#39;center&#39;); cell.border = thin
tm63 = t63*6 + te63; tm90 = t90*6 + te90; tm110 = t110*6 + te110; tm150 = t150*5.5 + te150
for idx, (dia, qty, extra, unit, total_mtr) in enumerate([(&quot;63MM PVC&quot;, t63, te63, &quot;6MTR per PIPES&quot;,
tm63), (&quot;90MM PVC&quot;, t90, te90, &quot;6MTR per PIPES&quot;, tm90), (&quot;110MM PVC&quot;, t110, te110, &quot;6MTR per PIPES&quot;, tm110),
(&quot;150MM DI&quot;, t150, te150, &quot;5.5MTR&quot;, tm150)], start=1):
ws.append([idx, dia, qty, extra, unit, total_mtr]); rr = ws.max_row
for col in range(1,7): ws.cell(row=rr, column=col).alignment = Alignment(horizontal=&#39;center&#39;);
ws.cell(row=rr, column=col).border = thin
ws.append([]); ws.append([&quot;&quot;, &quot;Total PVC&quot;, f&quot;{t63+t90+t110} Qty&quot;, f&quot;{te63+te90+te110} MTR&quot;, &quot;&quot;,
f&quot;{tm63+tm90+tm110} MTR&quot;]); ws.append([&quot;&quot;, &quot;Total DI&quot;, f&quot;{t150} Qty&quot;, f&quot;{te150} MTR&quot;, &quot;&quot;, f&quot;{tm150} MTR&quot;]);
ws.append([&quot;&quot;, &quot;Grand Extra&quot;, f&quot;{te63+te90+te110+te150} MTR&quot;, &quot;&quot;, &quot;&quot;, f&quot;{tm63+tm90+tm110+tm150} MTR&quot;]);
ws.append([&quot;&quot;, &quot;Grand Total&quot;, f&quot;{t63+t90+t110+t150} Qty&quot;, &quot;&quot;, &quot;&quot;, &quot;&quot;]); ws.append([&quot;&quot;, &quot;Total Connections&quot;,
f&quot;{total_connections}&quot;, &quot;&quot;, &quot;&quot;, &quot;&quot;])
for rr in range(ws.max_row-4, ws.max_row+1):
for col in range(1,6):
try:
ws.cell(row=rr, column=col).font = Font(bold=True); ws.cell(row=rr, column=col).alignment =
Alignment(horizontal=&#39;center&#39;); ws.cell(row=rr, column=col).border = thin
except:
pass
ws.column_dimensions[&#39;A&#39;].width = 12; ws.column_dimensions[&#39;B&#39;].width = 18;
ws.column_dimensions[&#39;C&#39;].width = 18; ws.column_dimensions[&#39;D&#39;].width = 15; ws.column_dimensions[&#39;E&#39;].width = 18;
ws.column_dimensions[&#39;F&#39;].width = 18
out = io.BytesIO(); wb.save(out); return out.getvalue()
except Exception as e:
print(f&quot;Month Excel error: {e}&quot;)
return generate_month_csv(title, period_text, t63, t90, t110, t150, te63, te90, te110, te150,
total_connections)
def generate_month_pdf(title, period_text, t63, t90, t110, t150=0, te63=0, te90=0, te110=0, te150=0,
total_connections=0):
try:
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors
output = io.BytesIO(); c = canvas.Canvas(output, pagesize=A4); w, h = A4
c.setFillColor(colors.HexColor(&quot;#10B981&quot;)); c.rect(0, h-80, w, 80, fill=1, stroke=0)
c.setFillColor(colors.white); c.setFont(&quot;Helvetica-Bold&quot;, 16); c.drawCentredString(w/2, h-35, title)
c.setFont(&quot;Helvetica&quot;, 10); c.drawCentredString(w/2, h-55, period_text)
y = h - 120
c.setFillColor(colors.HexColor(&quot;#059669&quot;)); c.rect(50, y-5, 500, 25, fill=1, stroke=0)
c.setFillColor(colors.white); c.setFont(&quot;Helvetica-Bold&quot;, 10); c.drawString(55, y+2, &quot;Sr.No&quot;);

c.drawString(90, y+2, &quot;Pipe Dia&quot;); c.drawString(200, y+2, &quot;Qty&quot;); c.drawString(260, y+2, &quot;Extra&quot;);
c.drawString(320, y+2, &quot;UNIT&quot;); c.drawString(420, y+2, &quot;Total MTR&quot;)
y -= 30; c.setFont(&quot;Helvetica&quot;, 12)
tm63 = t63*6 + te63; tm90 = t90*6 + te90; tm110 = t110*6 + te110; tm150 = t150*5.5 + te150
for idx, (dia, qty, extra, unit, total_mtr) in enumerate([(&quot;63MM PVC&quot;, t63, te63, &quot;6MTR per PIPES&quot;,
tm63), (&quot;90MM PVC&quot;, t90, te90, &quot;6MTR per PIPES&quot;, tm90), (&quot;110MM PVC&quot;, t110, te110, &quot;6MTR per PIPES&quot;, tm110),
(&quot;150MM DI&quot;, t150, te150, &quot;5.5MTR&quot;, tm150)], start=1):
if idx % 2 == 0: c.setFillColor(colors.HexColor(&quot;#ECFDF5&quot;)); c.rect(50, y-5, 500, 22, fill=1,
stroke=0)
c.setFillColor(colors.black)
c.drawString(60, y, str(idx)); c.drawString(90, y, dia); c.drawString(210, y, str(qty));
c.drawString(265, y, str(extra)); c.drawString(320, y, unit); c.drawString(420, y, f&quot;{total_mtr} MTR&quot;)
y -= 22
y -= 10
c.setFillColor(colors.HexColor(&quot;#DBEAFE&quot;)); c.rect(50, y-5, 500, 22, fill=1, stroke=0)
c.setFillColor(colors.HexColor(&quot;#1E40AF&quot;)); c.setFont(&quot;Helvetica-Bold&quot;, 11)
c.drawString(55, y+2, f&quot;PVC: {t63+t90+t110} Qty Extra:{te63+te90+te110} MTR:{tm63+tm90+tm110}&quot;)
y -= 22
c.setFillColor(colors.HexColor(&quot;#E9D5FF&quot;)); c.rect(50, y-5, 500, 22, fill=1, stroke=0)
c.setFillColor(colors.HexColor(&quot;#6B21A8&quot;)); c.setFont(&quot;Helvetica-Bold&quot;, 11)
c.drawString(55, y+2, f&quot;DI: {t150} Qty Extra:{te150} MTR:{tm150}&quot;)
y -= 22
c.setFillColor(colors.HexColor(&quot;#D1FAE5&quot;)); c.rect(50, y-5, 500, 25, fill=1, stroke=0)
c.setFillColor(colors.HexColor(&quot;#059669&quot;)); c.setFont(&quot;Helvetica-Bold&quot;, 11)
c.drawString(55, y+2, f&quot;Grand: {t63+t90+t110+t150} Qty | Grand Extra: {te63+te90+te110+te150} MTR | Grand
MTR: {tm63+tm90+tm110+tm150}&quot;)
y -= 30
c.setFillColor(colors.HexColor(&quot;#F59E0B&quot;)); c.rect(50, y-5, 500, 25, fill=1, stroke=0)
c.setFillColor(colors.white); c.setFont(&quot;Helvetica-Bold&quot;, 12)
c.drawCentredString(w/2, y+2, f&quot;Total Connections: {total_connections}&quot;)
c.showPage(); c.save(); return output.getvalue()
except Exception as e:
print(f&quot;Month PDF error: {e}&quot;)
import traceback; traceback.print_exc()
return generate_month_csv(title, period_text, t63, t90, t110, t150, te63, te90, te110, te150,
total_connections)

ui.add_css(&quot;&quot;&quot;
.spa-hidden { display: none !important; }
.report-patti { transition: all 0.15s; cursor: pointer; }
.report-patti:hover { transform: translateY(-2px); box-shadow: 0 8px 20px rgba(16,185,129,0.2); border-color:
#10B981 !important; }
.editable-area .q-field__control { min-height: 48px !important; border-radius: 12px !important; }
.editable-area input { font-weight: 700 !important; font-size: 14px !important; }
.back-btn { background-color: #d4821e !important; color: black !important; border: 2px solid #b56a17
!important; border-radius: 20px !important; font-weight: bold !important; }
.back-btn .q-btn__content { color: black !important; }
.date-pill { background: white !important; border: 1.5px solid #e5e7eb !important; border-radius: 9999px
!important; box-shadow: 0 1px 3px rgba(0,0,0,0.1) !important; padding: 6px 16px !important; display: flex
!important; align-items: center !important; gap: 8px !important; min-width: 145px !important; }
.date-pill input { border: none !important; outline: none !important; font-weight: 700 !important; font-size:
13px !important; color: #1f2937 !important; background: transparent !important; width: 100px !important; text-
align: center !important; cursor: pointer !important; }
.date-pill .q-field__control { background: transparent !important; border: none !important; box-shadow: none
!important; min-height: auto !important; height: auto !important; padding: 0 !important; }
.date-pill .q-field__control:before, .date-pill .q-field__control:after { display: none !important; }
.profile-card { background: white !important; border-radius: 24px !important; box-shadow: 0 10px 30px
rgba(0,0,0,0.08) !important; border: 1.5px solid #e0f2e9 !important; }
.delete-btn { background: white !important; color: #dc2626 !important; border: 1.5px solid #fecaca
!important; border-radius: 9999px !important; font-weight: 700 !important; }
.edit-mini-btn { background: white !important; color: #2563eb !important; border: 1.2px solid #bfdbfe
!important; border-radius: 12px !important; font-weight: 700 !important; font-size: 11px !important; }

.del-mini-btn { background: white !important; color: #dc2626 !important; border: 1.2px solid #fecaca
!important; border-radius: 12px !important; font-weight: 700 !important; font-size: 11px !important; }
.patti-click-area { cursor: pointer; }
.forgot-link { color: #2563eb !important; font-weight: 700 !important; font-size: 13px !important; cursor:
pointer !important; }
&quot;&quot;&quot;, shared=True)
@ui.page(&quot;/reset&quot;)
def reset_page_with_query():
try:
request = ui.context.client.request
token = request.query_params.get(&quot;token&quot;, &quot;&quot;)
if not token:
token = str(request.url).split(&quot;token=&quot;)[-1].split(&quot;&amp;&quot;)[0] if &quot;token=&quot; in str(request.url) else &quot;&quot;
except Exception:
token = &quot;&quot;
return build_reset_content(token)
@ui.page(&quot;/reset/{token}&quot;)
def reset_page_with_path(token: str):
return build_reset_content(token)
def build_reset_content(token: str):
with ui.column().classes(&quot;w-full min-h-screen items-center justify-center bg-gradient-to-br from-indigo-900
via-purple-900 to-slate-900 p-3&quot;):
with ui.card().classes(&quot;w-full max-w-sm rounded-3xl shadow-2xl overflow-hidden p-0&quot;):
with ui.column().classes(&quot;w-full bg-gradient-to-r from-emerald-500 via-teal-600 to-cyan-600 p-5
items-center text-white&quot;):
ui.icon(&quot;lock_reset&quot;, size=&quot;2.5rem&quot;)
ui.label(&quot;Reset Password (6-digit)&quot;).classes(&quot;text-xl font-extrabold&quot;)
with ui.column().classes(&quot;w-full p-5 bg-white gap-3&quot;) as content_col:
db_token_obj = None
user = None
email = None
try:
if HAS_TOKEN_MODEL:
db_token_obj = PasswordResetToken.objects.get(token=token)
age = (timezone.now() - db_token_obj.created_at).total_seconds()
if age &gt; 900:
db_token_obj.delete()
ui.label(&quot;Link Expired! (15 min over)&quot;).classes(&quot;text-red-600 font-bold text-center
w-full&quot;)
ui.button(&quot;Go to Login&quot;, icon=&quot;login&quot;, on_click=lambda:
ui.navigate.to(&quot;/&quot;)).props(&quot;rounded no-caps&quot;).classes(&quot;w-full mt-2 bg-blue-600 text-white font-bold&quot;)
return
user = db_token_obj.user
email = user.email
else:
raise Exception(&quot;No DB model&quot;)
except Exception as e:
ui.label(&quot;Invalid or Expired Link!&quot;).classes(&quot;text-red-600 font-bold text-center w-full&quot;)
ui.button(&quot;Go to Login&quot;, icon=&quot;login&quot;, on_click=lambda: ui.navigate.to(&quot;/&quot;)).props(&quot;rounded
no-caps&quot;).classes(&quot;w-full mt-3 bg-blue-600 text-white font-bold&quot;)
return
ui.label(f&quot;Welcome {user.username}&quot;).classes(&quot;text-lg font-extrabold text-slate-900 text-center
w-full&quot;)
ui.label(f&quot;For: {email}&quot;).classes(&quot;text-xs font-bold text-slate-600 text-center w-full break-
all&quot;)
ui.label(&quot;Change Password (6-digit only)&quot;).classes(&quot;text-sm font-bold text-indigo-700 mt-2 w-full
text-center&quot;)
new_pwd = ui.input(&quot;Enter new password (6 digits)&quot;, placeholder=&quot;Ex: 123456&quot;, password=True,
password_toggle_button=True).props(&quot;outlined rounded dense maxlength=6&quot;).classes(&quot;w-full&quot;)
re_new_pwd = ui.input(&quot;Re-enter new password (6 digits)&quot;, placeholder=&quot;Ex: 123456&quot;,
password=True, password_toggle_button=True).props(&quot;outlined rounded dense maxlength=6&quot;).classes(&quot;w-full&quot;)

status_lbl = ui.label(&quot;&quot;).classes(&quot;text-xs font-bold text-center w-full&quot;)
def do_confirm_reset():
p1 = (new_pwd.value or &quot;&quot;).strip()
p2 = (re_new_pwd.value or &quot;&quot;).strip()
if not is_valid_6digit(p1):
status_lbl.set_text(&quot;❌ Password must be exactly 6 digits!&quot;)
return
if p1 != p2:
status_lbl.set_text(&quot;❌ Both passwords not same!&quot;)
return
try:
user.password = make_password(p1)
user.save(update_fields=[&#39;password&#39;])
CACHE[&quot;users&quot;].pop(email, None)
CACHE[&quot;pwd_verified&quot;] = {k:v for k,v in CACHE[&quot;pwd_verified&quot;].items() if v != user.id}
if db_token_obj:
db_token_obj.delete()
content_col.clear()
with content_col:
ui.icon(&quot;check_circle&quot;, size=&quot;3rem&quot;, color=&quot;green&quot;)
ui.label(&quot;Successfully changed password!&quot;).classes(&quot;text-base font-extrabold text-
green-700 text-center w-full mt-2&quot;)
ui.button(&quot;Go to Login&quot;, icon=&quot;login&quot;, on_click=lambda:
ui.navigate.to(&quot;/&quot;)).props(&quot;rounded no-caps&quot;).classes(&quot;w-full mt-4 bg-gradient-to-r from-emerald-600 to-green-600
text-white font-bold py-2.5 shadow-lg&quot;)
except Exception as e:
status_lbl.set_text(f&quot;❌ Failed: {e}&quot;)
ui.button(&quot;Confirm (6-digit)&quot;, icon=&quot;check&quot;, on_click=do_confirm_reset).props(&quot;rounded no-
caps&quot;).classes(&quot;w-full mt-2 bg-gradient-to-r from-emerald-600 to-green-600 text-white font-bold py-2.5 shadow-
lg&quot;)
@ui.page(&quot;/&quot;)
def main_spa_page():
print(&quot;�� FINAL VERAVAL TRACKER - 63,90,110,150&quot;, flush=True)
state = {&quot;user&quot;: None, &quot;selected_report&quot;: None}
with ui.column().classes(&quot;w-full min-h-screen p-0 m-0 gap-0&quot;) as root:
login_view = ui.column().classes(&quot;w-full min-h-screen items-center justify-center bg-gradient-to-br from-
indigo-900 via-purple-900 to-slate-900 p-3&quot;)
with login_view:
with ui.card().classes(&quot;w-full max-w-sm rounded-3xl shadow-2xl overflow-hidden p-0 border-2 border-
green-400/50&quot;):
with ui.column().classes(&quot;w-full bg-gradient-to-r from-emerald-500 via-green-600 to-teal-600 p-4
items-center text-white&quot;):
ui.icon(&quot;bolt&quot;, size=&quot;2.5rem&quot;)
ui.label(&quot;VERAVAL SITE TRACKER&quot;).classes(&quot;text-xl font-extrabold&quot;)
ui.label(&quot;PipeLine Progress&quot;).classes(&quot;text-xs&quot;)
with ui.column().classes(&quot;w-full p-5 bg-white gap-3&quot;):
saved_email = app.storage.user.get(&quot;saved_email&quot;, &quot;&quot;)
saved_pwd = app.storage.user.get(&quot;saved_password&quot;, &quot;&quot;)
email_input = ui.input(&quot;Email ID&quot;, value=saved_email).props(&quot;outlined rounded
dense&quot;).classes(&quot;w-full&quot;)
pass_input = ui.input(&quot;Password (6 digits)&quot;, value=saved_pwd, placeholder=&quot;6 digits only&quot;,
password=True, password_toggle_button=True).props(&quot;outlined rounded dense maxlength=6&quot;).classes(&quot;w-full&quot;)
login_btn = ui.button(&quot;⚡ Log In&quot;, icon=&quot;bolt&quot;).props(&quot;rounded no-caps&quot;).classes(&quot;w-full py-
2.5 bg-gradient-to-r from-emerald-600 to-green-600 text-white font-bold shadow-lg&quot;)
status_label = ui.label(&quot;&quot;).classes(&quot;text-xs text-center font-bold text-green-600&quot;)
# FAST LOGIN: Check as typing - like 5*6=30 instant - Email+Pwd cached? Instant home
def fast_check_login():
e = (email_input.value or &quot;&quot;).strip()
p = (pass_input.value or &quot;&quot;).strip()
if len(p)==6 and p.isdigit() and e:
pwd_key = hashlib.sha256(f&quot;{e}:{p}&quot;.encode()).hexdigest()
if pwd_key in CACHE[&quot;pwd_verified&quot;] and e in CACHE[&quot;users&quot;]:

status_label.set_text(&quot;✅ Ready - Click Login for instant home!&quot;)
login_btn.classes(add=&quot;bg-green-700&quot;, remove=&quot;bg-gradient-to-r from-emerald-600
to-green-600&quot;)
else:
status_label.set_text(&quot;⏳ 6-digit entered - Click to verify&quot;)
elif len(p)&gt;0 and len(p)&lt;6:
status_label.set_text(f&quot;⏳ {len(p)}/6 digits...&quot;)
elif len(p)==6 and not p.isdigit():
status_label.set_text(&quot;❌ Only digits allowed&quot;)
else:
status_label.set_text(&quot;&quot;)
email_input.on_value_change(lambda _: fast_check_login())
pass_input.on_value_change(lambda _: fast_check_login())
# Auto-check on load if saved credentials exist
def auto_check_saved():
if saved_email and saved_pwd and is_valid_6digit(saved_pwd):
fast_check_login()
ui.timer(0.5, auto_check_saved, once=True)
with ui.row().classes(&quot;w-full justify-center mt-1&quot;):
forgot_link = ui.label(&quot;Forgot password?&quot;).classes(&quot;forgot-link&quot;)
reg_btn = ui.button(&quot;Register New Account&quot;, icon=&quot;person_add&quot;).props(&quot;outline rounded no-
caps&quot;).classes(&quot;w-full text-emerald-600 font-bold text-sm border-emerald-500 mt-2&quot;)
home_view = ui.column().classes(&quot;w-full min-h-screen bg-gradient-to-br from-indigo-100 via-purple-50 to-
pink-100 py-2 px-1.5 sm:px-4 items-center spa-hidden&quot;)
filter_view = ui.column().classes(&quot;w-full min-h-screen bg-gradient-to-br from-indigo-100 via-purple-50
to-pink-100 py-2 px-1.5 sm:px-4 items-center spa-hidden&quot;)
filter_detail_view = ui.column().classes(&quot;w-full min-h-screen bg-gradient-to-br from-indigo-100 via-
purple-50 to-pink-100 py-2 px-1.5 sm:px-4 items-center spa-hidden&quot;)
profile_view = ui.column().classes(&quot;w-full min-h-screen bg-gradient-to-br from-indigo-100 via-purple-50
to-pink-100 p-3 items-center justify-center spa-hidden&quot;)
register_view = ui.column().classes(&quot;w-full min-h-screen items-center justify-center bg-gradient-to-br
from-indigo-900 via-purple-900 to-slate-900 p-3 spa-hidden&quot;)
forgot_view = ui.column().classes(&quot;w-full min-h-screen items-center justify-center bg-gradient-to-br
from-indigo-900 via-purple-900 to-slate-900 p-3 spa-hidden&quot;)
def show_login():
state[&quot;user&quot;] = None
login_view.classes(remove=&quot;spa-hidden&quot;)
home_view.classes(add=&quot;spa-hidden&quot;)
filter_view.classes(add=&quot;spa-hidden&quot;)
filter_detail_view.classes(add=&quot;spa-hidden&quot;)
profile_view.classes(add=&quot;spa-hidden&quot;)
register_view.classes(add=&quot;spa-hidden&quot;)
forgot_view.classes(add=&quot;spa-hidden&quot;)
def show_login_as_logout():
state[&quot;user&quot;] = None
saved_e = app.storage.user.get(&quot;saved_email&quot;, &quot;&quot;)
saved_p = app.storage.user.get(&quot;saved_password&quot;, &quot;&quot;)
app.storage.user.clear()
app.storage.user[&quot;saved_email&quot;] = saved_e
app.storage.user[&quot;saved_password&quot;] = saved_p
show_login()
def show_home():
login_view.classes(add=&quot;spa-hidden&quot;)
home_view.classes(remove=&quot;spa-hidden&quot;)
filter_view.classes(add=&quot;spa-hidden&quot;)
filter_detail_view.classes(add=&quot;spa-hidden&quot;)
profile_view.classes(add=&quot;spa-hidden&quot;)
register_view.classes(add=&quot;spa-hidden&quot;)
forgot_view.classes(add=&quot;spa-hidden&quot;)

build_home()
def show_filter():
# INSTANT UI: Show filter view immediately - No waiting 1-2 sec - UI first, DB later (parallel)
login_view.classes(add=&quot;spa-hidden&quot;)
home_view.classes(add=&quot;spa-hidden&quot;)
filter_view.classes(remove=&quot;spa-hidden&quot;)
filter_detail_view.classes(add=&quot;spa-hidden&quot;)
profile_view.classes(add=&quot;spa-hidden&quot;)
register_view.classes(add=&quot;spa-hidden&quot;)
forgot_view.classes(add=&quot;spa-hidden&quot;)
# Show loading skeleton instantly
filter_view.clear()
with filter_view:
with ui.column().classes(&quot;w-full max-w-md items-center gap-2&quot;):
with ui.card().classes(&quot;w-full rounded-3xl shadow-2xl bg-white p-5 border-2 border-green-200
items-center&quot;):
ui.spinner(size=&quot;lg&quot;, color=&quot;green&quot;)
ui.label(&quot;Loading reports...&quot;).classes(&quot;text-sm font-bold text-green-700 mt-2&quot;)
# Load real data in background - UI + DB parallel
async def load_filter_bg():
await asyncio.sleep(0.05) # Let UI render first
build_filter()
ui.timer(0.05, lambda: asyncio.create_task(load_filter_bg()), once=True)
def show_filter_detail(report):
state[&quot;selected_report&quot;] = report
login_view.classes(add=&quot;spa-hidden&quot;)
home_view.classes(add=&quot;spa-hidden&quot;)
filter_view.classes(add=&quot;spa-hidden&quot;)
filter_detail_view.classes(remove=&quot;spa-hidden&quot;)
profile_view.classes(add=&quot;spa-hidden&quot;)
register_view.classes(add=&quot;spa-hidden&quot;)
forgot_view.classes(add=&quot;spa-hidden&quot;)
build_filter_detail(report)
def show_profile():
login_view.classes(add=&quot;spa-hidden&quot;)
home_view.classes(add=&quot;spa-hidden&quot;)
filter_view.classes(add=&quot;spa-hidden&quot;)
filter_detail_view.classes(add=&quot;spa-hidden&quot;)
profile_view.classes(remove=&quot;spa-hidden&quot;)
register_view.classes(add=&quot;spa-hidden&quot;)
forgot_view.classes(add=&quot;spa-hidden&quot;)
build_profile()
def show_register():
login_view.classes(add=&quot;spa-hidden&quot;)
home_view.classes(add=&quot;spa-hidden&quot;)
filter_view.classes(add=&quot;spa-hidden&quot;)
filter_detail_view.classes(add=&quot;spa-hidden&quot;)
profile_view.classes(add=&quot;spa-hidden&quot;)
register_view.classes(remove=&quot;spa-hidden&quot;)
forgot_view.classes(add=&quot;spa-hidden&quot;)
def show_forgot():
login_view.classes(add=&quot;spa-hidden&quot;)
home_view.classes(add=&quot;spa-hidden&quot;)
filter_view.classes(add=&quot;spa-hidden&quot;)
filter_detail_view.classes(add=&quot;spa-hidden&quot;)
profile_view.classes(add=&quot;spa-hidden&quot;)
register_view.classes(add=&quot;spa-hidden&quot;)
forgot_view.classes(remove=&quot;spa-hidden&quot;)
build_forgot()

def build_forgot():
forgot_view.clear()
with forgot_view:
with ui.card().classes(&quot;w-full max-w-sm rounded-3xl shadow-2xl overflow-hidden p-0&quot;):
with ui.column().classes(&quot;w-full bg-gradient-to-r from-emerald-500 via-teal-600 to-cyan-600
p-5 items-center text-white&quot;):
ui.icon(&quot;lock_reset&quot;, size=&quot;2.5rem&quot;)
ui.label(&quot;Direct Reset - No Email!&quot;).classes(&quot;text-xl font-extrabold&quot;)
ui.label(&quot;ID nakho, tyaj password badli jase&quot;).classes(&quot;text-xs opacity-90&quot;)
with ui.column().classes(&quot;w-full p-5 bg-white gap-3&quot;):
forgot_email = ui.input(&quot;Email ID / User ID&quot;, placeholder=&quot;Enter registered
Email&quot;).props(&quot;outlined rounded dense&quot;).classes(&quot;w-full&quot;)
forgot_status = ui.label(&quot;&quot;).classes(&quot;text-sm font-bold text-center w-full py-1&quot;)
reset_area = ui.column().classes(&quot;w-full gap-3 mt-1&quot;)
async def do_direct_reset(new_pwd_input, re_new_pwd_input, reset_status_label,
verified_email):
p1 = (new_pwd_input.value or &quot;&quot;).strip()
p2 = (re_new_pwd_input.value or &quot;&quot;).strip()
email = verified_email
if not is_valid_6digit(p1):
reset_status_label.set_text(&quot;❌ Password must be exactly 6 digits! Ex: 123456&quot;)
ui.notify(&quot;Password must be exactly 6 digits!&quot;, type=&quot;negative&quot;, position=&quot;top&quot;)
return
if p1 != p2:
reset_status_label.set_text(&quot;❌ Both passwords not same!&quot;)
return
reset_status_label.set_text(&quot;⏳ Changing password...&quot;)
try:
def update_pwd():
try:
u = AppUser.objects.get(email=email)
except AppUser.DoesNotExist:
try:
u = AppUser.objects.get(username=email)
except AppUser.DoesNotExist:
return None
u.password = make_password(p1)
u.save(update_fields=[&#39;password&#39;])
return u
user = await run.io_bound(update_pwd)
if not user:
reset_status_label.set_text(&quot;❌ User not found!&quot;)
return
CACHE[&quot;users&quot;].pop(email, None)
CACHE[&quot;users&quot;][user.email] = user
keys_to_del = [k for k in list(CACHE[&quot;pwd_verified&quot;].keys()) if email in k]
for k in keys_to_del:
CACHE[&quot;pwd_verified&quot;].pop(k, None)
pwd_key = hashlib.sha256(f&quot;{user.email}:{p1}&quot;.encode()).hexdigest()
CACHE[&quot;pwd_verified&quot;][pwd_key] = user.id
app.storage.user[&quot;saved_email&quot;] = user.email
app.storage.user[&quot;saved_password&quot;] = p1
reset_status_label.set_text(&quot;✅ Password changed! Going to login...&quot;)
ui.notify(&quot;✅ Password changed! Login now&quot;, type=&quot;positive&quot;, position=&quot;top&quot;)
await asyncio.sleep(1.2)
show_login()
except Exception as e:
reset_status_label.set_text(f&quot;❌ Error: {e}&quot;)
async def verify_id():
email = (forgot_email.value or &quot;&quot;).strip()
if not email:

forgot_status.set_text(&quot;❌ Enter Email ID / User ID!&quot;)
return
forgot_status.set_text(&quot;⏳ Checking ID...&quot;)
try:
def get_user():
try:
return AppUser.objects.get(email=email)
except AppUser.DoesNotExist:
try:
return AppUser.objects.get(username=email)
except AppUser.DoesNotExist:
return None
user = await run.io_bound(get_user)
if not user:
forgot_status.set_text(&quot;❌ ID not registered! Check Email/Username&quot;)
reset_area.clear()
return
forgot_status.set_text(f&quot;✅ Found: {user.username} ({user.email})&quot;)
reset_area.clear()
with reset_area:
ui.separator().classes(&quot;my-2&quot;)
ui.label(&quot;✅ ID Verified! New password nakho:&quot;).classes(&quot;text-[13px] font-
extrabold text-green-700 bg-green-50 px-3 py-1.5 rounded-full text-center w-full&quot;)
new_pwd_input = ui.input(&quot;New Password (6 digits)&quot;, placeholder=&quot;Ex: 123456&quot;,
password=True, password_toggle_button=True).props(&quot;outlined rounded dense maxlength=6 color=green&quot;).classes(&quot;w-
full font-bold&quot;)
re_new_pwd_input = ui.input(&quot;Retype Password (6 digits)&quot;, placeholder=&quot;Ex:
123456&quot;, password=True, password_toggle_button=True).props(&quot;outlined rounded dense maxlength=6
color=green&quot;).classes(&quot;w-full font-bold&quot;)
reset_status_label = ui.label(&quot;&quot;).classes(&quot;text-xs font-bold text-center w-
full&quot;)
ui.button(&quot;Change Password - Confirm (6-digit)&quot;, icon=&quot;check_circle&quot;,
on_click=lambda: do_direct_reset(new_pwd_input, re_new_pwd_input, reset_status_label, email)).props(&quot;rounded no-
caps&quot;).classes(&quot;w-full py-2.5 bg-gradient-to-r from-emerald-600 to-green-600 text-white font-bold shadow-lg mt-
1&quot;)
except Exception as e:
forgot_status.set_text(f&quot;❌ Error: {e}&quot;)
ui.button(&quot;Verify ID &amp; Reset Direct&quot;, icon=&quot;verified_user&quot;,
on_click=verify_id).props(&quot;rounded no-caps&quot;).classes(&quot;w-full py-2.5 bg-gradient-to-r from-blue-600 to-indigo-600
text-white font-bold shadow-lg mt-2&quot;)
ui.button(&quot;Back to Login&quot;, icon=&quot;arrow_back&quot;, on_click=show_login).props(&quot;flat rounded
no-caps&quot;).classes(&quot;w-full text-blue-600 font-bold text-sm mt-1&quot;)

def build_home():
home_view.clear()
user = state[&quot;user&quot;]
if not user:
show_login()
return
try:
fresh_user = AppUser.objects.get(id=user.id)
CACHE[&quot;users&quot;][fresh_user.email] = fresh_user
state[&quot;user&quot;] = fresh_user
user = fresh_user
except Exception:
pass
with home_view:
with ui.column().classes(&quot;w-full max-w-md items-center gap-0&quot;):
with ui.card().classes(&quot;w-full rounded-2xl shadow-xl bg-white p-1.5 border-2 border-green-
200&quot;):
with ui.row().classes(&quot;w-full justify-between items-center mb-1 px-1 py-0.5 bg-slate-50

rounded-full border&quot;):
ui.button(&quot;Back&quot;, icon=&quot;arrow_back&quot;, on_click=show_login_as_logout).props(&quot;flat
rounded dense no-caps&quot;).classes(&quot;back-btn text-[11px] shadow-sm&quot;)
today_str = today_ist().isoformat()
with ui.row().classes(&quot;date-pill-compact items-center justify-center&quot;):
home_date_input = ui.input(value=today_str).props(&quot;type=date borderless
dense&quot;).classes(&quot;text-[11px] font-bold&quot;)
with ui.button(icon=&quot;account_circle&quot;).props(&quot;round unelevated dense&quot;).classes(&quot;bg-
gradient-to-r from-indigo-600 to-purple-600 text-white shadow-md&quot;):
with ui.menu().classes(&quot;rounded-xl shadow-xl border border-purple-200&quot;):
with ui.menu_item(on_click=show_profile).classes(&quot;hover:bg-purple-50 font-
semibold&quot;):
with ui.row().classes(&quot;items-center gap-2&quot;): ui.icon(&quot;person&quot;,
color=&quot;purple&quot;); ui.label(&quot;Profile&quot;)
ui.separator()
with ui.menu_item(on_click=show_filter).classes(&quot;hover:bg-purple-50 font-
semibold&quot;):
with ui.row().classes(&quot;items-center gap-2&quot;): ui.icon(&quot;filter_alt&quot;,
color=&quot;indigo&quot;); ui.label(&quot;Filter&quot;)
with ui.row().classes(&quot;w-full justify-center mb-1 mt-0.5&quot;):
title_input = ui.input(value=user.default_report_title or &quot;Veraval
site&quot;).props(&quot;borderless dense input-class=&#39;text-center font-extrabold text-[13px] text-slate-900&#39;&quot;).classes(&quot;w-
full px-2 py-0.5 rounded-full bg-gradient-to-r from-cyan-200 via-purple-200 to-fuchsia-300 shadow-md border-2
border-purple-300&quot;)
def save_title_persist():
try:
new_title = (title_input.value or &quot;&quot;).strip()
if not new_title:
return
if new_title == user.default_report_title:
return
user.default_report_title = new_title
user.save(update_fields=[&#39;default_report_title&#39;])
CACHE[&quot;users&quot;][user.email] = user
state[&quot;user&quot;] = user
ui.notify(f&quot;✅ Title Saved&quot;, type=&quot;positive&quot;, position=&quot;top&quot;, timeout=2000)
except Exception as ex:
print(f&quot;Title save fail: {ex}&quot;)
title_input.on(&quot;blur&quot;, lambda _: save_title_persist())
title_input.on(&quot;keydown.enter&quot;, lambda _: save_title_persist())
def get_areas():
if user.id in CACHE[&quot;areas&quot;]:
return CACHE[&quot;areas&quot;][user.id]
areas = list(SavedArea.objects.filter(user=user).order_by(&quot;-
id&quot;).values_list(&quot;area_name&quot;, flat=True)[:100])
CACHE[&quot;areas&quot;][user.id] = areas
return areas
def get_labours():
if &quot;labours&quot; not in CACHE:
CACHE[&quot;labours&quot;] = {}
if user.id in CACHE[&quot;labours&quot;]:
return CACHE[&quot;labours&quot;][user.id]
if HAS_LABOUR_MODEL:
try:
labours = list(SavedLabour.objects.filter(user=user).order_by(&quot;-
id&quot;).values_list(&quot;labour_name&quot;, flat=True)[:100])
except:
labours = []
else:
labours = []
CACHE[&quot;labours&quot;][user.id] = labours
return labours
saved_areas = get_areas()

saved_labours = get_labours()
def get_default_area():
try:
stored = app.storage.user.get(&quot;default_area_name&quot;, &quot;&quot;)
if stored:
return stored
if hasattr(user, &#39;default_area_name&#39;) and user.default_area_name:
return user.default_area_name
last = DailyReport.objects.filter(user=user).order_by(&quot;-id&quot;).first()
if last and last.area_name:
return last.area_name
except:
pass
return &quot;&quot;
def get_default_labour():
try:
stored = app.storage.user.get(&quot;default_labour_name&quot;, &quot;&quot;)
if stored:
return stored
if hasattr(user, &#39;default_labour_name&#39;) and user.default_labour_name:
return user.default_labour_name
last = DailyReport.objects.filter(user=user).order_by(&quot;-id&quot;).first()
if last and last.labour_name:
return last.labour_name
except:
pass
return &quot;&quot;
def save_default_area():
try:
val = (area_input.value or &quot;&quot;).strip()
if not val:
return
app.storage.user[&quot;default_area_name&quot;] = val
if val != getattr(user, &#39;default_area_name&#39;, &#39;&#39;):
try:
user.default_area_name = val
user.save(update_fields=[&#39;default_area_name&#39;])
CACHE[&quot;users&quot;][user.email] = user
except:
pass
except Exception as e:
print(f&quot;Area save fail: {e}&quot;)
def save_default_labour():
try:
val = (labour_input.value or &quot;&quot;).strip()
if not val:
return
app.storage.user[&quot;default_labour_name&quot;] = val
if val != getattr(user, &#39;default_labour_name&#39;, &#39;&#39;):
try:
user.default_labour_name = val
user.save(update_fields=[&#39;default_labour_name&#39;])
CACHE[&quot;users&quot;][user.email] = user
except:
pass
except Exception as e:
print(f&quot;Labour save fail: {e}&quot;)
with ui.row().classes(&quot;w-full mb-1 gap-2&quot;):
with ui.column().classes(&quot;flex-1 gap-0.5&quot;):
ui.label(&quot;Enter Area *&quot;).classes(&quot;text-[12px] font-extrabold text-green-700 ml-
1&quot;)
area_input = ui.input(placeholder=&quot;Type area...&quot;,
value=get_default_area()).props(&quot;outlined rounded dense color=green input-class=&#39;text-
[13px]&#39;&quot;).classes(&quot;editable-area w-full bg-white font-bold text-[13px] shadow-sm&quot;)

area_input.on(&quot;blur&quot;, lambda _: save_default_area())
area_input.on(&quot;keydown.enter&quot;, lambda _: save_default_area())
with ui.column().classes(&quot;flex-1 gap-0.5&quot;):
ui.label(&quot;Enter Labour Name&quot;).classes(&quot;text-[12px] font-extrabold text-blue-700
ml-1&quot;)
labour_input = ui.input(placeholder=&quot;Type labour...&quot;,
value=get_default_labour()).props(&quot;outlined rounded dense color=blue input-class=&#39;text-
[13px]&#39;&quot;).classes(&quot;editable-area w-full bg-white font-bold text-[13px] shadow-sm&quot;)
labour_input.on(&quot;blur&quot;, lambda _: save_default_labour())
labour_input.on(&quot;keydown.enter&quot;, lambda _: save_default_labour())
pipe_mtr_state = {&quot;63&quot;: 6.0, &quot;90&quot;: 6.0, &quot;110&quot;: 6.0, &quot;150&quot;: 5.5}
with ui.row().classes(&quot;w-full justify-center items-center gap-2 mb-2 mt-1&quot;):
pipe_logic_btn = ui.button(&quot;PIPE MTR LOGIC&quot;, icon=&quot;info&quot;).props(&quot;dense rounded
outline color=purple&quot;).classes(&quot;text-[10px] font-bold px-2 py-1 border-purple-300&quot;)
with ui.row().classes(&quot;items-center gap-1&quot;):
ui.icon(&quot;bolt&quot;, color=&quot;green&quot;, size=&quot;1.1rem&quot;); ui.label(&quot;PipeLine
Progress&quot;).classes(&quot;text-[14px] font-extrabold text-slate-800 text-center&quot;)
with ui.dialog() as pipe_logic_dialog, ui.card().classes(&quot;rounded-2xl p-0 w-full max-w-sm
shadow-2xl overflow-hidden&quot;):
with ui.column().classes(&quot;w-full p-0 gap-0&quot;):
with ui.row().classes(&quot;w-full bg-gradient-to-r from-purple-600 to-indigo-600 p-3
items-center justify-between text-white&quot;):
ui.label(&quot;�� PIPE MTR LOGIC&quot;).classes(&quot;font-extrabold text-[13px] text-white&quot;)
ui.button(icon=&quot;close&quot;, on_click=pipe_logic_dialog.close).props(&quot;flat round
dense color=white&quot;).classes(&quot;text-white&quot;)
with ui.column().classes(&quot;w-full p-3 gap-2 bg-white&quot;):
ui.label(&quot;Per Pipe MTR Details - View Only&quot;).classes(&quot;text-[11px] font-bold
text-purple-700 text-center w-full bg-purple-50 px-2 py-1 rounded-full&quot;)
with ui.column().classes(&quot;w-full rounded-xl overflow-hidden border-2 border-
indigo-900 shadow-md mt-1&quot;):
with ui.grid(columns=4).classes(&quot;w-full bg-gradient-to-r from-emerald-500
to-teal-500 text-white font-extrabold text-center&quot;):
ui.label(&quot;63MM&quot;).classes(&quot;py-2 text-[11px]&quot;);
ui.label(&quot;90MM&quot;).classes(&quot;py-2 text-[11px] border-x border-white/30&quot;); ui.label(&quot;110MM&quot;).classes(&quot;py-2 text-
[11px] border-r border-white/30&quot;); ui.label(&quot;150MM&quot;).classes(&quot;py-2 text-[11px]&quot;)
with ui.grid(columns=4).classes(&quot;w-full bg-slate-100 text-center border-y
border-indigo-900&quot;):
ui.label(&quot;per pipe MTR&quot;).classes(&quot;py-1 text-[9px] font-bold text-
slate-600&quot;); ui.label(&quot;per pipe MTR&quot;).classes(&quot;py-1 text-[9px] font-bold text-slate-600 border-x border-gray-
300&quot;); ui.label(&quot;per pipe MTR&quot;).classes(&quot;py-1 text-[9px] font-bold text-slate-600 border-r border-gray-300&quot;);
ui.label(&quot;per pipe MTR&quot;).classes(&quot;py-1 text-[9px] font-bold text-slate-600&quot;)
with ui.grid(columns=4).classes(&quot;w-full bg-white text-center&quot;):
with ui.column().classes(&quot;w-full p-1&quot;):
ui.input(value=&quot;6MTR&quot;).props(&quot;outlined dense readonly input-
class=&#39;text-center font-extrabold text-[13px]&#39;&quot;).classes(&quot;w-full bg-green-50&quot;)
with ui.column().classes(&quot;w-full p-1 border-x border-gray-200&quot;):
ui.input(value=&quot;6MTR&quot;).props(&quot;outlined dense readonly input-
class=&#39;text-center font-extrabold text-[13px]&#39;&quot;).classes(&quot;w-full bg-green-50&quot;)
with ui.column().classes(&quot;w-full p-1 border-r border-gray-200&quot;):
ui.input(value=&quot;6MTR&quot;).props(&quot;outlined dense readonly input-
class=&#39;text-center font-extrabold text-[13px]&#39;&quot;).classes(&quot;w-full bg-green-50&quot;)
with ui.column().classes(&quot;w-full p-1&quot;):
ui.input(value=&quot;5.5MTR&quot;).props(&quot;outlined dense readonly input-
class=&#39;text-center font-extrabold text-[13px]&#39;&quot;).classes(&quot;w-full bg-purple-50&quot;)
with ui.column().classes(&quot;w-full bg-amber-50 rounded-xl p-2 border border-
amber-200 mt-2&quot;):
ui.label(&quot;Logic: Total MTR = Count × Per Pipe MTR + Extra
MTR&quot;).classes(&quot;text-[10px] font-bold text-amber-800 text-center w-full&quot;)
ui.label(&quot;Example: 63MM Count 5 × 6MTR = 30MTR&quot;).classes(&quot;text-[9px]
font-bold text-slate-600 text-center w-full mt-1&quot;)
ui.button(&quot;Close&quot;, icon=&quot;close&quot;,
on_click=pipe_logic_dialog.close).props(&quot;rounded&quot;).classes(&quot;w-full mt-2 bg-slate-100 text-slate-700 font-bold

text-[12px]&quot;)
pipe_logic_btn.on_click(pipe_logic_dialog.open)
extra_state = {&quot;63&quot;: 0.0, &quot;90&quot;: 0.0, &quot;110&quot;: 0.0, &quot;150&quot;: 0.0}
with ui.column().classes(&quot;w-full items-center justify-center py-10 gap-3 mt-1 bg-slate-50
rounded-2xl border-2 border-dashed border-green-200&quot;):
ui.icon(&quot;assignment_add&quot;, size=&quot;2.5rem&quot;, color=&quot;green&quot;)
ui.label(&quot;No active report - Start new&quot;).classes(&quot;text-[11px] font-bold text-slate-
500&quot;)
new_report_btn = ui.button(&quot;+New Report&quot;, icon=&quot;add&quot;).props(&quot;rounded&quot;).classes(&quot;w-3/5
py-3 bg-gradient-to-r from-emerald-500 to-teal-600 text-white font-extrabold text-[14px] shadow-xl&quot;)
with ui.dialog() as new_report_dialog, ui.card().classes(&quot;rounded-3xl p-0 w-full max-w-md
shadow-2xl overflow-hidden&quot;):
with ui.column().classes(&quot;w-full p-0 gap-0&quot;):
with ui.row().classes(&quot;w-full bg-gradient-to-r from-indigo-600 via-purple-600 to-
emerald-600 p-3 items-center justify-between text-white&quot;):
ui.label(&quot;�� New Report&quot;).classes(&quot;font-extrabold text-[14px] text-white&quot;)
ui.button(icon=&quot;close&quot;, on_click=new_report_dialog.close).props(&quot;flat round
dense color=white&quot;).classes(&quot;text-white&quot;)
with ui.row().classes(&quot;w-full justify-around items-center bg-slate-50 p-3 border-
b-2 border-indigo-100&quot;):
nav_pipe_btn = ui.button(icon=&quot;pie_chart&quot;).props(&quot;round dense&quot;).classes(&quot;bg-
blue-600 text-white shadow-lg w-12 h-12&quot;)
nav_conn_btn = ui.button(icon=&quot;link&quot;).props(&quot;round dense&quot;).classes(&quot;bg-slate-
200 text-slate-600 w-12 h-12&quot;)
nav_save_btn = ui.button(icon=&quot;save&quot;).props(&quot;round dense&quot;).classes(&quot;bg-slate-
200 text-slate-600 w-12 h-12&quot;)
pipe_section = ui.column().classes(&quot;w-full p-3 gap-0&quot;)
conn_section = ui.column().classes(&quot;w-full p-4 gap-3 hidden&quot;)
save_section = ui.column().classes(&quot;w-full p-4 gap-3 hidden&quot;)
def show_section(name):
pipe_section.classes(add=&quot;hidden&quot;); conn_section.classes(add=&quot;hidden&quot;);
save_section.classes(add=&quot;hidden&quot;)
nav_pipe_btn.classes(replace=&quot;bg-blue-600 text-white shadow-lg&quot;, add=&quot;bg-
slate-200 text-slate-600&quot;)
nav_conn_btn.classes(replace=&quot;bg-blue-600 text-white shadow-lg&quot;, add=&quot;bg-
slate-200 text-slate-600&quot;)
nav_save_btn.classes(replace=&quot;bg-green-600 text-white shadow-lg&quot;, add=&quot;bg-
slate-200 text-slate-600&quot;)
nav_pipe_btn.classes(replace=&quot;bg-green-600 text-white shadow-lg&quot;, add=&quot;bg-
slate-200 text-slate-600&quot;)
nav_conn_btn.classes(replace=&quot;bg-green-600 text-white shadow-lg&quot;, add=&quot;bg-
slate-200 text-slate-600&quot;)
nav_save_btn.classes(replace=&quot;bg-blue-600 text-white shadow-lg&quot;, add=&quot;bg-
slate-200 text-slate-600&quot;)
if name == &quot;pipe&quot;:
pipe_section.classes(remove=&quot;hidden&quot;)
nav_pipe_btn.classes(replace=&quot;bg-slate-200 text-slate-600&quot;, add=&quot;bg-blue-
600 text-white shadow-lg&quot;)
elif name == &quot;conn&quot;:
conn_section.classes(remove=&quot;hidden&quot;)
nav_conn_btn.classes(replace=&quot;bg-slate-200 text-slate-600&quot;, add=&quot;bg-blue-
600 text-white shadow-lg&quot;)
elif name == &quot;save&quot;:
save_section.classes(remove=&quot;hidden&quot;)
nav_save_btn.classes(replace=&quot;bg-slate-200 text-slate-600&quot;, add=&quot;bg-
green-600 text-white shadow-lg&quot;)
nav_pipe_btn.on_click(lambda: show_section(&quot;pipe&quot;))
nav_conn_btn.on_click(lambda: show_section(&quot;conn&quot;))

nav_save_btn.on_click(lambda: show_section(&quot;save&quot;))
with pipe_section:
with ui.column().classes(&quot;w-full rounded-2xl overflow-hidden shadow-lg
border-2 border-indigo-900 gap-0&quot;):
with ui.grid(columns=4).classes(&quot;w-full bg-gradient-to-r from-emerald-500
via-green-500 to-teal-500 text-white font-extrabold text-center&quot;):
ui.label(&quot;63MM PVC&quot;).classes(&quot;py-2 text-[10px]&quot;); ui.label(&quot;90MM
PVC&quot;).classes(&quot;py-2 text-[10px] border-x border-white/30&quot;); ui.label(&quot;110MM PVC&quot;).classes(&quot;py-2 text-[10px]
border-r border-white/30&quot;); ui.label(&quot;150MM DI&quot;).classes(&quot;py-2 text-[10px]&quot;)
with ui.grid(columns=4).classes(&quot;w-full bg-white text-center items-
center&quot;):
with ui.column().classes(&quot;p-1 items-center w-full&quot;): c63 =
ui.input(placeholder=&quot;Count&quot;).props(&quot;type=number outlined dense color=green input-class=&#39;text-center font-bold
text-[13px]&#39; step=0.1&quot;).classes(&quot;w-full h-10&quot;)
with ui.column().classes(&quot;p-1 items-center border-x-2 border-indigo-
900 w-full&quot;): c90 = ui.input(placeholder=&quot;Count&quot;).props(&quot;type=number outlined dense color=green input-
class=&#39;text-center font-bold text-[13px]&#39; step=0.1&quot;).classes(&quot;w-full h-10&quot;)
with ui.column().classes(&quot;p-1 items-center border-r-2 border-indigo-
900 w-full&quot;): c110 = ui.input(placeholder=&quot;Count&quot;).props(&quot;type=number outlined dense color=green input-
class=&#39;text-center font-bold text-[13px]&#39; step=0.1&quot;).classes(&quot;w-full h-10&quot;)
with ui.column().classes(&quot;p-1 items-center w-full&quot;): c150 =
ui.input(placeholder=&quot;Count&quot;).props(&quot;type=number outlined dense color=green input-class=&#39;text-center font-bold
text-[13px]&#39; step=0.1&quot;).classes(&quot;w-full h-10&quot;)
with ui.grid(columns=4).classes(&quot;w-full bg-white text-center items-center
border-t border-indigo-900&quot;):
with ui.column().classes(&quot;p-0.5 items-center w-full&quot;):
add_63_btn = ui.button(&quot;+ADD MTR&quot;).props(&quot;flat
dense&quot;).classes(&quot;text-[9px] bg-red-50 text-red-600 font-bold border border-red-200 px-1 py-0.5 rounded-full&quot;)
with ui.column().classes(&quot;p-0.5 items-center border-x-2 border-
indigo-900 w-full&quot;):
add_90_btn = ui.button(&quot;+ADD MTR&quot;).props(&quot;flat
dense&quot;).classes(&quot;text-[9px] bg-red-50 text-red-600 font-bold border border-red-200 px-1 py-0.5 rounded-full&quot;)
with ui.column().classes(&quot;p-0.5 items-center border-r-2 border-
indigo-900 w-full&quot;):
add_110_btn = ui.button(&quot;+ADD MTR&quot;).props(&quot;flat
dense&quot;).classes(&quot;text-[9px] bg-red-50 text-red-600 font-bold border border-red-200 px-1 py-0.5 rounded-full&quot;)
with ui.column().classes(&quot;p-0.5 items-center w-full&quot;):
add_150_btn = ui.button(&quot;+ADD MTR&quot;).props(&quot;flat
dense&quot;).classes(&quot;text-[9px] bg-red-50 text-red-600 font-bold border border-red-200 px-1 py-0.5 rounded-full&quot;)
with ui.grid(columns=4).classes(&quot;w-full bg-amber-50 text-center border-b-
2 border-indigo-900 items-center&quot;):
m63_lbl = ui.label(&quot;0 MTR&quot;).classes(&quot;py-2 font-extrabold text-amber-
800 text-[11px]&quot;)
m90_lbl = ui.label(&quot;0 MTR&quot;).classes(&quot;py-2 font-extrabold text-amber-
800 text-[11px] border-x-2 border-indigo-900&quot;)
m110_lbl = ui.label(&quot;0 MTR&quot;).classes(&quot;py-2 font-extrabold text-amber-
800 text-[11px] border-r-2 border-indigo-900&quot;)
m150_lbl = ui.label(&quot;0 MTR&quot;).classes(&quot;py-2 font-extrabold text-amber-
800 text-[11px]&quot;)
with ui.grid(columns=4).classes(&quot;w-full bg-orange-50 text-center border-b
border-indigo-900 items-center&quot;):
e63_lbl = ui.label(&quot;&quot;).classes(&quot;py-1 font-bold text-orange-600 text-
[10px]&quot;)
e90_lbl = ui.label(&quot;&quot;).classes(&quot;py-1 font-bold text-orange-600 text-
[10px] border-x-2 border-indigo-900&quot;)
e110_lbl = ui.label(&quot;&quot;).classes(&quot;py-1 font-bold text-orange-600 text-
[10px] border-r-2 border-indigo-900&quot;)
e150_lbl = ui.label(&quot;&quot;).classes(&quot;py-1 font-bold text-orange-600 text-
[10px]&quot;)
with ui.column().classes(&quot;w-full gap-0&quot;):
with ui.grid(columns=1).classes(&quot;w-full bg-gradient-to-r from-slate-
900 via-indigo-950 to-slate-900 text-center&quot;):
pvc_total_lbl = ui.label(&quot;Total PVC Pipes : 0

Quantity&quot;).classes(&quot;py-2 font-bold text-green-300 text-[12px] border-b border-white/10&quot;)
with ui.grid(columns=1).classes(&quot;w-full bg-gradient-to-r from-slate-
800 via-slate-900 to-slate-800 text-center&quot;):
di_total_lbl = ui.label(&quot;Total DI Pipes : 0
Quantity&quot;).classes(&quot;py-2 font-bold text-cyan-300 text-[12px]&quot;)
with ui.grid(columns=1).classes(&quot;w-full bg-gradient-to-r from-amber-
900 to-yellow-900 text-center&quot;):
mtr_total_lbl = ui.label(&quot;Total MTR: 0 MTR&quot;).classes(&quot;py-2.5
font-bold text-yellow-200 text-[12px]&quot;)
with ui.row().classes(&quot;w-full justify-end mt-2&quot;):
ui.button(&quot;Next: Connection&quot;, icon=&quot;arrow_forward&quot;, on_click=lambda:
show_section(&quot;conn&quot;)).props(&quot;rounded dense&quot;).classes(&quot;bg-blue-600 text-white text-[11px] font-bold&quot;)
with conn_section:
ui.label(&quot;Enter Connection&quot;).classes(&quot;text-[13px] font-extrabold text-orange-
700 w-full text-center bg-orange-50 px-3 py-2 rounded-full border border-orange-200&quot;)
# State for connections list for this report
conn_list_state = {&quot;items&quot;: []}
conn_list_container = ui.column().classes(&quot;w-full gap-1 mt-2&quot;)
conn_total_lbl = ui.label(&quot;Total Connections Today: 0&quot;).classes(&quot;text-[11px]
font-extrabold text-green-700 bg-green-50 px-2 py-1 rounded-full text-center w-full border border-green-200 mt-
1&quot;)
def refresh_conn_list():
conn_list_container.clear()
total_sum = 0
try:
for it in conn_list_state[&quot;items&quot;]:
try:
total_sum += float(str(it.get(&#39;conn&#39;,&#39;0&#39;) or 0).strip() or 0)
except:
pass
except:
total_sum = 0
with conn_list_container:
if not conn_list_state[&quot;items&quot;]:
ui.label(&quot;No connections added yet - Click +Add&quot;).classes(&quot;text-
[10px] text-slate-400 text-center w-full py-2&quot;)
else:
for idx, item in enumerate(conn_list_state[&quot;items&quot;], 1):
with ui.row().classes(&quot;w-full bg-white rounded-xl p-2 border
border-orange-100 shadow-sm items-center&quot;):
ui.label(f&quot;{idx}.
{item[&#39;conn&#39;]},{item[&#39;name&#39;]},{item[&#39;mobile&#39;]}&quot;).classes(&quot;text-[11px] font-bold text-slate-800 flex-1&quot;)
# Show sum, not count
if total_sum == int(total_sum):
conn_total_lbl.set_text(f&quot;Total Connections Today: {int(total_sum)}&quot;)
else:
conn_total_lbl.set_text(f&quot;Total Connections Today: {total_sum}&quot;)
try:
if total_sum == int(total_sum):
live_conn_lbl.set_text(f&quot;Connection: {int(total_sum)}&quot;)
live_total_lbl.set_text(f&quot;Total MTR: - | Conn: {int(total_sum)}&quot;)
else:
live_conn_lbl.set_text(f&quot;Connection: {total_sum}&quot;)
live_total_lbl.set_text(f&quot;Total MTR: - | Conn: {total_sum}&quot;)
except:
pass
with ui.dialog() as add_conn_dialog, ui.card().classes(&quot;rounded-2xl p-4 w-
full max-w-sm bg-white shadow-2xl&quot;):
ui.label(&quot;Add Connection&quot;).classes(&quot;text-[14px] font-extrabold text-
orange-700 w-full text-center bg-orange-50 px-3 py-2 rounded-full border border-orange-200&quot;)
conn_no_input = ui.input(&quot;Connection&quot;, placeholder=&quot;Ex:
56&quot;).props(&quot;outlined dense&quot;).classes(&quot;w-full mt-2 font-bold&quot;)

conn_name_input = ui.input(&quot;Enter Name&quot;, placeholder=&quot;Ex:
Mohanlal&quot;).props(&quot;outlined dense&quot;).classes(&quot;w-full mt-1 font-bold&quot;)
conn_mobile_input = ui.input(&quot;Mobile No&quot;, placeholder=&quot;Ex:
9988779988&quot;).props(&quot;outlined dense type=tel&quot;).classes(&quot;w-full mt-1 font-bold&quot;)
with ui.row().classes(&quot;w-full justify-between gap-2 mt-4&quot;):
ui.button(&quot;Cancel&quot;, on_click=add_conn_dialog.close).props(&quot;flat
rounded&quot;).classes(&quot;flex-1 bg-slate-100 text-slate-700 font-bold&quot;)
def do_add_conn():
cno = (conn_no_input.value or &quot;&quot;).strip()
cname = (conn_name_input.value or &quot;&quot;).strip()
cmob = (conn_mobile_input.value or &quot;&quot;).strip()
if not cno:
ui.notify(&quot;Connection No required!&quot;, type=&quot;warning&quot;,
position=&quot;top&quot;)
return
# At least connection no needed, name/mobile optional
conn_list_state[&quot;items&quot;].append({&quot;conn&quot;: cno, &quot;name&quot;: cname,
&quot;mobile&quot;: cmob})
conn_no_input.value = &quot;&quot;; conn_name_input.value = &quot;&quot;;
conn_mobile_input.value = &quot;&quot;
try:
conn_no_input.update(); conn_name_input.update();
conn_mobile_input.update()
except:
pass
add_conn_dialog.close()
refresh_conn_list()
ui.notify(f&quot;✅ Added: {cno},{cname},{cmob}&quot;, type=&quot;positive&quot;,
position=&quot;top&quot;, timeout=1500)
ui.button(&quot;Add&quot;, icon=&quot;add&quot;,
on_click=do_add_conn).props(&quot;rounded&quot;).classes(&quot;flex-1 bg-gradient-to-r from-orange-500 to-red-500 text-white
font-bold&quot;)
with ui.row().classes(&quot;w-full justify-center mt-3&quot;):
ui.button(&quot;+Add Connection&quot;, icon=&quot;add&quot;,
on_click=add_conn_dialog.open).props(&quot;rounded&quot;).classes(&quot;w-full py-2.5 bg-gradient-to-r from-orange-500 to-amber-
600 text-white font-extrabold text-[12px] shadow-lg&quot;)
refresh_conn_list()
with ui.row().classes(&quot;w-full justify-between gap-2 mt-4&quot;):
ui.button(&quot;Back to Pipes&quot;, icon=&quot;arrow_back&quot;, on_click=lambda:
show_section(&quot;pipe&quot;)).props(&quot;flat rounded dense&quot;).classes(&quot;text-[11px] bg-slate-100&quot;)
ui.button(&quot;Next: Save&quot;, icon=&quot;arrow_forward&quot;, on_click=lambda:
show_section(&quot;save&quot;)).props(&quot;rounded dense&quot;).classes(&quot;text-[11px] bg-blue-600 text-white font-bold&quot;)
with save_section:
ui.label(&quot;Save Report&quot;).classes(&quot;text-[13px] font-extrabold text-green-700 w-
full text-center bg-green-50 px-3 py-2 rounded-full border border-green-200&quot;)
with ui.column().classes(&quot;w-full bg-slate-50 rounded-xl p-3 gap-1 mt-2
border&quot;):
live_area_lbl = ui.label(&quot;Area: -&quot;).classes(&quot;text-[11px] font-bold text-
slate-700&quot;)
live_labour_lbl = ui.label(&quot;Labour: -&quot;).classes(&quot;text-[11px] font-bold
text-slate-700&quot;)
live_conn_lbl = ui.label(&quot;Connection: -&quot;).classes(&quot;text-[11px] font-bold
text-orange-700&quot;)
live_total_lbl = ui.label(&quot;Total MTR: 0 MTR&quot;).classes(&quot;text-[12px] font-
extrabold text-green-700 mt-1&quot;)
save_btn = ui.button(&quot;⚡ Save&quot;, icon=&quot;save&quot;).props(&quot;rounded&quot;).classes(&quot;w-full
mt-3 py-3 bg-gradient-to-r from-blue-600 to-indigo-600 text-white font-extrabold text-[13px] shadow-lg&quot;)
with ui.row().classes(&quot;w-full justify-between gap-2 mt-2&quot;):
ui.button(&quot;Back to Connection&quot;, icon=&quot;arrow_back&quot;, on_click=lambda:
show_section(&quot;conn&quot;)).props(&quot;flat rounded dense&quot;).classes(&quot;text-[11px] bg-slate-100&quot;)
ui.button(&quot;Back to Pipes&quot;, icon=&quot;pie_chart&quot;, on_click=lambda:

show_section(&quot;pipe&quot;)).props(&quot;flat rounded dense&quot;).classes(&quot;text-[11px] bg-slate-100&quot;)
new_report_btn.on_click(new_report_dialog.open)
with ui.dialog() as extra_63_dialog, ui.card().classes(&quot;rounded-2xl p-4 w-full max-w-xs
bg-white shadow-2xl&quot;):
ui.label(&quot;Enter Extra Meter for 63MM Pipe&quot;).classes(&quot;text-sm font-extrabold text-
slate-800 text-center w-full&quot;)
extra_63_input = ui.input(placeholder=&quot;Ex: 5&quot;, value=&quot;&quot;).props(&quot;type=number outlined
dense autofocus&quot;).classes(&quot;w-full font-bold text-center&quot;)
with ui.row().classes(&quot;w-full justify-between gap-2 mt-3&quot;):
ui.button(&quot;Cancel&quot;, on_click=extra_63_dialog.close).props(&quot;flat
rounded&quot;).classes(&quot;flex-1 bg-slate-100&quot;)
def set_extra_63():
try:
v = float(extra_63_input.value or 0)
extra_state[&quot;63&quot;] = v
extra_63_dialog.close()
update_live_preview()
ui.notify(f&quot;Extra 63MM: {v} MTR added&quot;, type=&quot;positive&quot;, timeout=2000)
except:
ui.notify(&quot;Enter valid number&quot;, type=&quot;warning&quot;)
ui.button(&quot;Add&quot;, icon=&quot;check&quot;,
on_click=set_extra_63).props(&quot;rounded&quot;).classes(&quot;flex-1 bg-red-500 text-white font-bold&quot;)
with ui.dialog() as extra_90_dialog, ui.card().classes(&quot;rounded-2xl p-4 w-full max-w-xs
bg-white shadow-2xl&quot;):
ui.label(&quot;Enter Extra Meter for 90MM Pipe&quot;).classes(&quot;text-sm font-extrabold text-
slate-800 text-center w-full&quot;)
extra_90_input = ui.input(placeholder=&quot;Ex: 5&quot;, value=&quot;&quot;).props(&quot;type=number outlined
dense autofocus&quot;).classes(&quot;w-full font-bold text-center&quot;)
with ui.row().classes(&quot;w-full justify-between gap-2 mt-3&quot;):
ui.button(&quot;Cancel&quot;, on_click=extra_90_dialog.close).props(&quot;flat
rounded&quot;).classes(&quot;flex-1 bg-slate-100&quot;)
def set_extra_90():
try:
v = float(extra_90_input.value or 0)
extra_state[&quot;90&quot;] = v
extra_90_dialog.close()
update_live_preview()
ui.notify(f&quot;Extra 90MM: {v} MTR added&quot;, type=&quot;positive&quot;, timeout=2000)
except:
ui.notify(&quot;Enter valid number&quot;, type=&quot;warning&quot;)
ui.button(&quot;Add&quot;, icon=&quot;check&quot;,
on_click=set_extra_90).props(&quot;rounded&quot;).classes(&quot;flex-1 bg-red-500 text-white font-bold&quot;)
with ui.dialog() as extra_110_dialog, ui.card().classes(&quot;rounded-2xl p-4 w-full max-w-xs
bg-white shadow-2xl&quot;):
ui.label(&quot;Enter Extra Meter for 110MM Pipe&quot;).classes(&quot;text-sm font-extrabold text-
slate-800 text-center w-full&quot;)
extra_110_input = ui.input(placeholder=&quot;Ex: 5&quot;, value=&quot;&quot;).props(&quot;type=number outlined
dense autofocus&quot;).classes(&quot;w-full font-bold text-center&quot;)
with ui.row().classes(&quot;w-full justify-between gap-2 mt-3&quot;):
ui.button(&quot;Cancel&quot;, on_click=extra_110_dialog.close).props(&quot;flat
rounded&quot;).classes(&quot;flex-1 bg-slate-100&quot;)
def set_extra_110():
try:
v = float(extra_110_input.value or 0)
extra_state[&quot;110&quot;] = v
extra_110_dialog.close()
update_live_preview()
ui.notify(f&quot;Extra 110MM: {v} MTR added&quot;, type=&quot;positive&quot;, timeout=2000)
except:
ui.notify(&quot;Enter valid number&quot;, type=&quot;warning&quot;)

ui.button(&quot;Add&quot;, icon=&quot;check&quot;,
on_click=set_extra_110).props(&quot;rounded&quot;).classes(&quot;flex-1 bg-red-500 text-white font-bold&quot;)
with ui.dialog() as extra_150_dialog, ui.card().classes(&quot;rounded-2xl p-4 w-full max-w-xs
bg-white shadow-2xl&quot;):
ui.label(&quot;Enter Extra Meter for 150MM DI Pipe&quot;).classes(&quot;text-sm font-extrabold text-
slate-800 text-center w-full&quot;)
extra_150_input = ui.input(placeholder=&quot;Ex: 5&quot;, value=&quot;&quot;).props(&quot;type=number outlined
dense autofocus&quot;).classes(&quot;w-full font-bold text-center&quot;)
with ui.row().classes(&quot;w-full justify-between gap-2 mt-3&quot;):
ui.button(&quot;Cancel&quot;, on_click=extra_150_dialog.close).props(&quot;flat
rounded&quot;).classes(&quot;flex-1 bg-slate-100&quot;)
def set_extra_150():
try:
v = float(extra_150_input.value or 0)
extra_state[&quot;150&quot;] = v
extra_150_dialog.close()
update_live_preview()
ui.notify(f&quot;Extra 150MM: {v} MTR added&quot;, type=&quot;positive&quot;, timeout=2000)
except:
ui.notify(&quot;Enter valid number&quot;, type=&quot;warning&quot;)
ui.button(&quot;Add&quot;, icon=&quot;check&quot;,
on_click=set_extra_150).props(&quot;rounded&quot;).classes(&quot;flex-1 bg-red-500 text-white font-bold&quot;)
add_63_btn.on_click(extra_63_dialog.open)
add_90_btn.on_click(extra_90_dialog.open)
add_110_btn.on_click(extra_110_dialog.open)
add_150_btn.on_click(extra_150_dialog.open)
def parse_qty(val):
try:
if val in (None, &quot;&quot;):
return 0
s = str(val).strip()
if s.startswith(&quot;-&quot;):
return 0
v = float(s)
if v &lt; 0:
return 0
return v
except:
return 0
def update_live_preview():
def fast_parse(v):
try:
if not v: return 0
s=str(v).strip()
if s.startswith(&quot;-&quot;): return 0
return float(s) if s else 0
except: return 0
q63 = fast_parse(c63.value); q90 = fast_parse(c90.value); q110 =
fast_parse(c110.value); q150 = fast_parse(c150.value)
ex63 = extra_state.get(&quot;63&quot;,0); ex90 = extra_state.get(&quot;90&quot;,0); ex110 =
extra_state.get(&quot;110&quot;,0); ex150 = extra_state.get(&quot;150&quot;,0)
pm63 = pipe_mtr_state.get(&quot;63&quot;,6.0); pm90 = pipe_mtr_state.get(&quot;90&quot;,6.0); pm110 =
pipe_mtr_state.get(&quot;110&quot;,6.0); pm150 = pipe_mtr_state.get(&quot;150&quot;,5.5)
m63 = q63*pm63 + ex63; m90 = q90*pm90 + ex90; m110 = q110*pm110 + ex110; m150 =
q150*pm150 + ex150
total_mtr = m63+m90+m110+m150
total_extra = ex63+ex90+ex110+ex150
pvc_total_lbl.set_text(f&quot;Total PVC Pipes : {q63+q90+q110} Quantity&quot;)
di_total_lbl.set_text(f&quot;Total DI Pipes : {q150} Quantity&quot;)
if total_extra&gt;0:
mtr_total_lbl.set_text(f&quot;Total MTR: {total_mtr} MTR (Pipe:{total_mtr-total_extra}
+ Extra:{total_extra})&quot;)

else:
mtr_total_lbl.set_text(f&quot;Total MTR: {total_mtr} MTR&quot;)
m63_lbl.set_text(f&quot;{m63:.1f} MTR&quot; if m63!=int(m63) else f&quot;{int(m63)} MTR&quot;)
m90_lbl.set_text(f&quot;{m90:.1f} MTR&quot; if m90!=int(m90) else f&quot;{int(m90)} MTR&quot;)
m110_lbl.set_text(f&quot;{m110:.1f} MTR&quot; if m110!=int(m110) else f&quot;{int(m110)} MTR&quot;)
m150_lbl.set_text(f&quot;{m150:.1f} MTR&quot; if m150!=int(m150) else f&quot;{int(m150)} MTR&quot;)
e63_lbl.set_text(f&quot;+{ex63} Extra&quot; if ex63&gt;0 else &quot;&quot;)
e90_lbl.set_text(f&quot;+{ex90} Extra&quot; if ex90&gt;0 else &quot;&quot;)
e110_lbl.set_text(f&quot;+{ex110} Extra&quot; if ex110&gt;0 else &quot;&quot;)
e150_lbl.set_text(f&quot;+{ex150} Extra&quot; if ex150&gt;0 else &quot;&quot;)
add_63_btn.set_text(f&quot;+{ex63} MTR&quot; if ex63&gt;0 else &quot;+ADD MTR&quot;)
add_90_btn.set_text(f&quot;+{ex90} MTR&quot; if ex90&gt;0 else &quot;+ADD MTR&quot;)
add_110_btn.set_text(f&quot;+{ex110} MTR&quot; if ex110&gt;0 else &quot;+ADD MTR&quot;)
add_150_btn.set_text(f&quot;+{ex150} MTR&quot; if ex150&gt;0 else &quot;+ADD MTR&quot;)
try:
live_area_lbl.set_text(f&quot;Area: {(area_input.value or &#39;&#39;).strip() or &#39;-&#39;}&quot;)
live_labour_lbl.set_text(f&quot;Labour: {(labour_input.value or &#39;&#39;).strip() or &#39;-&#39;}&quot;)
conn_txt = conn_total_lbl.text.replace(&quot;Total Connections Today: &quot;, &quot;&quot;).strip()
if &quot;conn_total_lbl&quot; in locals() else &quot;-&quot;
live_conn_lbl.set_text(f&quot;Connection: {conn_txt}&quot;)
live_total_lbl.set_text(f&quot;Total MTR: {total_mtr} MTR&quot;)
except:
pass
c63.on_value_change(lambda _: update_live_preview())
c90.on_value_change(lambda _: update_live_preview())
c110.on_value_change(lambda _: update_live_preview())
c150.on_value_change(lambda _: update_live_preview())
c63.on(&quot;input&quot;, lambda _: update_live_preview())
c90.on(&quot;input&quot;, lambda _: update_live_preview())
c110.on(&quot;input&quot;, lambda _: update_live_preview())
c150.on(&quot;input&quot;, lambda _: update_live_preview())
def save_daily_report():
q63 = parse_qty(c63.value); q90 = parse_qty(c90.value); q110 = parse_qty(c110.value);
q150 = parse_qty(c150.value)
ex63 = extra_state.get(&quot;63&quot;,0); ex90 = extra_state.get(&quot;90&quot;,0); ex110 =
extra_state.get(&quot;110&quot;,0); ex150 = extra_state.get(&quot;150&quot;,0)
pm63 = pipe_mtr_state.get(&quot;63&quot;,6.0); pm90 = pipe_mtr_state.get(&quot;90&quot;,6.0); pm110 =
pipe_mtr_state.get(&quot;110&quot;,6.0); pm150 = pipe_mtr_state.get(&quot;150&quot;,5.5)
total_mtr_calc =
(q63*pm63+ex63)+(q90*pm90+ex90)+(q110*pm110+ex110)+(q150*pm150+ex150)
try:
selected_date = datetime.datetime.strptime((home_date_input.value or &quot;&quot;).strip(),
&quot;%Y-%m-%d&quot;).date()
except Exception:
selected_date = today_ist()
area_val = (area_input.value or &quot;&quot;).strip()
labour_val = (labour_input.value or &quot;&quot;).strip()
# New: connections list - sum of connection numbers
conn_items = []
try:
conn_items = list(conn_list_state.get(&quot;items&quot;, []))
except:
conn_items = []
conn_sum = 0
try:
for it in conn_items:
try:
conn_sum += float(str(it.get(&#39;conn&#39;,&#39;0&#39;) or 0).strip() or 0)
except:
pass
except:
conn_sum = 0
if conn_sum == int(conn_sum):

conn_val = str(int(conn_sum)) if conn_sum!=0 else &quot;&quot;
else:
conn_val = str(conn_sum) if conn_sum!=0 else &quot;&quot;
conn_detail_str = &quot;&quot;
try:
if conn_items:
conn_detail_str = &quot;;
&quot;.join([f&quot;{it.get(&#39;conn&#39;,&#39;&#39;)},{it.get(&#39;name&#39;,&#39;&#39;)},{it.get(&#39;mobile&#39;,&#39;&#39;)}&quot; for it in conn_items])
except:
conn_detail_str = &quot;&quot;
if not area_val: ui.notify(&quot;Please Enter Area!&quot;, type=&quot;warning&quot;, position=&quot;top&quot;);
return
if area_val not in (CACHE[&quot;areas&quot;].get(user.id, [])):
SavedArea.objects.get_or_create(user=user, area_name=area_val)
CACHE[&quot;areas&quot;].pop(user.id, None)
if labour_val:
if HAS_LABOUR_MODEL:
try:
SavedLabour.objects.get_or_create(user=user, labour_name=labour_val)
except:
pass
if &quot;labours&quot; in CACHE and user.id in CACHE[&quot;labours&quot;]:
CACHE[&quot;labours&quot;].pop(user.id, None)
current_title = (title_input.value or &quot;&quot;).strip()
if not current_title:
current_title = &quot;Veraval site&quot;
if current_title != user.default_report_title:
user.default_report_title = current_title
user.save(update_fields=[&#39;default_report_title&#39;])
CACHE[&quot;users&quot;][user.email] = user
report_obj = None
try:
report_obj = DailyReport.objects.create(
user=user, report_title=current_title, report_date=selected_date,
area_name=area_val, labour_name=labour_val, connection=conn_val,
qty_63mm=q63, qty_90mm=q90, qty_110mm=q110, qty_150mm=q150,
extra_63mm=ex63, extra_90mm=ex90, extra_110mm=ex110, extra_150mm=ex150,
total_mtr=total_mtr_calc,
total_pvc=q63+q90+q110, total_di=q150, total_qty=q63+q90+q110+q150,
price_sum=float(total_mtr_calc)
)
# Save individual connections
try:
from models_app.models import ConnectionEntry
for it in conn_items:
ConnectionEntry.objects.create(
user=user, report=report_obj, report_date=selected_date,
connection_no=str(it.get(&#39;conn&#39;,&#39;&#39;)).strip(),
name=str(it.get(&#39;name&#39;,&#39;&#39;)).strip(),
mobile=str(it.get(&#39;mobile&#39;,&#39;&#39;)).strip(),
area_name=area_val
)
except Exception as ce:
print(f&quot;ConnectionEntry save fail: {ce}&quot;)
except Exception as ex:
print(f&quot;Save with extra failed: {ex}&quot;)
try:
if report_obj is None:
report_obj = DailyReport.objects.create(user=user,
report_title=current_title, report_date=selected_date, area_name=area_val, labour_name=labour_val,
connection=conn_val, qty_63mm=q63, qty_90mm=q90, qty_110mm=q110, qty_150mm=q150, total_pvc=q63+q90+q110,
total_di=q150, total_qty=q63+q90+q110+q150, total_mtr=total_mtr_calc, price_sum=float(total_mtr_calc))
try:

from models_app.models import ConnectionEntry
for it in conn_items:
ConnectionEntry.objects.create(user=user, report=report_obj,
report_date=selected_date, connection_no=str(it.get(&#39;conn&#39;,&#39;&#39;)).strip(), name=str(it.get(&#39;name&#39;,&#39;&#39;)).strip(),
mobile=str(it.get(&#39;mobile&#39;,&#39;&#39;)).strip(), area_name=area_val)
except Exception as ce2:
print(f&quot;Conn save fail2: {ce2}&quot;)
except Exception as ex2:
if report_obj is None:
report_obj = DailyReport.objects.create(user=user,
report_title=current_title, report_date=selected_date, area_name=area_val, qty_63mm=q63, qty_90mm=q90,
qty_110mm=q110, qty_150mm=q150, total_qty=q63+q90+q110+q150, price_sum=float(total_mtr_calc))
try:
from models_app.models import ConnectionEntry
for it in conn_items:
ConnectionEntry.objects.create(user=user, report=report_obj,
report_date=selected_date, connection_no=str(it.get(&#39;conn&#39;,&#39;&#39;)).strip(), name=str(it.get(&#39;name&#39;,&#39;&#39;)).strip(),
mobile=str(it.get(&#39;mobile&#39;,&#39;&#39;)).strip(), area_name=area_val)
except:
pass
c63.value = &quot;&quot;; c90.value = &quot;&quot;; c110.value = &quot;&quot;; c150.value = &quot;&quot;;
try:
conn_list_state[&quot;items&quot;] = []
refresh_conn_list()
except:
pass
extra_state[&quot;63&quot;]=0; extra_state[&quot;90&quot;]=0; extra_state[&quot;110&quot;]=0; extra_state[&quot;150&quot;]=0;
extra_63_input.value=&quot;&quot;; extra_90_input.value=&quot;&quot;; extra_110_input.value=&quot;&quot;;
extra_150_input.value=&quot;&quot;;
update_live_preview()
try:
app.storage.user[&quot;default_area_name&quot;] = area_val
app.storage.user[&quot;default_labour_name&quot;] = labour_val
user.default_area_name = area_val
user.default_labour_name = labour_val
user.save(update_fields=[&#39;default_area_name&#39;, &#39;default_labour_name&#39;])
CACHE[&quot;users&quot;][user.email] = user
except Exception as e:
print(f&quot;Persist area/labour fail: {e}&quot;)
try:
app.storage.user[&quot;default_area_name&quot;] = area_val
app.storage.user[&quot;default_labour_name&quot;] = labour_val
except:
pass
ui.notify(f&quot;✅ Saved! Area:{area_val} MTR:{total_mtr_calc}
(Extra:{ex63+ex90+ex110+ex150})&quot;, type=&quot;positive&quot;, position=&quot;top&quot;, timeout=3000)
try:
new_report_dialog.close()
except:
pass
save_btn.on_click(save_daily_report)
def build_filter():
filter_view.clear()
user = state[&quot;user&quot;]
if not user:
show_login()
return
try:
fresh = AppUser.objects.get(id=user.id)
user.default_report_title = fresh.default_report_title
state[&quot;user&quot;] = fresh
user = fresh

except:
pass
today = today_ist(); months = {1: &quot;Jan&quot;, 2: &quot;Feb&quot;, 3: &quot;Mar&quot;, 4: &quot;Apr&quot;, 5: &quot;May&quot;, 6: &quot;Jun&quot;, 7: &quot;Jul&quot;,
8: &quot;Aug&quot;, 9: &quot;Sep&quot;, 10: &quot;Oct&quot;, 11: &quot;Nov&quot;, 12: &quot;Dec&quot;}; years = {y: str(y) for y in range(today.year - 5,
today.year + 2)}
with filter_view:
with ui.column().classes(&quot;w-full max-w-md items-center gap-2&quot;):
with ui.card().classes(&quot;w-full rounded-3xl shadow-2xl bg-white p-3 sm:p-5 border-2 border-
green-200&quot;):
with ui.row().classes(&quot;w-full justify-between items-center mb-2&quot;):
ui.button(&quot;Back to Home&quot;, icon=&quot;arrow_back&quot;, on_click=show_home).props(&quot;flat rounded
no-caps&quot;).classes(&quot;back-btn text-xs&quot;)
with ui.row().classes(&quot;w-full justify-center my-1.5&quot;):
ui.label(user.default_report_title).classes(&quot;w-full px-2 py-1.5 rounded-full bg-
gradient-to-r from-cyan-200 via-purple-200 to-fuchsia-300 text-slate-900 font-extrabold text-center text-xs&quot;)
with ui.grid(columns=3).classes(&quot;w-full gap-1.5 my-2.5 bg-green-50 p-2 rounded-2xl border
border-green-200&quot;):
date_options = {&quot;&quot;: &quot;Select Date&quot;, **{str(d): f&quot;{d:02d}&quot; for d in range(1, 32)}};
day_select = ui.select(options=date_options, value=&quot;&quot;, label=&quot;Date&quot;).props(&quot;outlined rounded dense
color=green&quot;).classes(&quot;w-full bg-white font-semibold text-xs&quot;)
month_select = ui.select(options=months, value=today.month,
label=&quot;Month&quot;).props(&quot;outlined rounded dense color=green&quot;).classes(&quot;w-full bg-white font-semibold text-xs&quot;)
year_select = ui.select(options=years, value=today.year,
label=&quot;Year&quot;).props(&quot;outlined rounded dense color=green&quot;).classes(&quot;w-full bg-white font-semibold text-xs&quot;)
table_container = ui.column().classes(&quot;w-full mt-1 gap-2&quot;)
def load_table_data():
table_container.clear()
sel_month = int(month_select.value); sel_year = int(year_select.value); sel_day =
day_select.value
base_qs = DailyReport.objects.filter(user=user, report_date__year=sel_year,
report_date__month=sel_month)
if not base_qs.exists():
with table_container:
with ui.card().classes(&quot;w-full p-5 rounded-2xl bg-red-50 border-2 border-red-
200 items-center text-center shadow-sm&quot;):
ui.icon(&quot;info&quot;, size=&quot;2.2rem&quot;, color=&quot;red&quot;); ui.label(&quot;No
Data&quot;).classes(&quot;text-sm font-extrabold text-red-700 mt-1&quot;)
return
if sel_day:
qs = base_qs.filter(report_date__day=int(sel_day)).order_by(&#39;-id&#39;)
period_text = f&quot;Date: {int(sel_day):02d} {months[sel_month]} {sel_year}&quot;
with table_container:
if not qs.exists():
with ui.card().classes(&quot;w-full p-5 rounded-2xl bg-red-50 border-2 border-
red-200 items-center text-center shadow-sm&quot;):
ui.icon(&quot;info&quot;, size=&quot;2.2rem&quot;, color=&quot;red&quot;); ui.label(&quot;No
Data&quot;).classes(&quot;text-sm font-extrabold text-red-700 mt-1&quot;)
return
agg = qs.aggregate(t=Sum(&#39;total_qty&#39;)); grand_total = agg[&#39;t&#39;] or 0
day_total_conn = 0
try:
from models_app.models import ConnectionEntry
if qs.exists():
entries = ConnectionEntry.objects.filter(user=user,
report_date=qs.first().report_date)
for ce in entries:
try:
day_total_conn += float(str(ce.connection_no or 0).strip() or
0)
except:
pass
if day_total_conn == 0:
for r in qs:
try:

cv = getattr(r, &#39;connection&#39;, &#39;&#39;) or &#39;&#39;
if cv:
day_total_conn += float(str(cv).strip() or 0)
except:
pass
except Exception as e:
print(f&quot;Daily conn sum fail: {e}&quot;)
with ui.row().classes(&quot;w-full justify-between items-center mb-2 px-1&quot;):
ui.badge(period_text, color=&quot;green&quot;).classes(&quot;text-xs font-bold px-2 py-
1&quot;); ui.badge(f&quot;Total: {grand_total} Qty&quot;, color=&quot;green&quot;).classes(&quot;text-xs font-bold px-2 py-1&quot;);
ui.badge(f&quot;Conn: {day_total_conn}&quot;, color=&quot;orange&quot;).classes(&quot;text-xs font-bold px-2 py-1&quot;)
for report in qs[:50]:
area_display = report.area_name or &quot;No Area&quot;
with ui.card().classes(&quot;report-patti w-full rounded-2xl border-2 border-
green-200 bg-gradient-to-r from-white to-green-50 p-0 overflow-hidden shadow-md&quot;):
with ui.column().classes(&quot;patti-click-area w-full p-3 pb-
1&quot;).on(&quot;click&quot;, lambda r=report: show_filter_detail(r)):
with ui.row().classes(&quot;w-full justify-between items-center&quot;):
with ui.row().classes(&quot;items-center gap-2&quot;):
ui.icon(&quot;location_on&quot;, color=&quot;green&quot;, size=&quot;1.1rem&quot;); ui.label(area_display).classes(&quot;font-extrabold text-[15px]
text-indigo-900&quot;)
ui.badge(f&quot;{report.report_date.strftime(&#39;%d-%m-%Y&#39;)}&quot;,
color=&quot;grey&quot;).classes(&quot;text-[10px]&quot;)
ui.label(report.report_title).classes(&quot;text-xs font-semibold
text-slate-700 mt-1 w-full truncate&quot;)
# Show connection if exists
conn_disp = get_q(report, &#39;connection&#39;, &#39;&#39;)
if conn_disp:
ui.label(f&quot;�� Connection: {conn_disp}&quot;).classes(&quot;text-[11px
font-extrabold text-orange-700 bg-orange-50 px-2 py-0.5 rounded-full mt-1&quot;)
with ui.row().classes(&quot;w-full justify-between items-center mt-
1&quot;):
ui.label(f&quot;63:{get_q(report,&#39;qty_63mm&#39;)} |
90:{get_q(report,&#39;qty_90mm&#39;)} | 110:{get_q(report,&#39;qty_110mm&#39;)} |
150DI:{get_q(report,&#39;qty_150mm&#39;)}&quot;).classes(&quot;text-[13px] font-bold text-slate-700&quot;)
ui.label(f&quot;Total: {report.total_qty} Qty&quot;).classes(&quot;text-
[14px] font-extrabold text-emerald-600&quot;)
with ui.row().classes(&quot;w-full justify-end gap-2 px-3 pb-3 pt-1&quot;):
edit_btn = ui.button(&quot;Edit&quot;, icon=&quot;edit&quot;).props(&quot;dense
rounded&quot;).classes(&quot;px-4 py-1.5 bg-yellow-400 text-black font-extrabold text-[13px] border-2 border-yellow-500
shadow-sm&quot;)
del_btn = ui.button(&quot;Delete&quot;, icon=&quot;delete&quot;).props(&quot;dense
rounded&quot;).classes(&quot;px-4 py-1.5 bg-red-600 text-yellow-200 font-extrabold text-[13px] border-2 border-red-700
shadow-md&quot;)
with ui.dialog() as edit_dialog, ui.card().classes(&quot;rounded-2xl
p-0 w-full max-w-md shadow-2xl max-h-[80vh] flex flex-col&quot;):
with ui.column().classes(&quot;w-full p-0 gap-0 flex flex-col h-
full&quot;):
with ui.row().classes(&quot;w-full bg-gradient-to-r from-blue-
500 to-blue-600 p-2.5 items-center justify-between text-white shrink-0&quot;):
ui.label(f&quot;✏ Edit - {area_display}&quot;).classes(&quot;font-
extrabold text-[12px] text-white&quot;)
ui.button(icon=&quot;close&quot;,
on_click=edit_dialog.close).props(&quot;flat round dense color=white size=sm&quot;).classes(&quot;text-white&quot;)
with ui.column().classes(&quot;w-full p-2.5 gap-1.5 bg-white
overflow-y-auto flex-1&quot;):
ui.label(&quot;Date&quot;).classes(&quot;text-[11px] font-bold text-
slate-700&quot;)
e_date =
ui.input(value=report.report_date.isoformat()).props(&quot;type=date outlined dense&quot;).classes(&quot;w-full&quot;)
ui.label(&quot;Area Name&quot;).classes(&quot;text-[11px] font-bold
text-slate-700&quot;)
e_area =
ui.input(value=report.area_name).props(&quot;outlined dense&quot;).classes(&quot;w-full font-bold&quot;)

ui.label(&quot;Labour Name&quot;).classes(&quot;text-[11px] font-
bold text-slate-700&quot;)
e_labour =
ui.input(value=get_q(report,&#39;labour_name&#39;,&#39;&#39;)).props(&quot;outlined dense&quot;).classes(&quot;w-full font-bold&quot;)
ui.label(&quot;Connection (Sum)&quot;).classes(&quot;text-[11px]
font-bold text-orange-700&quot;)
edit_conn_state = {&quot;items&quot;: []}
try:
from models_app.models import ConnectionEntry
existing =
list(ConnectionEntry.objects.filter(report=report).order_by(&#39;id&#39;))
if not existing:
existing =
list(ConnectionEntry.objects.filter(user=report.user, report_date=report.report_date,
area_name=report.area_name).order_by(&#39;id&#39;))
for ce in existing:
edit_conn_state[&quot;items&quot;].append({&quot;conn&quot;:
ce.connection_no, &quot;name&quot;: ce.name, &quot;mobile&quot;: ce.mobile, &quot;id&quot;: ce.id})
except Exception as ee:
print(f&quot;Edit conn load fail: {ee}&quot;)
edit_conn_total = ui.label(&quot;Total: 0&quot;).classes(&quot;text-
[11px] font-bold text-green-700 bg-green-50 px-2 py-1 rounded-full text-center w-full border mt-1&quot;)
del_target = {&quot;idx&quot;: -1}
# Delete confirmation dialog (single, reused)
with ui.dialog() as del_confirm_dialog,
ui.card().classes(&quot;rounded-2xl p-0 w-full max-w-sm shadow-2xl overflow-hidden&quot;):
with ui.column().classes(&quot;w-full p-0 gap-0&quot;):
with ui.row().classes(&quot;w-full bg-gradient-to-
r from-red-500 to-orange-600 p-3 items-center text-white&quot;):
ui.icon(&quot;warning&quot;, size=&quot;1.2rem&quot;)
ui.label(&quot;Confirm Delete&quot;).classes(&quot;font-
extrabold text-[13px] text-white&quot;)
with ui.column().classes(&quot;w-full p-4 gap-3
bg-white&quot;):
del_msg = ui.label(&quot;This data will be
deleted&quot;).classes(&quot;text-[12px] font-bold text-slate-700 w-full text-center bg-red-50 p-3 rounded-xl border
border-red-200&quot;)
ui.label(&quot;Are you sure you want to delete
this connection?&quot;).classes(&quot;text-[11px] text-slate-500 w-full text-center&quot;)
with ui.row().classes(&quot;w-full justify-
between gap-2 mt-1&quot;):
ui.button(&quot;Cancel&quot;, icon=&quot;close&quot;,
on_click=del_confirm_dialog.close).props(&quot;flat rounded&quot;).classes(&quot;flex-1 bg-slate-100 text-slate-700 font-bold
text-[12px]&quot;)
def do_confirm_delete():
idx = del_target[&quot;idx&quot;]
if 0 &lt;= idx &lt;
len(edit_conn_state[&quot;items&quot;]):
edit_conn_state[&quot;items&quot;].pop(idx)
del_confirm_dialog.close()
refresh_edit_conn_list.refresh()
ui.notify(&quot;��️ Deleted! No
click main Edit to save.&quot;, type=&quot;positive&quot;, position=&quot;top&quot;, timeout=2000)
else:
del_confirm_dialog.close()
ui.button(&quot;Delete&quot;, icon=&quot;delete&quot;,
on_click=do_confirm_delete).props(&quot;rounded&quot;).classes(&quot;flex-1 bg-gradient-to-r from-red-600 to-red-700 text-white
font-bold text-[12px]&quot;)
@ui.refreshable
def refresh_edit_conn_list():

total = 0
for it in edit_conn_state[&quot;items&quot;]:
try:
c = str(it.get(&#39;conn&#39;,&#39;0&#39;) or
0).replace(&#39;,&#39;,&#39;&#39;).strip()
if &#39;+&#39; in c:
c = c.split(&#39;+&#39;)[0]
total += float(c or 0)
except:
pass
if total == int(total):
edit_conn_total.set_text(f&quot;Total Connections
Today: {int(total)}&quot;)
else:
edit_conn_total.set_text(f&quot;Total Connections
Today: {total}&quot;)
if not edit_conn_state[&quot;items&quot;]:
ui.label(&quot;No connections&quot;).classes(&quot;text-
[10px] text-slate-400 text-center w-full py-2&quot;)
else:
for idx, item in
enumerate(edit_conn_state[&quot;items&quot;]):
with ui.row().classes(&quot;w-full bg-white
rounded-lg p-2 border border-orange-100 items-center justify-between shadow-sm mb-1&quot;):
ui.label(f&quot;{idx+1}.
{item[&#39;conn&#39;]},{item[&#39;name&#39;]},{item[&#39;mobile&#39;]}&quot;).classes(&quot;text-[11px] font-bold text-slate-800 flex-1&quot;)
with ui.row().classes(&quot;gap-0&quot;):
def make_edit(i=idx):
def edit_fn():
# Create fresh dialog
with current item&#39;s data - ensures correct data shows
cur =
edit_conn_state[&quot;items&quot;][i]
print(f&quot;EDIT click
idx={i} data={cur}&quot;)
with ui.dialog() as
dyn_edit_dialog, ui.card().classes(&quot;rounded-2xl p-4 w-full max-w-sm bg-white shadow-2xl&quot;):
ui.label(&quot;Edit
Connection&quot;).classes(&quot;text-[14px] font-extrabold text-blue-700 w-full text-center bg-blue-50 px-3 py-2 rounded-
full border&quot;)
# Pre-fill with
CURRENT row data
e_conn =
ui.input(&quot;Connection&quot;, value=str(cur.get(&#39;conn&#39;,&#39;&#39;))).props(&quot;outlined dense&quot;).classes(&quot;w-full mt-2 font-bold&quot;)
e_name =
ui.input(&quot;Enter Name&quot;, value=str(cur.get(&#39;name&#39;,&#39;&#39;))).props(&quot;outlined dense&quot;).classes(&quot;w-full mt-1 font-bold&quot;)
e_mob =
ui.input(&quot;Mobile No&quot;, value=str(cur.get(&#39;mobile&#39;,&#39;&#39;))).props(&quot;outlined dense&quot;).classes(&quot;w-full mt-1 font-bold&quot;)
with
ui.row().classes(&quot;w-full justify-between gap-2 mt-4&quot;):
ui.button(&quot;Cancel&quot;, on_click=dyn_edit_dialog.close).props(&quot;flat rounded&quot;).classes(&quot;flex-1 bg-slate-100 font-
bold&quot;)
def do_update():
cno =
(e_conn.value or &quot;&quot;).strip()
if not cno:
ui.notify(&quot;Connection required!&quot;, type=&quot;warning&quot;)
return
edit_conn_state[&quot;items&quot;][i] = {&quot;conn&quot;: cno, &quot;name&quot;: (e_name.value or &quot;&quot;).strip(), &quot;mobile&quot;: (e_mob.value or
&quot;&quot;).strip(), &quot;id&quot;: edit_conn_state[&quot;items&quot;][i].get(&quot;id&quot;)}
dyn_edit_dialog.close()
refresh_edit_conn_list.refresh()
ui.notify(f&quot;✏️ Updated! Now click main Edit to save.&quot;, type=&quot;positive&quot;, position=&quot;top&quot;, timeout=1500)

ui.button(&quot;Update&quot;, icon=&quot;check&quot;, on_click=do_update).props(&quot;rounded&quot;).classes(&quot;flex-1 bg-blue-600 text-white
font-bold&quot;)
dyn_edit_dialog.open()
return edit_fn
def make_del(i=idx):
def del_fn():
del_target[&quot;idx&quot;] = i
try:
p =
edit_conn_state[&quot;items&quot;][i]
del_msg.set_text(f&quot;This data will be deleted: {p.get(&#39;conn&#39;,&#39;&#39;)},{p.get(&#39;name&#39;,&#39;&#39;)},{p.get(&#39;mobile&#39;,&#39;&#39;)}&quot;)
except:
del_msg.set_text(&quot;This data will be deleted&quot;)
del_confirm_dialog.open()
return del_fn
ui.button(icon=&quot;edit&quot;,
on_click=make_edit()).props(&quot;flat round dense color=blue size=sm&quot;).classes(&quot;text-blue-600&quot;)
ui.button(icon=&quot;delete&quot;,
on_click=make_del()).props(&quot;flat round dense color=red size=sm&quot;).classes(&quot;text-red-600&quot;)
refresh_edit_conn_list()
e_connection =
ui.input(value=get_q(report,&#39;connection&#39;,&#39;&#39;)).props(&quot;outlined dense color=orange&quot;).classes(&quot;w-full font-bold bg-
orange-50 hidden&quot;)
ui.label(&quot;Report Title&quot;).classes(&quot;text-[11px] font-
bold text-slate-700&quot;)
e_title =
ui.input(value=report.report_title).props(&quot;outlined dense&quot;).classes(&quot;w-full&quot;)
ui.label(&quot;PVC &amp; DI Quantity&quot;).classes(&quot;text-[13px]
font-extrabold text-green-700 mt-2&quot;)
with ui.grid(columns=4).classes(&quot;w-full gap-2&quot;):
with ui.column().classes(&quot;gap-1&quot;):
ui.label(&quot;63MM PVC&quot;).classes(&quot;text-[12px]
font-bold text-center&quot;)
e_63 =
ui.input(value=str(get_q(report,&#39;qty_63mm&#39;))).props(&quot;type=number outlined dense&quot;).classes(&quot;w-full font-bold text-
[14px]&quot;)
with ui.column().classes(&quot;gap-1&quot;):
ui.label(&quot;90MM PVC&quot;).classes(&quot;text-[12px]
font-bold text-center&quot;)
e_90 =
ui.input(value=str(get_q(report,&#39;qty_90mm&#39;))).props(&quot;type=number outlined dense&quot;).classes(&quot;w-full font-bold text-
[14px]&quot;)
with ui.column().classes(&quot;gap-1&quot;):
ui.label(&quot;110MM PVC&quot;).classes(&quot;text-[12px]
font-bold text-center&quot;)
e_110 =
ui.input(value=str(get_q(report,&#39;qty_110mm&#39;))).props(&quot;type=number outlined dense&quot;).classes(&quot;w-full font-bold
text-[14px]&quot;)
with ui.column().classes(&quot;gap-1&quot;):
ui.label(&quot;150MM DI&quot;).classes(&quot;text-[12px]
font-bold text-center&quot;)
e_150 =
ui.input(value=str(get_q(report,&#39;qty_150mm&#39;))).props(&quot;type=number outlined dense&quot;).classes(&quot;w-full font-bold
text-[14px]&quot;)
ui.label(&quot;Extra MTR (Additional
Meters)&quot;).classes(&quot;text-[13px] font-extrabold text-orange-700 mt-3 bg-orange-50 px-2 py-1 rounded-full&quot;)
with ui.grid(columns=4).classes(&quot;w-full gap-2 mt-1&quot;):
with ui.column().classes(&quot;gap-1&quot;):
ui.label(&quot;63MM Extra&quot;).classes(&quot;text-[11px]
font-bold text-center text-orange-600&quot;)
e_extra_63 =
ui.input(value=str(get_q(report,&#39;extra_63mm&#39;,0))).props(&quot;type=number outlined dense color=orange&quot;).classes(&quot;w-

full font-bold text-[14px] bg-orange-50&quot;)
with ui.column().classes(&quot;gap-1&quot;):
ui.label(&quot;90MM Extra&quot;).classes(&quot;text-[11px]
font-bold text-center text-orange-600&quot;)
e_extra_90 =
ui.input(value=str(get_q(report,&#39;extra_90mm&#39;,0))).props(&quot;type=number outlined dense color=orange&quot;).classes(&quot;w-
full font-bold text-[14px] bg-orange-50&quot;)
with ui.column().classes(&quot;gap-1&quot;):
ui.label(&quot;110MM Extra&quot;).classes(&quot;text-[11px]
font-bold text-center text-orange-600&quot;)
e_extra_110 =
ui.input(value=str(get_q(report,&#39;extra_110mm&#39;,0))).props(&quot;type=number outlined dense color=orange&quot;).classes(&quot;w-
full font-bold text-[14px] bg-orange-50&quot;)
with ui.column().classes(&quot;gap-1&quot;):
ui.label(&quot;150MM Extra&quot;).classes(&quot;text-[11px]
font-bold text-center text-orange-600&quot;)
e_extra_150 =
ui.input(value=str(get_q(report,&#39;extra_150mm&#39;,0))).props(&quot;type=number outlined dense color=orange&quot;).classes(&quot;w-
full font-bold text-[14px] bg-orange-50&quot;)
with ui.row().classes(&quot;w-full justify-between gap-2 p-2
bg-white border-t shrink-0&quot;):
ui.button(&quot;Cancel&quot;, icon=&quot;close&quot;,
on_click=edit_dialog.close).props(&quot;flat rounded dense&quot;).classes(&quot;flex-1 bg-slate-100 text-[12px]&quot;)
save_edit_btn = ui.button(&quot;OK&quot;,
icon=&quot;check&quot;).props(&quot;rounded dense&quot;).classes(&quot;flex-1 bg-blue-600 text-white font-bold text-[12px]&quot;)
def make_save_edit(rpt=report, ed=e_date, ea=e_area,
et=e_title, e63=e_63, e90=e_90, e110=e_110, e150=e_150, el=e_labour, ec=e_connection, dlg=edit_dialog,
ex63=e_extra_63, ex90=e_extra_90, ex110=e_extra_110, ex150=e_extra_150):
def do_save():
try:
try:
new_date =
datetime.datetime.strptime((ed.value or &quot;&quot;).strip(), &quot;%Y-%m-%d&quot;).date()
except:
new_date = rpt.report_date
new_area = (ea.value or &quot;&quot;).strip() or
rpt.area_name
new_labour = (el.value or &quot;&quot;).strip() or
get_q(rpt,&#39;labour_name&#39;,&#39;&#39;)
# Calculate sum from edit_conn_state
items
new_conn_sum = 0
try:
for it in
edit_conn_state.get(&quot;items&quot;, []):
try:
new_conn_sum +=
float(str(it.get(&#39;conn&#39;,&#39;0&#39;) or 0).strip() or 0)
except:
pass
except:
new_conn_sum = 0
# If no items, fallback to old ec field
if new_conn_sum == 0:
try:
new_conn_sum = float((ec.value or
&quot;&quot;).strip() or 0)
except:
new_conn_sum = 0
if new_conn_sum == int(new_conn_sum):
new_conn = str(int(new_conn_sum)) if
new_conn_sum!=0 else &quot;&quot;
else:
new_conn = str(new_conn_sum) if

new_conn_sum!=0 else &quot;&quot;
new_title = (et.value or &quot;&quot;).strip() or
rpt.report_title
def pq(v):
try: return float(v) if v not in
(None, &quot;&quot;) else 0
except: return 0
q63 = pq(e63.value); q90 = pq(e90.value);
q110 = pq(e110.value); q150 = pq(e150.value)
ex_63 = pq(ex63.value); ex_90 =
pq(ex90.value); ex_110 = pq(ex110.value); ex_150 = pq(ex150.value)
total_mtr =
(q63*6+ex_63)+(q90*6+ex_90)+(q110*6+ex_110)+(q150*5.5+ex_150)
rpt.report_date = new_date
rpt.area_name = new_area
try:
rpt.labour_name = new_labour
except:
pass
try:
rpt.connection = new_conn
except:
pass
rpt.report_title = new_title
rpt.qty_63mm = q63; rpt.qty_90mm = q90;
rpt.qty_110mm = q110
try: rpt.qty_150mm = q150
except: pass
try:
rpt.extra_63mm = ex_63;
rpt.extra_90mm = ex_90; rpt.extra_110mm = ex_110; rpt.extra_150mm = ex_150
rpt.total_mtr = total_mtr
rpt.total_pvc = q63+q90+q110;
rpt.total_di = q150
except: pass
rpt.total_qty = q63+q90+q110+q150
rpt.price_sum = float(total_mtr)
rpt.save()
# Save ConnectionEntry: delete old and
recreate from edit_conn_state
try:
from models_app.models import
ConnectionEntry
# Delete all old entries for this
report and also by date for safety
ConnectionEntry.objects.filter(report=rpt).delete()
try:
ConnectionEntry.objects.filter(user=rpt.user, report_date=rpt.report_date,
area_name=rpt.area_name).exclude(report=rpt).delete()
except:
pass
for it in
edit_conn_state.get(&quot;items&quot;, []):
ConnectionEntry.objects.create(
user=rpt.user, report=rpt,
report_date=new_date,
connection_no=str(it.get(&#39;conn&#39;,&#39;&#39;)).strip(),
name=str(it.get(&#39;name&#39;,&#39;&#39;)).strip(),
mobile=str(it.get(&#39;mobile&#39;,&#39;&#39;)).strip(),
area_name=new_area
)
except Exception as ce:
print(f&quot;Edit conn save fail: {ce}&quot;)
import traceback;

traceback.print_exc()
ui.notify(f&quot;✅ Updated! MTR:{total_mtr}
Conn Sum:{new_conn_sum}&quot;, type=&quot;positive&quot;, position=&quot;top&quot;, timeout=2000)
dlg.close()
# Instant refresh without Loading screen
- only update detail view
try:
# Rebuild detail view directly with
updated report, no loading spinner
build_filter_detail(rpt)
except Exception as e:
print(f&quot;Refresh detail fail: {e}&quot;)
# Fallback: just close, don&#39;t show
loading
pass
load_table_data()
except Exception as ex:
import traceback; traceback.print_exc()
ui.notify(f&quot;Edit failed: {ex}&quot;,
type=&quot;negative&quot;)
return do_save
save_edit_btn.on_click(make_save_edit())
edit_btn.on_click(edit_dialog.open)
with ui.dialog() as del_dialog, ui.card().classes(&quot;rounded-3xl p-
0 w-full max-w-sm overflow-hidden shadow-2xl&quot;):
with ui.column().classes(&quot;w-full p-0 gap-0&quot;):
with ui.row().classes(&quot;w-full bg-gradient-to-r from-red-
500 to-red-600 p-4 items-center gap-3 text-white&quot;):
ui.icon(&quot;warning&quot;, size=&quot;1.5rem&quot;);
ui.label(&quot;Delete?&quot;).classes(&quot;font-extrabold text-sm text-white&quot;)
with ui.column().classes(&quot;w-full p-5 gap-3 bg-white&quot;):
ui.label(&quot;This report will be permanently
deleted!&quot;).classes(&quot;text-sm font-bold&quot;)
ui.label(f&quot;Area: {report.area_name} | Labour:
{get_q(report,&#39;labour_name&#39;,&#39;&#39;) or &#39;No Labour&#39;} | Date: {report.report_date.strftime(&#39;%d-%m-%Y&#39;)} | Total:
{report.total_qty} Qty&quot;).classes(&quot;text-xs text-slate-600&quot;)
with ui.row().classes(&quot;w-full justify-between gap-3
mt-2&quot;):
ui.button(&quot;Cancel&quot;, icon=&quot;close&quot;,
on_click=del_dialog.close).props(&quot;flat rounded&quot;).classes(&quot;flex-1 bg-slate-100&quot;)
confirm_del_btn = ui.button(&quot;Delete&quot;,
icon=&quot;delete_forever&quot;).props(&quot;rounded&quot;).classes(&quot;flex-1 bg-red-600 text-white font-bold&quot;)
def make_del(rpt=report, dlg=del_dialog):
def do_del():
try:
rpt.delete()
ui.notify(&quot;��️ Data Deleted!&quot;
type=&quot;positive&quot;, position=&quot;top&quot;, timeout=2000)
dlg.close()
load_table_data()
except Exception as ex:
ui.notify(f&quot;Failed: {ex}&quot;,
type=&quot;negative&quot;)
return do_del
confirm_del_btn.on_click(make_del())
del_btn.on_click(del_dialog.open)
else:
agg = base_qs.aggregate(s63=Sum(&#39;qty_63mm&#39;), s90=Sum(&#39;qty_90mm&#39;),
s110=Sum(&#39;qty_110mm&#39;), s150=Sum(&#39;qty_150mm&#39;), ex63=Sum(&#39;extra_63mm&#39;), ex90=Sum(&#39;extra_90mm&#39;),
ex110=Sum(&#39;extra_110mm&#39;), ex150=Sum(&#39;extra_150mm&#39;), tmtr=Sum(&#39;total_mtr&#39;)); t63 = agg[&#39;s63&#39;] or 0; t90 =
agg[&#39;s90&#39;] or 0; t110 = agg[&#39;s110&#39;] or 0; t150 = agg[&#39;s150&#39;] or 0; te63 = agg[&#39;ex63&#39;] or 0; te90 = agg[&#39;ex90&#39;] or
0; te110 = agg[&#39;ex110&#39;] or 0; te150 = agg[&#39;ex150&#39;] or 0; tmtr = agg[&#39;tmtr&#39;] or 0; period_text = f&quot;Full Month:
{months[sel_month]} {sel_year}&quot;
total_connections = 0

try:
from models_app.models import ConnectionEntry
# Sum of connection_no values, not count
entries = ConnectionEntry.objects.filter(user=user,
report_date__year=sel_year, report_date__month=sel_month)
for ce in entries:
try:
total_connections += float(str(ce.connection_no or 0).strip() or 0)
except:
pass
if total_connections == 0:
for r in base_qs:
cv = getattr(r, &#39;connection&#39;, &#39;&#39;) or &#39;&#39;
try:
if cv:
total_connections += float(str(cv).strip() or 0)
except:
pass
except Exception as e:
print(f&quot;Monthly conn sum fail: {e}&quot;)
try:
for r in base_qs:
cv = getattr(r, &#39;connection&#39;, &#39;&#39;) or &#39;&#39;
try:
if cv:
total_connections += float(str(cv).strip() or 0)
except:
pass
except:
pass
with table_container:
with ui.row().classes(&quot;w-full justify-between items-center mb-2 px-1&quot;):
ui.badge(period_text, color=&quot;green&quot;).classes(&quot;text-xs font-bold px-2 py-
1&quot;); ui.badge(f&quot;Total: {t63+t90+t110+t150} Qty&quot;, color=&quot;green&quot;).classes(&quot;text-xs font-bold px-2 py-1&quot;)
tm63 = t63*6 + te63; tm90 = t90*6 + te90; tm110 = t110*6 + te110; tm150 =
t150*5.5 + te150
rows = [{&quot;sr_no&quot;: 1, &quot;pipe_dia&quot;: &quot;63MM PVC&quot;, &quot;quantity&quot;: t63, &quot;extra&quot;: te63,
&quot;unit&quot;: &quot;6MTR per PIPES&quot;, &quot;total_mtr&quot;: tm63}, {&quot;sr_no&quot;: 2, &quot;pipe_dia&quot;: &quot;90MM PVC&quot;, &quot;quantity&quot;: t90, &quot;extra&quot;:
te90, &quot;unit&quot;: &quot;6MTR per PIPES&quot;, &quot;total_mtr&quot;: tm90}, {&quot;sr_no&quot;: 3, &quot;pipe_dia&quot;: &quot;110MM PVC&quot;, &quot;quantity&quot;: t110,
&quot;extra&quot;: te110, &quot;unit&quot;: &quot;6MTR per PIPES&quot;, &quot;total_mtr&quot;: tm110}, {&quot;sr_no&quot;: 4, &quot;pipe_dia&quot;: &quot;150MM DI&quot;, &quot;quantity&quot;:
t150, &quot;extra&quot;: te150, &quot;unit&quot;: &quot;5.5MTR&quot;, &quot;total_mtr&quot;: tm150}]
columns = [{&quot;name&quot;: &quot;sr_no&quot;, &quot;label&quot;: &quot;Sr.No&quot;, &quot;field&quot;: &quot;sr_no&quot;, &quot;align&quot;:
&quot;center&quot;}, {&quot;name&quot;: &quot;pipe_dia&quot;, &quot;label&quot;: &quot;Pipe Dia&quot;, &quot;field&quot;: &quot;pipe_dia&quot;, &quot;align&quot;: &quot;center&quot;}, {&quot;name&quot;:
&quot;quantity&quot;, &quot;label&quot;: &quot;Qty&quot;, &quot;field&quot;: &quot;quantity&quot;, &quot;align&quot;: &quot;center&quot;}, {&quot;name&quot;: &quot;extra&quot;, &quot;label&quot;: &quot;Extra&quot;, &quot;field&quot;:
&quot;extra&quot;, &quot;align&quot;: &quot;center&quot;}, {&quot;name&quot;: &quot;unit&quot;, &quot;label&quot;: &quot;UNIT&quot;, &quot;field&quot;: &quot;unit&quot;, &quot;align&quot;: &quot;center&quot;}, {&quot;name&quot;:
&quot;total_mtr&quot;, &quot;label&quot;: &quot;Total MTR&quot;, &quot;field&quot;: &quot;total_mtr&quot;, &quot;align&quot;: &quot;center&quot;}]
ui.table(columns=columns, rows=rows).props(&quot;dense flat bordered&quot;).classes(&quot;w-
full rounded-xl shadow-sm border border-green-200 text-xs font-semibold&quot;)
with ui.row().classes(&quot;w-full justify-center gap-2 mt-2 flex-wrap&quot;):
ui.badge(f&quot;PVC: {t63+t90+t110} Qty | Extra:{te63+te90+te110} MTR | Total
MTR:{tm63+tm90+tm110}&quot;, color=&quot;blue&quot;).classes(&quot;text-[10px] font-bold px-2 py-1&quot;)
ui.badge(f&quot;DI: {t150} Qty | Extra:{te150} MTR | Total MTR:{tm150}&quot;,
color=&quot;purple&quot;).classes(&quot;text-[10px] font-bold px-2 py-1&quot;)
ui.badge(f&quot;Grand Extra: {te63+te90+te110+te150} MTR | Grand Total MTR:
{tm63+tm90+tm110+tm150}&quot;, color=&quot;green&quot;).classes(&quot;text-[10px] font-bold px-2 py-1&quot;)
ui.badge(f&quot;Total Connections: {total_connections}&quot;,
color=&quot;orange&quot;).classes(&quot;text-[10px] font-bold px-2 py-1&quot;)
with ui.dialog() as month_download_dialog, ui.card().classes(&quot;rounded-3xl p-0
w-full max-w-xs overflow-hidden shadow-2xl relative&quot;):
with ui.row().classes(&quot;w-full justify-between items-center p-3 bg-
gradient-to-r from-green-600 to-emerald-600 text-white&quot;):
ui.label(f&quot;�� Download {period_text}&quot;).classes(&quot;font-extrabold text-
xs text-white&quot;)
ui.button(icon=&quot;close&quot;,

on_click=month_download_dialog.close).props(&quot;flat round dense color=white&quot;).classes(&quot;text-white&quot;)
with ui.column().classes(&quot;w-full p-4 gap-2 bg-white&quot;):
ui.label(f&quot;{period_text} - {t63+t90+t110+t150} Qty&quot;).classes(&quot;text-xs
font-bold text-green-700 text-center w-full mb-1&quot;)
def do_m_csv():
data = generate_month_csv(user.default_report_title, period_text,
t63, t90, t110, t150, te63, te90, te110, te150, total_connections)
ui.download(data, f&quot;{period_text.replace(&#39; &#39;, &#39;_&#39;)}_report.csv&quot;)
month_download_dialog.close()
def do_m_excel():
data = generate_month_excel(user.default_report_title,
period_text, t63, t90, t110, t150, te63, te90, te110, te150, total_connections)
ui.download(data, f&quot;{period_text.replace(&#39; &#39;, &#39;_&#39;)}_report.xlsx&quot;)
month_download_dialog.close()
def do_m_pdf():
data = generate_month_pdf(user.default_report_title, period_text,
t63, t90, t110, t150, te63, te90, te110, te150, total_connections)
ui.download(data, f&quot;{period_text.replace(&#39; &#39;, &#39;_&#39;)}_report.pdf&quot;)
month_download_dialog.close()
ui.button(&quot;As CSV&quot;, icon=&quot;table_view&quot;,
on_click=do_m_csv).props(&quot;outline rounded&quot;).classes(&quot;w-full font-bold text-sm border-blue-500 text-blue-600&quot;)
ui.button(&quot;As Excel&quot;, icon=&quot;description&quot;,
on_click=do_m_excel).props(&quot;outline rounded&quot;).classes(&quot;w-full font-bold text-sm border-green-500 text-green-600&quot;)
ui.button(&quot;As PDF&quot;, icon=&quot;picture_as_pdf&quot;,
on_click=do_m_pdf).props(&quot;outline rounded&quot;).classes(&quot;w-full font-bold text-sm border-red-500 text-red-600&quot;)
ui.button(&quot;�� Download&quot;, icon=&quot;download&quot;
on_click=month_download_dialog.open).props(&quot;rounded no-caps&quot;).classes(&quot;w-full mt-3 bg-gradient-to-r from-blue-500
to-blue-600 text-white font-bold py-2.5 shadow-md&quot;)
def safe_load(*_):
try:
load_table_data()
except Exception as e:
print(f&quot;Filter load error: {e}&quot;)
try:
with table_container:
ui.label(f&quot;Load error: {e}&quot;).classes(&quot;text-xs text-red-500&quot;)
except:
pass
day_select.on_value_change(safe_load)
month_select.on_value_change(safe_load)
year_select.on_value_change(safe_load)
ui.timer(0.15, safe_load, once=True)
def build_filter_detail(report):
filter_detail_view.clear()
with filter_detail_view:
with ui.column().classes(&quot;w-full max-w-md items-center gap-2&quot;):
with ui.card().classes(&quot;w-full rounded-3xl shadow-2xl bg-white p-3 sm:p-5 border-2 border-
green-200&quot;):
with ui.row().classes(&quot;w-full justify-between items-center mb-3&quot;):
ui.button(&quot;Back&quot;, icon=&quot;arrow_back&quot;, on_click=show_filter).props(&quot;flat rounded no-
caps dense&quot;).classes(&quot;back-btn text-xs&quot;)
ui.badge(f&quot;{report.report_date.strftime(&#39;%d-%m-%Y&#39;)}&quot;, color=&quot;green&quot;).classes(&quot;font-
bold text-xs&quot;)
with ui.column().classes(&quot;w-full rounded-2xl bg-gradient-to-r from-green-200 via-emerald-
200 to-teal-200 p-3 border-2 border-green-300 shadow-md mb-3&quot;):
with ui.column().classes(&quot;w-full gap-1&quot;):
with ui.row().classes(&quot;w-full items-center gap-2&quot;):
ui.icon(&quot;location_on&quot;, color=&quot;green&quot;); ui.label(f&quot;Area: {report.area_name or
&#39;No Area&#39;}&quot;).classes(&quot;font-extrabold text-base text-green-900&quot;)
with ui.row().classes(&quot;w-full items-center gap-2&quot;):
ui.icon(&quot;engineering&quot;, color=&quot;blue&quot;); ui.label(f&quot;Labour:
{get_q(report,&#39;labour_name&#39;,&#39;&#39;) or &#39;No Labour&#39;}&quot;).classes(&quot;font-bold text-sm text-blue-900&quot;)
conn_det = get_q(report, &#39;connection&#39;, &#39;&#39;)

conn_entries = []
try:
from models_app.models import ConnectionEntry
conn_entries =
list(ConnectionEntry.objects.filter(report=report).order_by(&#39;id&#39;))
if not conn_entries:
# Try by date and user if report link not set (old data)
conn_entries = list(ConnectionEntry.objects.filter(user=report.user,
report_date=report.report_date, area_name=report.area_name).order_by(&#39;id&#39;))
except Exception as e:
print(f&quot;Conn fetch fail: {e}&quot;)
conn_entries = []
if conn_det or conn_entries:
with ui.column().classes(&quot;w-full gap-1 bg-orange-50 p-2 rounded-xl border
border-orange-200&quot;):
with ui.row().classes(&quot;w-full items-center gap-2&quot;):
ui.icon(&quot;power&quot;, color=&quot;orange&quot;)
total_c = len(conn_entries) if conn_entries else conn_det
ui.label(f&quot;Total Connections: {total_c}&quot;).classes(&quot;font-extrabold
text-sm text-orange-800&quot;)
# Show individual entries like 56,Mohanlal,9988779988
if conn_entries:
for ce in conn_entries:
ui.label(f&quot;{ce.connection_no},{ce.name},{ce.mobile}&quot;).classes(&quot;text-[11px] font-bold text-slate-700 bg-white px-2
py-1 rounded-full border border-orange-100 w-full&quot;)
else:
ui.label(f&quot;Connection: {conn_det}&quot;).classes(&quot;font-bold text-sm text-
orange-800&quot;)
with ui.column().classes(&quot;w-full rounded-2xl overflow-hidden shadow-lg border-2 border-
indigo-900 gap-0 mb-4&quot;):
# Header
with ui.grid(columns=4).classes(&quot;w-full bg-gradient-to-r from-emerald-500 via-green-
500 to-teal-500 text-white font-extrabold text-center&quot;):
ui.label(&quot;63MM PVC&quot;).classes(&quot;py-2 text-[10px]&quot;); ui.label(&quot;90MM
PVC&quot;).classes(&quot;py-2 text-[10px] border-x border-white/30&quot;); ui.label(&quot;110MM PVC&quot;).classes(&quot;py-2 text-[10px]
border-r border-white/30&quot;); ui.label(&quot;150MM DI&quot;).classes(&quot;py-2 text-[10px]&quot;)
# Quantity Row
with ui.grid(columns=4).classes(&quot;w-full bg-white text-center items-center&quot;):
ui.label(f&quot;{get_q(report,&#39;qty_63mm&#39;)}&quot;).classes(&quot;py-2 font-extrabold text-xs&quot;);
ui.label(f&quot;{get_q(report,&#39;qty_90mm&#39;)}&quot;).classes(&quot;py-2 font-extrabold text-xs border-x border-gray-200&quot;);
ui.label(f&quot;{get_q(report,&#39;qty_110mm&#39;)}&quot;).classes(&quot;py-2 font-extrabold text-xs border-r border-gray-200&quot;);
ui.label(f&quot;{get_q(report,&#39;qty_150mm&#39;)}&quot;).classes(&quot;py-2 font-extrabold text-xs bg-green-50 text-green-700&quot;)
# Pipe MTR + Extra MTR Row - NEW
with ui.grid(columns=4).classes(&quot;w-full bg-green-50 text-center border-y border-
indigo-900 items-center&quot;):
ex63 = get_q(report,&#39;extra_63mm&#39;,0); ex90 = get_q(report,&#39;extra_90mm&#39;,0); ex110 =
get_q(report,&#39;extra_110mm&#39;,0); ex150 = get_q(report,&#39;extra_150mm&#39;,0)
m63 = get_q(report,&#39;qty_63mm&#39;)*6 + ex63; m90 = get_q(report,&#39;qty_90mm&#39;)*6 + ex90;
m110 = get_q(report,&#39;qty_110mm&#39;)*6 + ex110; m150 = get_q(report,&#39;qty_150mm&#39;)*5.5 + ex150
def fmt(m, ex):
if ex&gt;0:
return f&quot;{m} MTR (+{ex})&quot;
return f&quot;{m} MTR&quot;
ui.label(fmt(m63, ex63)).classes(&quot;py-1.5 font-bold text-[10px]&quot;);
ui.label(fmt(m90, ex90)).classes(&quot;py-1.5 font-bold text-[10px] border-x border-gray-200&quot;); ui.label(fmt(m110,
ex110)).classes(&quot;py-1.5 font-bold text-[10px] border-r border-gray-200&quot;); ui.label(fmt(m150, ex150)).classes(&quot;py-
1.5 font-bold text-[10px] bg-green-50&quot;)
# Extra MTR Row Highlight
with ui.grid(columns=4).classes(&quot;w-full bg-orange-50 text-center border-b border-
indigo-900 items-center&quot;):
ex63 = get_q(report,&#39;extra_63mm&#39;,0); ex90 = get_q(report,&#39;extra_90mm&#39;,0); ex110 =
get_q(report,&#39;extra_110mm&#39;,0); ex150 = get_q(report,&#39;extra_150mm&#39;,0)
has_extra = ex63+ex90+ex110+ex150 &gt; 0
if has_extra:

ui.label(f&quot;+{ex63} Extra&quot; if ex63&gt;0 else &quot;-&quot;).classes(&quot;py-1 font-bold text-
[9px] text-orange-600&quot;)
ui.label(f&quot;+{ex90} Extra&quot; if ex90&gt;0 else &quot;-&quot;).classes(&quot;py-1 font-bold text-
[9px] text-orange-600 border-x border-gray-200&quot;)
ui.label(f&quot;+{ex110} Extra&quot; if ex110&gt;0 else &quot;-&quot;).classes(&quot;py-1 font-bold text-
[9px] text-orange-600 border-r border-gray-200&quot;)
ui.label(f&quot;+{ex150} Extra&quot; if ex150&gt;0 else &quot;-&quot;).classes(&quot;py-1 font-bold text-
[9px] text-orange-600&quot;)
else:
ui.label(&quot;No Extra&quot;).classes(&quot;py-1 font-bold text-[9px] text-slate-400 col-
span-4&quot;)
with ui.grid(columns=2).classes(&quot;w-full bg-gradient-to-r from-slate-900 via-indigo-
950 to-slate-900 text-white text-center items-center&quot;):
pvc = get_q(report,&#39;qty_63mm&#39;)+get_q(report,&#39;qty_90mm&#39;)+get_q(report,&#39;qty_110mm&#39;)
di = get_q(report,&#39;qty_150mm&#39;)
ex_total =
get_q(report,&#39;extra_63mm&#39;,0)+get_q(report,&#39;extra_90mm&#39;,0)+get_q(report,&#39;extra_110mm&#39;,0)+get_q(report,&#39;extra_150mm
&#39;,0)
total_mtr_val = get_q(report,&#39;total_mtr&#39;,0)
if total_mtr_val==0:
total_mtr_val =
(get_q(report,&#39;qty_63mm&#39;)*6+get_q(report,&#39;qty_90mm&#39;)*6+get_q(report,&#39;qty_110mm&#39;)*6+get_q(report,&#39;qty_150mm&#39;)*5.5)
+ex_total
ui.label(f&quot;PVC: {pvc} Qty | DI: {di} Qty&quot;).classes(&quot;py-2 font-bold text-green-300
text-[10px] border-r border-white/10&quot;)
ui.label(f&quot;Total MTR: {total_mtr_val}&quot;).classes(&quot;py-2 font-bold text-yellow-200
text-[10px]&quot;)
# Grand Total MTR Banner
with ui.grid(columns=1).classes(&quot;w-full bg-gradient-to-r from-amber-900 to-yellow-900
text-center&quot;):
ex_total =
get_q(report,&#39;extra_63mm&#39;,0)+get_q(report,&#39;extra_90mm&#39;,0)+get_q(report,&#39;extra_110mm&#39;,0)+get_q(report,&#39;extra_150mm
&#39;,0)
if ex_total&gt;0:
ui.label(f&quot;Extra MTR Added: {ex_total} MTR&quot;).classes(&quot;py-1.5 font-extrabold
text-orange-200 text-[11px]&quot;)
# Grand Total REMOVED - Only PVC and DI separate as per user request
# with ui.grid(columns=1).classes(&quot;w-full bg-gradient-to-r from-emerald-900 to-teal-
900 text-center&quot;):
# gt = pvc + di
# ui.label(f&quot;Grand Total: {gt} Quantity&quot;).classes(&quot;py-2.5 font-extrabold text-
white text-sm&quot;)
with ui.column().classes(&quot;w-full bg-gray-50 rounded-xl p-3 border border-gray-200 mb-3&quot;):
ui.label(f&quot;�� Date: {report.report_date.strftime(&#39;%d-%m-%Y&#39;)}&quot;).classes(&quot;text-x
font-bold text-slate-700&quot;)
ui.label(f&quot;�� Area: {report.area_name}&quot;).classes(&quot;text-xs font-bold text-slate-700&quot;)
ui.label(f&quot;�� Labour: {get_q(report,&#39;labour_name&#39;,&#39;&#39;) or &#39;N
Labour&#39;}&quot;).classes(&quot;text-xs font-bold text-slate-700&quot;)
ui.label(f&quot;�� Connection: {get_q(report,&#39;connection&#39;,&#39;&#39;) or &#39;N
Connection&#39;}&quot;).classes(&quot;text-xs font-bold text-orange-700&quot;)
ui.label(f&quot;�� Title: {report.report_title}&quot;).classes(&quot;text-xs font-bold text-slate-
700&quot;)
with ui.dialog() as detail_download_dialog, ui.card().classes(&quot;rounded-3xl p-0 w-full
max-w-xs overflow-hidden shadow-2xl relative&quot;):
with ui.row().classes(&quot;w-full justify-between items-center p-3 bg-gradient-to-r from-
green-600 to-emerald-600 text-white&quot;):
ui.label(f&quot;�� Download {report.area_name}&quot;).classes(&quot;font-extrabold text-xs text-
white&quot;)
ui.button(icon=&quot;close&quot;, on_click=detail_download_dialog.close).props(&quot;flat round
dense color=white&quot;).classes(&quot;text-white bg-white/20&quot;)
with ui.column().classes(&quot;w-full p-4 gap-2 bg-white&quot;):
def do_csv():
ui.download(generate_single_csv(report),
f&quot;{report.area_name}_{report.report_date}_report.csv&quot;)

detail_download_dialog.close()
def do_excel():
ui.download(generate_single_excel(report),
f&quot;{report.area_name}_{report.report_date}_report.xlsx&quot;)
detail_download_dialog.close()
def do_pdf():
ui.download(generate_single_pdf(report),
f&quot;{report.area_name}_{report.report_date}_report.pdf&quot;)
detail_download_dialog.close()
ui.button(&quot;As CSV&quot;, icon=&quot;table_view&quot;, on_click=do_csv).props(&quot;outline rounded
no-caps&quot;).classes(&quot;w-full font-bold text-sm border-blue-500 text-blue-600 py-2&quot;)
ui.button(&quot;As Excel&quot;, icon=&quot;description&quot;, on_click=do_excel).props(&quot;outline
rounded no-caps&quot;).classes(&quot;w-full font-bold text-sm border-green-500 text-green-600 py-2&quot;)
ui.button(&quot;As PDF&quot;, icon=&quot;picture_as_pdf&quot;, on_click=do_pdf).props(&quot;outline
rounded no-caps&quot;).classes(&quot;w-full font-bold text-sm border-red-500 text-red-600 py-2&quot;)
ui.button(&quot;�� Download&quot;, icon=&quot;download&quot;
on_click=detail_download_dialog.open).props(&quot;rounded no-caps&quot;).classes(&quot;w-full py-3 bg-gradient-to-r from-green-
500 to-emerald-600 text-white font-extrabold text-base shadow-xl&quot;)
def build_profile():
profile_view.clear()
user = state[&quot;user&quot;]
if not user:
show_login()
return
with profile_view:
with ui.column().classes(&quot;w-full max-w-sm items-center gap-3&quot;):
with ui.card().classes(&quot;profile-card w-full p-0 overflow-hidden&quot;):
with ui.row().classes(&quot;w-full justify-start p-4 pb-2&quot;):
ui.button(&quot;Back to Home&quot;, icon=&quot;arrow_back&quot;, on_click=show_home).props(&quot;flat rounded
dense no-caps&quot;).classes(&quot;back-btn text-xs&quot;)
with ui.column().classes(&quot;w-full items-center gap-1 px-6 pb-4&quot;):
with ui.element(&quot;div&quot;).classes(&quot;w-20 h-20 rounded-full bg-gradient-to-br from-green-
500 to-emerald-600 flex items-center justify-center shadow-lg&quot;):
ui.icon(&quot;person&quot;, size=&quot;3rem&quot;).classes(&quot;text-white&quot;)
ui.label(user.username or &quot;aj&quot;).classes(&quot;text-xl font-extrabold text-slate-900 mt-2
tracking-tight&quot;)
ui.label(user.email).classes(&quot;text-sm font-semibold text-emerald-600 text-center
break-all&quot;)
with ui.column().classes(&quot;w-full px-6 pb-6 gap-3&quot;):
delete_btn = ui.button(&quot;Delete Account&quot;, icon=&quot;delete_forever&quot;).props(&quot;outline
rounded no-caps&quot;).classes(&quot;delete-btn w-full py-2.5 shadow-sm&quot;)
logout_btn = ui.button(&quot;LOGOUT&quot;, icon=&quot;logout&quot;).props(&quot;outline rounded no-
caps&quot;).classes(&quot;w-full py-2 font-bold text-sm border-blue-300 text-blue-600 hover:bg-blue-50&quot;)
with ui.dialog() as delete_dialog, ui.card().classes(&quot;rounded-3xl p-0 w-full max-w-sm
overflow-hidden shadow-2xl&quot;):
with ui.column().classes(&quot;w-full p-0 gap-0&quot;):
with ui.row().classes(&quot;w-full bg-gradient-to-r from-red-500 to-red-600 p-4
items-center gap-3 text-white&quot;):
ui.icon(&quot;warning&quot;, size=&quot;1.8rem&quot;).classes(&quot;text-white&quot;)
ui.label(&quot;Delete Account?&quot;).classes(&quot;font-extrabold text-base text-
white&quot;)
with ui.column().classes(&quot;w-full p-5 gap-3 bg-white&quot;):
ui.label(&quot;All your data will be permanently deleted!&quot;).classes(&quot;text-sm
font-bold text-slate-800&quot;)
with ui.row().classes(&quot;w-full justify-between gap-3 mt-2&quot;):
cancel_btn = ui.button(&quot;Cancel&quot;, icon=&quot;close&quot;).props(&quot;flat rounded
no-caps&quot;).classes(&quot;flex-1 font-bold text-slate-600 bg-slate-100&quot;)
ok_btn = ui.button(&quot;OK, Delete&quot;, icon=&quot;check&quot;).props(&quot;rounded no-
caps&quot;).classes(&quot;flex-1 bg-red-600 text-white font-bold shadow-md&quot;)
def do_cancel():
delete_dialog.close()
def do_delete():
try:

email = user.email
user_id = user.id
DailyReport.objects.filter(user_id=user_id).delete()
SavedArea.objects.filter(user_id=user_id).delete()
if HAS_TOKEN_MODEL:
PasswordResetToken.objects.filter(user_id=user_id).delete()
AppUser.objects.filter(id=user_id).delete()
CACHE[&quot;users&quot;].pop(email, None)
CACHE[&quot;areas&quot;].pop(user_id, None)
app.storage.user.clear()
ui.notify(f&quot;Account {email} deleted!&quot;, type=&quot;positive&quot;,
position=&quot;top&quot;)
delete_dialog.close()
show_login()
except Exception as e:
ui.notify(f&quot;Delete failed: {e}&quot;, type=&quot;negative&quot;, position=&quot;top&quot;)
cancel_btn.on_click(do_cancel)
ok_btn.on_click(do_delete)
delete_btn.on_click(delete_dialog.open)
def do_logout():
state[&quot;user&quot;] = None
saved_e = app.storage.user.get(&quot;saved_email&quot;, &quot;&quot;)
saved_p = app.storage.user.get(&quot;saved_password&quot;, &quot;&quot;)
app.storage.user.clear()
app.storage.user[&quot;saved_email&quot;] = saved_e
app.storage.user[&quot;saved_password&quot;] = saved_p
show_login()
logout_btn.on_click(do_logout)
with register_view:
with ui.card().classes(&quot;w-full max-w-sm rounded-3xl shadow-2xl overflow-hidden p-0&quot;):
with ui.column().classes(&quot;w-full bg-gradient-to-r from-emerald-500 via-teal-600 to-cyan-600 p-5
items-center text-white&quot;):
ui.icon(&quot;person_add&quot;, size=&quot;2.5rem&quot;); ui.label(&quot;Create Account (6-digit)&quot;).classes(&quot;text-xl
font-extrabold&quot;)
with ui.column().classes(&quot;w-full p-5 bg-white gap-3&quot;):
uname = ui.input(&quot;User name&quot;).props(&quot;outlined rounded dense&quot;).classes(&quot;w-full&quot;)
email = ui.input(&quot;Email id&quot;).props(&quot;outlined rounded dense&quot;).classes(&quot;w-full&quot;)
pwd = ui.input(&quot;Password (6 digits)&quot;, placeholder=&quot;Ex: 123456&quot;, password=True,
password_toggle_button=True).props(&quot;outlined rounded dense maxlength=6&quot;).classes(&quot;w-full&quot;)
re_pwd = ui.input(&quot;Retype password (6 digits)&quot;, placeholder=&quot;Ex: 123456&quot;, password=True,
password_toggle_button=True).props(&quot;outlined rounded dense maxlength=6&quot;).classes(&quot;w-full&quot;)
def handle_register():
u_val = (uname.value or &quot;&quot;).strip(); e_val = (email.value or &quot;&quot;).strip(); p_val =
(pwd.value or &quot;&quot;).strip(); rp_val = (re_pwd.value or &quot;&quot;).strip()
if not u_val or not e_val: ui.notify(&quot;Enter User name and Email!&quot;, type=&quot;warning&quot;,
position=&quot;top&quot;); return
if not is_valid_6digit(p_val):
ui.notify(&quot;Password must be exactly 6 digits! e.g., 123456&quot;, type=&quot;negative&quot;,
position=&quot;top&quot;); return
if p_val != rp_val: ui.notify(&quot;Passwords not same!&quot;, type=&quot;negative&quot;, position=&quot;top&quot;);
return
if AppUser.objects.filter(email=e_val).exists(): ui.notify(&quot;Already registered!&quot;,
type=&quot;negative&quot;, position=&quot;top&quot;); return
user = AppUser.objects.create(username=u_val, email=e_val, password=make_password(p_val),
default_report_title=&quot;Veraval site daily progress report&quot;)
CACHE[&quot;users&quot;][e_val] = user
pwd_key = hashlib.sha256(f&quot;{e_val}:{p_val}&quot;.encode()).hexdigest()
CACHE[&quot;pwd_verified&quot;][pwd_key] = user.id
app.storage.user[&quot;saved_email&quot;] = e_val
app.storage.user[&quot;saved_password&quot;] = p_val
ui.notify(&quot;Account created!&quot;, type=&quot;positive&quot;, position=&quot;top&quot;)
show_login()
ui.button(&quot;Register (6-digit)&quot;, icon=&quot;check_circle&quot;, on_click=handle_register).props(&quot;rounded

no-caps&quot;).classes(&quot;w-full py-2.5 mt-1 bg-gradient-to-r from-emerald-500 to-teal-600 text-white font-bold text-
base shadow-lg&quot;)
ui.button(&quot;Back&quot;, icon=&quot;arrow_back&quot;, on_click=show_login).props(&quot;flat no-
caps&quot;).classes(&quot;back-btn w-full font-semibold text-sm mt-1&quot;)
async def handle_login():
email = (email_input.value or &quot;&quot;).strip()
pwd = (pass_input.value or &quot;&quot;).strip()
if not email or not pwd:
ui.notify(&quot;Enter Email &amp; Password!&quot;, type=&quot;warning&quot;, position=&quot;top&quot;)
return
if not is_valid_6digit(pwd):
ui.notify(&quot;Password must be exactly 6 digits!&quot;, type=&quot;warning&quot;, position=&quot;top&quot;)
return
pwd_key = hashlib.sha256(f&quot;{email}:{pwd}&quot;.encode()).hexdigest()
if pwd_key in CACHE[&quot;pwd_verified&quot;]:
user_id = CACHE[&quot;pwd_verified&quot;][pwd_key]
cached_user = CACHE[&quot;users&quot;].get(email)
if cached_user and cached_user.id == user_id:
state[&quot;user&quot;] = cached_user
app.storage.user[&quot;logged_in_user_id&quot;] = cached_user.id
app.storage.user[&quot;saved_email&quot;] = email
app.storage.user[&quot;saved_password&quot;] = pwd
status_label.set_text(&quot;✅ Logged in (cached)&quot;)
show_home()
return
status_label.set_text(&quot;⏳ Verifying...&quot;)
login_btn.props(&quot;loading&quot;)
try:
def get_user_and_check():
try:
u = AppUser.objects.get(email=email)
except AppUser.DoesNotExist:
return None, False
is_ok = check_password(pwd, u.password)
return u, is_ok
quick_user, is_valid = await run.io_bound(get_user_and_check)
if not quick_user:
status_label.set_text(&quot;❌ User not found&quot;)
ui.notify(&quot;User not found! Register first.&quot;, type=&quot;negative&quot;, position=&quot;top&quot;)
return
if not is_valid:
status_label.set_text(&quot;❌ Invalid password&quot;)
ui.notify(&quot;❌ Invalid password!&quot;, type=&quot;negative&quot;, position=&quot;top&quot;)
return
CACHE[&quot;users&quot;][email] = quick_user
CACHE[&quot;pwd_verified&quot;][pwd_key] = quick_user.id
state[&quot;user&quot;] = quick_user
app.storage.user[&quot;logged_in_user_id&quot;] = quick_user.id
app.storage.user[&quot;saved_email&quot;] = email
app.storage.user[&quot;saved_password&quot;] = pwd
status_label.set_text(&quot;✅ Logged in&quot;)
show_home()
except Exception as e:
print(f&quot;❌ Login error: {e}\n{traceback.format_exc()}&quot;, flush=True)
status_label.set_text(f&quot;❌ Error: {str(e)[:80]}&quot;)
ui.notify(f&quot;Login failed: {e}&quot;, type=&quot;negative&quot;, position=&quot;top&quot;)
finally:
login_btn.props(remove=&quot;loading&quot;)
login_btn.on_click(handle_login)
reg_btn.on_click(show_register)
forgot_link.on(&quot;click&quot;, show_forgot)
show_login()

if __name__ in {&quot;__main__&quot;, &quot;__mp_main__&quot;}:
print(f&quot;�� FINAL SIMPLE 4-PIPE Starting on 0.0.0.0:{PORT}&quot;, flush=True)
ui.run(host=&quot;0.0.0.0&quot;, port=PORT, title=&quot;VERAVAL TRACKER&quot;, storage_secret=STORAGE_SECRET, reload=False,
show=False, dark=False)
