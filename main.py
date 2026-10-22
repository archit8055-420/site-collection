import os, datetime, csv, io, secrets, hashlib, traceback, requests, asyncio
print("🚀 FINAL VERAVAL TRACKER Loading...", flush=True)
os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"
from nicegui import ui, app, run
CACHE = {"users": {}, "areas": {}, "pwd_verified": {}}
from db_setup import init_django
init_django()
from zoneinfo import ZoneInfo
IST = ZoneInfo("Asia/Kolkata")
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
                cursor.execute("SELECT to_regclass('models_app_dailyreport');")
                table_exists = cursor.fetchone()[0] is not None
            except Exception:
                # SQLite way - check sqlite_master
                try:
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='models_app_dailyreport';")
                    table_exists = cursor.fetchone() is not None
                except Exception:
                    table_exists = True  # Assume exists, let Django handle
            if not table_exists:
                print("⏳ Tables not yet created - skipping ALTER, will be created by Django", flush=True)
                return
            # Indexes - work on both
            try:
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_fast_email ON models_app_appuser (email);")
            except Exception:
                pass
            try:
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_fast_user_date ON models_app_dailyreport (user_id, report_date);")
            except Exception:
                pass
            try:
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_fast_date ON models_app_dailyreport (report_date);")
                # Ensure ConnectionEntry table exists (for old Neon DB without migration)
                try:
                    # Postgres
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS models_app_connectionentry (
                            id BIGSERIAL PRIMARY KEY,
                            report_date DATE NOT NULL,
                            connection_no VARCHAR(100) NOT NULL DEFAULT '',
                            name VARCHAR(150) NOT NULL DEFAULT '',
                            mobile VARCHAR(20) NOT NULL DEFAULT '',
                            area_name VARCHAR(100) NOT NULL DEFAULT '',
                            created_at TIMESTAMPTZ DEFAULT NOW(),
                            user_id BIGINT NOT NULL REFERENCES models_app_appuser (id) ON DELETE CASCADE,
                            report_id BIGINT REFERENCES models_app_dailyreport (id) ON DELETE CASCADE
                        );
                    """)
                except Exception as e:
                    print(f"Conn table create (pg) skip: {e}")
                try:
                    # SQLite fallback
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS models_app_connectionentry (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            report_date DATE NOT NULL,
                            connection_no VARCHAR(100) NOT NULL DEFAULT '',
                            name VARCHAR(150) NOT NULL DEFAULT '',
                            mobile VARCHAR(20) NOT NULL DEFAULT '',
                            area_name VARCHAR(100) NOT NULL DEFAULT '',
                            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                            user_id INTEGER NOT NULL,
                            report_id INTEGER
                        );
                    """)
                except Exception as e:
                    print(f"Conn table create (sqlite) skip: {e}")
            except Exception:
                pass
            try:
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_fast_area ON models_app_savedarea (user_id);")
            except Exception:
                pass
            # Add columns - Postgres uses ADD COLUMN IF NOT EXISTS, SQLite doesn't support IF NOT EXISTS for column
            is_sqlite = connection.vendor == 'sqlite'
            if is_sqlite:
                # SQLite - try to add, ignore if exists - ALL MISSING COLUMNS
                for sql in [
                    "ALTER TABLE models_app_appuser ADD COLUMN created_at DATETIME DEFAULT CURRENT_TIMESTAMP;",
                    "ALTER TABLE models_app_savedarea ADD COLUMN created_at DATETIME DEFAULT CURRENT_TIMESTAMP;",
                    "ALTER TABLE models_app_dailyreport ADD COLUMN labour_name VARCHAR(150) DEFAULT '';",
                    "ALTER TABLE models_app_dailyreport ADD COLUMN connection VARCHAR(100) DEFAULT '';",
                    "ALTER TABLE models_app_appuser ADD COLUMN default_area_name VARCHAR(255) DEFAULT '';",
                    "ALTER TABLE models_app_appuser ADD COLUMN default_labour_name VARCHAR(255) DEFAULT '';",
                    "ALTER TABLE models_app_appuser ADD COLUMN default_connection VARCHAR(100) DEFAULT '';",
                    "ALTER TABLE models_app_dailyreport ADD COLUMN qty_150mm REAL DEFAULT 0;",
                    "ALTER TABLE models_app_dailyreport ADD COLUMN total_pvc REAL DEFAULT 0;",
                    "ALTER TABLE models_app_dailyreport ADD COLUMN total_di REAL DEFAULT 0;",
                    "ALTER TABLE models_app_dailyreport ADD COLUMN extra_63mm REAL DEFAULT 0;",
                    "ALTER TABLE models_app_dailyreport ADD COLUMN extra_90mm REAL DEFAULT 0;",
                    "ALTER TABLE models_app_dailyreport ADD COLUMN extra_110mm REAL DEFAULT 0;",
                    "ALTER TABLE models_app_dailyreport ADD COLUMN extra_150mm REAL DEFAULT 0;",
                    "ALTER TABLE models_app_dailyreport ADD COLUMN total_mtr REAL DEFAULT 0;",
                    "ALTER TABLE models_app_dailyreport ADD COLUMN count_63mm INTEGER DEFAULT 0;",
                    "ALTER TABLE models_app_dailyreport ADD COLUMN count_90mm INTEGER DEFAULT 0;",
                    "ALTER TABLE models_app_dailyreport ADD COLUMN count_110mm INTEGER DEFAULT 0;",
                    "ALTER TABLE models_app_dailyreport ADD COLUMN count_150mm INTEGER DEFAULT 0;",
                    "ALTER TABLE models_app_dailyreport ADD COLUMN created_at DATETIME DEFAULT CURRENT_TIMESTAMP;",
                    "ALTER TABLE models_app_savedlabour ADD COLUMN created_at DATETIME DEFAULT CURRENT_TIMESTAMP;",
                ]:
                    try:
                        cursor.execute(sql)
                    except Exception:
                        pass
                # Create labour table for SQLite
                try:
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS models_app_savedlabour (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            user_id INTEGER NOT NULL,
                            labour_name VARCHAR(150) NOT NULL,
                            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                            UNIQUE(user_id, labour_name)
                        );
                    """)
                except Exception as e:
                    print(f"Labour table create skip: {e}")
            else:
                # Postgres (Neon) - Fix created_at missing + all extra columns
                # AppUser table
                cursor.execute("ALTER TABLE models_app_appuser ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW();")
                cursor.execute("ALTER TABLE models_app_appuser ADD COLUMN IF NOT EXISTS default_report_title VARCHAR(255) DEFAULT 'Veraval site';")
                cursor.execute("ALTER TABLE models_app_appuser ADD COLUMN IF NOT EXISTS default_area_name VARCHAR(255) DEFAULT '';")
                cursor.execute("ALTER TABLE models_app_appuser ADD COLUMN IF NOT EXISTS default_labour_name VARCHAR(255) DEFAULT '';")
                cursor.execute("ALTER TABLE models_app_appuser ADD COLUMN IF NOT EXISTS default_connection VARCHAR(100) DEFAULT '';")
                cursor.execute("ALTER TABLE models_app_dailyreport ADD COLUMN IF NOT EXISTS connection VARCHAR(100) DEFAULT '';")
                cursor.execute("ALTER TABLE models_app_dailyreport ADD COLUMN IF NOT EXISTS labour_name VARCHAR(150) DEFAULT '';")
                cursor.execute("ALTER TABLE models_app_appuser ADD COLUMN IF NOT EXISTS default_area_name VARCHAR(255) DEFAULT '';")
                cursor.execute("ALTER TABLE models_app_appuser ADD COLUMN IF NOT EXISTS default_labour_name VARCHAR(255) DEFAULT '';")
                cursor.execute("ALTER TABLE models_app_appuser ADD COLUMN IF NOT EXISTS default_connection VARCHAR(100) DEFAULT '';")
                cursor.execute("ALTER TABLE models_app_dailyreport ADD COLUMN IF NOT EXISTS connection VARCHAR(100) DEFAULT '';")
                cursor.execute("ALTER TABLE models_app_dailyreport ADD COLUMN IF NOT EXISTS labour_name VARCHAR(150) DEFAULT '';")
                # SavedArea
                cursor.execute("ALTER TABLE models_app_savedarea ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW();")
                # SavedLabour
                cursor.execute("ALTER TABLE models_app_savedlabour ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW();")
                # DailyReport
                cursor.execute("ALTER TABLE models_app_dailyreport ADD COLUMN IF NOT EXISTS labour_name VARCHAR(150) DEFAULT '';")
                cursor.execute("ALTER TABLE models_app_dailyreport ADD COLUMN IF NOT EXISTS qty_150mm DOUBLE PRECISION DEFAULT 0;")
                cursor.execute("ALTER TABLE models_app_dailyreport ADD COLUMN IF NOT EXISTS total_pvc DOUBLE PRECISION DEFAULT 0;")
                cursor.execute("ALTER TABLE models_app_dailyreport ADD COLUMN IF NOT EXISTS total_di DOUBLE PRECISION DEFAULT 0;")
                cursor.execute("ALTER TABLE models_app_dailyreport ADD COLUMN IF NOT EXISTS extra_63mm DOUBLE PRECISION DEFAULT 0;")
                cursor.execute("ALTER TABLE models_app_dailyreport ADD COLUMN IF NOT EXISTS extra_90mm DOUBLE PRECISION DEFAULT 0;")
                cursor.execute("ALTER TABLE models_app_dailyreport ADD COLUMN IF NOT EXISTS extra_110mm DOUBLE PRECISION DEFAULT 0;")
                cursor.execute("ALTER TABLE models_app_dailyreport ADD COLUMN IF NOT EXISTS extra_150mm DOUBLE PRECISION DEFAULT 0;")
                cursor.execute("ALTER TABLE models_app_dailyreport ADD COLUMN IF NOT EXISTS total_mtr DOUBLE PRECISION DEFAULT 0;")
                cursor.execute("ALTER TABLE models_app_dailyreport ADD COLUMN IF NOT EXISTS count_63mm INTEGER DEFAULT 0;")
                cursor.execute("ALTER TABLE models_app_dailyreport ADD COLUMN IF NOT EXISTS count_90mm INTEGER DEFAULT 0;")
                cursor.execute("ALTER TABLE models_app_dailyreport ADD COLUMN IF NOT EXISTS count_110mm INTEGER DEFAULT 0;")
                cursor.execute("ALTER TABLE models_app_dailyreport ADD COLUMN IF NOT EXISTS count_150mm INTEGER DEFAULT 0;")
                cursor.execute("ALTER TABLE models_app_dailyreport ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW();")
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS models_app_savedlabour (
                        id BIGSERIAL PRIMARY KEY,
                        user_id BIGINT NOT NULL REFERENCES models_app_appuser(id) ON DELETE CASCADE,
                        labour_name VARCHAR(150) NOT NULL,
                        created_at TIMESTAMPTZ DEFAULT NOW(),
                        UNIQUE(user_id, labour_name)
                    );
                """)
                # Fix savedlabour created_at if table existed before
                cursor.execute("ALTER TABLE models_app_savedlabour ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW();")
            print("✅ FAST INDEX OK - Point values handled by FloatField", flush=True)
    except Exception as e:
        print(f"Index skip (safe): {e}", flush=True)
ensure_neon_fast()

try:
    from models_app.models import PasswordResetToken
    HAS_TOKEN_MODEL = True
except:
    HAS_TOKEN_MODEL = False

from django.contrib.auth.hashers import make_password, check_password
from django.db.models import Sum
from django.utils import timezone
PORT = int(os.getenv("PORT", "8080"))
STORAGE_SECRET = os.getenv("STORAGE_SECRET", "my_persistent_secret_key_123")

def is_valid_6digit(pwd):
    return isinstance(pwd, str) and len(pwd)==6 and pwd.isdigit()

@app.get("/health")
def health_check():
    return {"status":"ok","mode":"VERAVAL TRACKER - 63,90,110,150"}

def get_q(report, field, default=0):
    try:
        return getattr(report, field, default) or 0
    except:
        return default

def generate_single_csv(report):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([report.report_title])
    conn = get_q(report, 'connection', '')
    writer.writerow([f"Date: {report.report_date.strftime('%d-%m-%Y')}", f"Area: {report.area_name}", f"Labour: {get_q(report, 'labour_name', '')}", f"Connection: {conn}"])
    writer.writerow([])
    ex63 = get_q(report,'extra_63mm',0); ex90 = get_q(report,'extra_90mm',0); ex110 = get_q(report,'extra_110mm',0); ex150 = get_q(report,'extra_150mm',0)
    writer.writerow(["PVC PIPES"])
    writer.writerow(["Sr.No", "Pipe Dia", "Quantity", "UNIT", "Pipe MTR", "Extra MTR", "Total MTR"])
    m63 = get_q(report,'qty_63mm')*6; m90 = get_q(report,'qty_90mm')*6; m110 = get_q(report,'qty_110mm')*6
    writer.writerow([1, "63MM PVC", get_q(report,'qty_63mm'), "6MTR per PIPES", f"{m63} MTR", f"{ex63} MTR", f"{m63+ex63} MTR"])
    writer.writerow([2, "90MM PVC", get_q(report,'qty_90mm'), "6MTR per PIPES", f"{m90} MTR", f"{ex90} MTR", f"{m90+ex90} MTR"])
    writer.writerow([3, "110MM PVC", get_q(report,'qty_110mm'), "6MTR per PIPES", f"{m110} MTR", f"{ex110} MTR", f"{m110+ex110} MTR"])
    pvc = get_q(report,'qty_63mm')+get_q(report,'qty_90mm')+get_q(report,'qty_110mm')
    pvc_mtr = m63+m90+m110
    pvc_extra = ex63+ex90+ex110
    writer.writerow([f"PVC Total: {pvc} Qty | Pipe:{pvc_mtr} + Extra:{pvc_extra} = Total:{pvc_mtr+pvc_extra} MTR"])
    writer.writerow([])
    writer.writerow(["DI PIPES"])
    writer.writerow(["Sr.No", "Pipe Dia", "Quantity", "UNIT", "Pipe MTR", "Extra MTR", "Total MTR"])
    di = get_q(report,'qty_150mm')
    di_mtr = di*5.5
    writer.writerow([1, "150MM DI", di, "5.5MTR", f"{di_mtr} MTR", f"{ex150} MTR", f"{di_mtr+ex150} MTR"])
    writer.writerow([f"DI Total: {di} Qty | Pipe:{di_mtr} + Extra:{ex150} = Total:{di_mtr+ex150} MTR"])
    writer.writerow([])
    grand_mtr = get_q(report,'total_mtr', pvc_mtr+di_mtr+pvc_extra+ex150)
    writer.writerow([f"GRAND TOTAL MTR: {grand_mtr} MTR (Pipe + Extra)"])
    return output.getvalue().encode("utf-8")

def generate_single_excel(report):
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
        wb = Workbook(); ws = wb.active; ws.title = "Report"
        thin = Border(left=Side(style='thin'), right=Side(style='thin'), top=Side(style='thin'), bottom=Side(style='thin'))
        hdr_fill = PatternFill(start_color="10B981", end_color="10B981", fill_type="solid")
        hdr_font = Font(bold=True, color="FFFFFF", size=11)
        ex63 = get_q(report,'extra_63mm',0); ex90 = get_q(report,'extra_90mm',0); ex110 = get_q(report,'extra_110mm',0); ex150 = get_q(report,'extra_150mm',0)
        ws.merge_cells('A1:G1'); ws['A1'] = report.report_title; ws['A1'].font = Font(bold=True, size=14); ws['A1'].alignment = Alignment(horizontal='center')
        ws.merge_cells('A2:G2'); ws['A2'] = f"Date: {report.report_date.strftime('%d-%m-%Y')} | Area: {report.area_name} | Labour: {get_q(report,'labour_name','')} | Connection: {get_q(report,'connection','')}"; ws['A2'].alignment = Alignment(horizontal='center')
        ws.append([]); ws.append(["Sr.No", "Pipe Dia", "Quantity", "UNIT", "Pipe MTR", "Extra MTR", "Total MTR"])
        r = ws.max_row
        for col in range(1,8): cell = ws.cell(row=r, column=col); cell.fill = hdr_fill; cell.font = hdr_font; cell.alignment = Alignment(horizontal='center'); cell.border = thin
        for idx, (dia, qty, unit, pipe_mtr, extra) in enumerate([
            ("63MM PVC", get_q(report,'qty_63mm'), "6MTR", get_q(report,'qty_63mm')*6, ex63),
            ("90MM PVC", get_q(report,'qty_90mm'), "6MTR", get_q(report,'qty_90mm')*6, ex90),
            ("110MM PVC", get_q(report,'qty_110mm'), "6MTR", get_q(report,'qty_110mm')*6, ex110),
            ("150MM DI", get_q(report,'qty_150mm'), "5.5MTR", get_q(report,'qty_150mm')*5.5, ex150)
        ], start=1):
            total = pipe_mtr + extra
            ws.append([idx, dia, qty, unit, f"{pipe_mtr} MTR", f"{extra} MTR", f"{total} MTR"])
            rr = ws.max_row
            for c in range(1,8): ws.cell(row=rr, column=c).alignment = Alignment(horizontal='center'); ws.cell(row=rr, column=c).border = thin
        ws.append([])
        pvc = get_q(report,'qty_63mm')+get_q(report,'qty_90mm')+get_q(report,'qty_110mm')
        pvc_mtr = get_q(report,'qty_63mm')*6 + get_q(report,'qty_90mm')*6 + get_q(report,'qty_110mm')*6
        pvc_extra = ex63+ex90+ex110
        di = get_q(report,'qty_150mm'); di_mtr = di*5.5
        ws.append(["", "Total PVC", f"{pvc} Qty", "", f"{pvc_mtr} MTR", f"{pvc_extra} MTR", f"{pvc_mtr+pvc_extra} MTR"])
        ws.append(["", "Total DI", f"{di} Qty", "", f"{di_mtr} MTR", f"{ex150} MTR", f"{di_mtr+ex150} MTR"])
        grand = get_q(report,'total_mtr', pvc_mtr+pvc_extra+di_mtr+ex150)
        ws.append(["", "GRAND TOTAL MTR", "", "", "", "", f"{grand} MTR"])
        for rr in [ws.max_row-2, ws.max_row-1, ws.max_row]:
            for c in range(1,8): ws.cell(row=rr, column=c).font = Font(bold=True); ws.cell(row=rr, column=c).alignment = Alignment(horizontal='center'); ws.cell(row=rr, column=c).border = thin
        ws.column_dimensions['A'].width = 10; ws.column_dimensions['B'].width = 15; ws.column_dimensions['C'].width = 12; ws.column_dimensions['D'].width = 10; ws.column_dimensions['E'].width = 14; ws.column_dimensions['F'].width = 14; ws.column_dimensions['G'].width = 14
        out = io.BytesIO(); wb.save(out); return out.getvalue()
    except Exception as e:
        print(f"Excel error: {e}")
        return generate_single_csv(report)

def generate_single_pdf(report):
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
        from reportlab.lib import colors
        output = io.BytesIO(); c = canvas.Canvas(output, pagesize=A4); width, height = A4
        c.setFillColor(colors.black)
        c.setFont("Helvetica-Bold", 16)
        c.drawCentredString(width/2, height-40, report.report_title)
        c.setFont("Helvetica", 11)
        c.setFillColor(colors.black)
        conn = get_q(report, 'connection', '')
        c.drawCentredString(width/2, height-60, f"Area: {report.area_name or 'No Area'} | Labour: {get_q(report,'labour_name','') or 'No Labour'} | Connection: {conn or '-'}")
        c.drawCentredString(width/2, height-75, f"Date: {report.report_date.strftime('%d-%m-%Y')}")
        y = height - 110
        # Extra values
        ex63 = get_q(report,'extra_63mm',0); ex90 = get_q(report,'extra_90mm',0); ex110 = get_q(report,'extra_110mm',0); ex150 = get_q(report,'extra_150mm',0)
        total_mtr_field = get_q(report,'total_mtr',0)
        # PVC PIPES
        y -= 10
        c.setFillColor(colors.HexColor("#DC2626"))
        c.setFont("Helvetica-Bold", 14)
        c.drawCentredString(width/2, y, "PVC PIPES")
        y -= 25
        c.setFillColor(colors.HexColor("#059669")); c.rect(30, y-5, 540, 25, fill=1, stroke=0)
        c.setFillColor(colors.white); c.setFont("Helvetica-Bold", 10)
        c.drawString(35, y+2, "Sr.No"); c.drawString(70, y+2, "Pipe Dia"); c.drawString(135, y+2, "Qty"); c.drawString(175, y+2, "UNIT"); c.drawString(220, y+2, "Pipe MTR"); c.drawString(300, y+2, "Extra MTR"); c.drawString(380, y+2, "Total MTR")
        y -= 30; c.setFont("Helvetica", 11)
        pvc_total = 0; pvc_mtr_total = 0; pvc_extra_total = 0
        data = [
            ("63MM PVC", get_q(report,'qty_63mm'), "6MTR", get_q(report,'qty_63mm')*6, ex63),
            ("90MM PVC", get_q(report,'qty_90mm'), "6MTR", get_q(report,'qty_90mm')*6, ex90),
            ("110MM PVC", get_q(report,'qty_110mm'), "6MTR", get_q(report,'qty_110mm')*6, ex110),
        ]
        for idx, (dia, qty, unit, mtr, extra) in enumerate(data, start=1):
            if idx % 2 == 0: c.setFillColor(colors.HexColor("#ECFDF5")); c.rect(30, y-5, 540, 22, fill=1, stroke=0)
            c.setFillColor(colors.black)
            total = mtr + extra
            c.drawString(40, y, str(idx)); c.drawString(70, y, dia); c.drawString(135, y, str(qty)); c.drawString(175, y, unit); 
            c.drawString(220, y, f"{mtr} MTR"); c.drawString(290, y, f"{extra} MTR"); c.drawString(360, y, f"{total} MTR")
            y -= 22
            pvc_total += qty; pvc_mtr_total += mtr; pvc_extra_total += extra
        y -= 5
        c.setFillColor(colors.HexColor("#D1FAE5")); c.rect(30, y-5, 540, 22, fill=1, stroke=0)
        c.setFillColor(colors.HexColor("#059669")); c.setFont("Helvetica-Bold", 10)
        c.drawString(35, y+2, f"PVC Total: {pvc_total} Qty | Pipe:{pvc_mtr_total} + Extra:{pvc_extra_total} = {pvc_mtr_total+pvc_extra_total} MTR")
        y -= 30
        # DI PIPES
        y -= 15
        c.setFillColor(colors.HexColor("#DC2626"))
        c.setFont("Helvetica-Bold", 14)
        c.drawCentredString(width/2, y, "DI PIPES")
        y -= 25
        c.setFillColor(colors.HexColor("#059669")); c.rect(30, y-5, 540, 25, fill=1, stroke=0)
        c.setFillColor(colors.white); c.setFont("Helvetica-Bold", 10)
        c.drawString(35, y+2, "Sr.No"); c.drawString(70, y+2, "Pipe Dia"); c.drawString(135, y+2, "Qty"); c.drawString(175, y+2, "UNIT"); c.drawString(220, y+2, "Pipe MTR"); c.drawString(300, y+2, "Extra MTR"); c.drawString(380, y+2, "Total MTR")
        y -= 30; c.setFont("Helvetica", 11)
        di_qty = get_q(report,'qty_150mm')
        di_mtr = di_qty * 5.5
        di_total = di_mtr + ex150
        c.setFillColor(colors.HexColor("#ECFDF5")); c.rect(30, y-5, 540, 22, fill=1, stroke=0)
        c.setFillColor(colors.black)
        c.drawString(40, y, "1"); c.drawString(70, y, "150MM DI"); c.drawString(135, y, str(di_qty)); c.drawString(175, y, "5.5MTR"); 
        c.drawString(220, y, f"{di_mtr} MTR"); c.drawString(290, y, f"{ex150} MTR"); c.drawString(360, y, f"{di_total} MTR")
        y -= 22
        y -= 5
        c.setFillColor(colors.HexColor("#D1FAE5")); c.rect(30, y-5, 540, 22, fill=1, stroke=0)
        c.setFillColor(colors.HexColor("#059669")); c.setFont("Helvetica-Bold", 10)
        c.drawString(35, y+2, f"DI Total: {di_qty} Qty | Pipe:{di_mtr} + Extra:{ex150} = {di_total} MTR")
        y -= 25
        # Connection info
        conn_val = get_q(report, 'connection', '')
        if conn_val:
            y -= 8
            c.setFillColor(colors.HexColor("#FEF3C7")); c.rect(30, y-5, 540, 22, fill=1, stroke=0)
            c.setFillColor(colors.HexColor("#92400E")); c.setFont("Helvetica-Bold", 11)
            c.drawString(35, y+2, f"Connection: {conn_val} - Total Connections: {conn_val}")
        # Grand total MTR
        grand_mtr = total_mtr_field if total_mtr_field>0 else (pvc_mtr_total+pvc_extra_total+di_total)
        c.setFillColor(colors.HexColor("#1F2937")); c.rect(30, y-5, 540, 25, fill=1, stroke=0)
        c.setFillColor(colors.white); c.setFont("Helvetica-Bold", 12)
        c.drawCentredString(width/2, y+2, f"GRAND TOTAL MTR: {grand_mtr} MTR")
        # Connection summary footer
        if conn_val:
            y -= 30
            c.setFillColor(colors.HexColor("#F59E0B")); c.rect(30, y-5, 540, 22, fill=1, stroke=0)
            c.setFillColor(colors.white); c.setFont("Helvetica-Bold", 11)
            c.drawCentredString(width/2, y+2, f"Total Connections in this report: {conn_val}")
        c.showPage(); c.save(); return output.getvalue()
    except Exception as e:
        print(f"PDF error: {e}")
        import traceback; traceback.print_exc()
        return generate_single_csv(report)

def generate_month_csv(title, period_text, t63, t90, t110, t150=0, te63=0, te90=0, te110=0, te150=0, total_connections=0):
    output = io.StringIO(); writer = csv.writer(output)
    writer.writerow([title]); writer.writerow([period_text]); writer.writerow([])
    writer.writerow(["Sr.No", "Pipe Dia", "Qty", "Extra", "UNIT", "Total MTR"])
    tm63 = t63*6 + te63; tm90 = t90*6 + te90; tm110 = t110*6 + te110; tm150 = t150*5.5 + te150
    writer.writerow([1, "63MM PVC", t63, te63, "6MTR per PIPES", tm63]); writer.writerow([2, "90MM PVC", t90, te90, "6MTR per PIPES", tm90]); writer.writerow([3, "110MM PVC", t110, te110, "6MTR per PIPES", tm110]); writer.writerow([4, "150MM DI", t150, te150, "5.5MTR", tm150]); writer.writerow([])
    writer.writerow([f"Total PVC: {t63+t90+t110} Qty | Extra: {te63+te90+te110} MTR | Total MTR: {tm63+tm90+tm110} MTR"])
    writer.writerow([f"Total DI: {t150} Qty | Extra: {te150} MTR | Total MTR: {tm150} MTR"])
    writer.writerow([f"Grand Extra: {te63+te90+te110+te150} MTR | Grand Total MTR: {tm63+tm90+tm110+tm150} MTR"])
    writer.writerow([f"Grand Total Qty: {t63+t90+t110+t150} Qty"])
    writer.writerow([f"Total Connections: {total_connections}"])
    return output.getvalue().encode("utf-8")

def generate_month_excel(title, period_text, t63, t90, t110, t150=0, te63=0, te90=0, te110=0, te150=0, total_connections=0):
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
        wb = Workbook(); ws = wb.active; ws.title = "Monthly"
        thin = Border(left=Side(style='thin'), right=Side(style='thin'), top=Side(style='thin'), bottom=Side(style='thin'))
        hdr_fill = PatternFill(start_color="10B981", end_color="10B981", fill_type="solid")
        hdr_font = Font(bold=True, color="FFFFFF", size=11)
        ws.merge_cells('A1:F1'); ws['A1'] = title; ws['A1'].font = Font(bold=True, size=14); ws['A1'].alignment = Alignment(horizontal='center')
        ws.merge_cells('A2:F2'); ws['A2'] = period_text; ws['A2'].alignment = Alignment(horizontal='center')
        ws.append([]); ws.append(["Sr.No", "Pipe Dia", "Qty", "Extra", "UNIT", "Total MTR"])
        r = ws.max_row
        for col in range(1,7): cell = ws.cell(row=r, column=col); cell.fill = hdr_fill; cell.font = hdr_font; cell.alignment = Alignment(horizontal='center'); cell.border = thin
        tm63 = t63*6 + te63; tm90 = t90*6 + te90; tm110 = t110*6 + te110; tm150 = t150*5.5 + te150
        for idx, (dia, qty, extra, unit, total_mtr) in enumerate([("63MM PVC", t63, te63, "6MTR per PIPES", tm63), ("90MM PVC", t90, te90, "6MTR per PIPES", tm90), ("110MM PVC", t110, te110, "6MTR per PIPES", tm110), ("150MM DI", t150, te150, "5.5MTR", tm150)], start=1):
            ws.append([idx, dia, qty, extra, unit, total_mtr]); rr = ws.max_row
            for col in range(1,7): ws.cell(row=rr, column=col).alignment = Alignment(horizontal='center'); ws.cell(row=rr, column=col).border = thin
        ws.append([]); ws.append(["", "Total PVC", f"{t63+t90+t110} Qty", f"{te63+te90+te110} MTR", "", f"{tm63+tm90+tm110} MTR"]); ws.append(["", "Total DI", f"{t150} Qty", f"{te150} MTR", "", f"{tm150} MTR"]); ws.append(["", "Grand Extra", f"{te63+te90+te110+te150} MTR", "", "", f"{tm63+tm90+tm110+tm150} MTR"]); ws.append(["", "Grand Total", f"{t63+t90+t110+t150} Qty", "", "", ""]); ws.append(["", "Total Connections", f"{total_connections}", "", "", ""])
        for rr in range(ws.max_row-4, ws.max_row+1):
            for col in range(1,6):
                try:
                    ws.cell(row=rr, column=col).font = Font(bold=True); ws.cell(row=rr, column=col).alignment = Alignment(horizontal='center'); ws.cell(row=rr, column=col).border = thin
                except:
                    pass
        ws.column_dimensions['A'].width = 12; ws.column_dimensions['B'].width = 18; ws.column_dimensions['C'].width = 18; ws.column_dimensions['D'].width = 15; ws.column_dimensions['E'].width = 18; ws.column_dimensions['F'].width = 18
        out = io.BytesIO(); wb.save(out); return out.getvalue()
    except Exception as e:
        print(f"Month Excel error: {e}")
        return generate_month_csv(title, period_text, t63, t90, t110, t150, te63, te90, te110, te150, total_connections)

def generate_month_pdf(title, period_text, t63, t90, t110, t150=0, te63=0, te90=0, te110=0, te150=0, total_connections=0):
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
        from reportlab.lib import colors
        output = io.BytesIO(); c = canvas.Canvas(output, pagesize=A4); w, h = A4
        c.setFillColor(colors.HexColor("#10B981")); c.rect(0, h-80, w, 80, fill=1, stroke=0)
        c.setFillColor(colors.white); c.setFont("Helvetica-Bold", 16); c.drawCentredString(w/2, h-35, title)
        c.setFont("Helvetica", 10); c.drawCentredString(w/2, h-55, period_text)
        y = h - 120
        c.setFillColor(colors.HexColor("#059669")); c.rect(50, y-5, 500, 25, fill=1, stroke=0)
        c.setFillColor(colors.white); c.setFont("Helvetica-Bold", 10); c.drawString(55, y+2, "Sr.No"); c.drawString(90, y+2, "Pipe Dia"); c.drawString(200, y+2, "Qty"); c.drawString(260, y+2, "Extra"); c.drawString(320, y+2, "UNIT"); c.drawString(420, y+2, "Total MTR")
        y -= 30; c.setFont("Helvetica", 12)
        tm63 = t63*6 + te63; tm90 = t90*6 + te90; tm110 = t110*6 + te110; tm150 = t150*5.5 + te150
        for idx, (dia, qty, extra, unit, total_mtr) in enumerate([("63MM PVC", t63, te63, "6MTR per PIPES", tm63), ("90MM PVC", t90, te90, "6MTR per PIPES", tm90), ("110MM PVC", t110, te110, "6MTR per PIPES", tm110), ("150MM DI", t150, te150, "5.5MTR", tm150)], start=1):
            if idx % 2 == 0: c.setFillColor(colors.HexColor("#ECFDF5")); c.rect(50, y-5, 500, 22, fill=1, stroke=0)
            c.setFillColor(colors.black)
            c.drawString(60, y, str(idx)); c.drawString(90, y, dia); c.drawString(210, y, str(qty)); c.drawString(265, y, str(extra)); c.drawString(320, y, unit); c.drawString(420, y, f"{total_mtr} MTR")
            y -= 22
        y -= 10
        c.setFillColor(colors.HexColor("#DBEAFE")); c.rect(50, y-5, 500, 22, fill=1, stroke=0)
        c.setFillColor(colors.HexColor("#1E40AF")); c.setFont("Helvetica-Bold", 11)
        c.drawString(55, y+2, f"PVC: {t63+t90+t110} Qty Extra:{te63+te90+te110} MTR:{tm63+tm90+tm110}")
        y -= 22
        c.setFillColor(colors.HexColor("#E9D5FF")); c.rect(50, y-5, 500, 22, fill=1, stroke=0)
        c.setFillColor(colors.HexColor("#6B21A8")); c.setFont("Helvetica-Bold", 11)
        c.drawString(55, y+2, f"DI: {t150} Qty Extra:{te150} MTR:{tm150}")
        y -= 22
        c.setFillColor(colors.HexColor("#D1FAE5")); c.rect(50, y-5, 500, 25, fill=1, stroke=0)
        c.setFillColor(colors.HexColor("#059669")); c.setFont("Helvetica-Bold", 11)
        c.drawString(55, y+2, f"Grand: {t63+t90+t110+t150} Qty | Grand Extra: {te63+te90+te110+te150} MTR | Grand MTR: {tm63+tm90+tm110+tm150}")
        y -= 30
        c.setFillColor(colors.HexColor("#F59E0B")); c.rect(50, y-5, 500, 25, fill=1, stroke=0)
        c.setFillColor(colors.white); c.setFont("Helvetica-Bold", 12)
        c.drawCentredString(w/2, y+2, f"Total Connections: {total_connections}")
        c.showPage(); c.save(); return output.getvalue()
    except Exception as e:
        print(f"Month PDF error: {e}")
        import traceback; traceback.print_exc()
        return generate_month_csv(title, period_text, t63, t90, t110, t150, te63, te90, te110, te150, total_connections)



ui.add_css("""
    .spa-hidden { display: none !important; }
    .report-patti { transition: all 0.15s; cursor: pointer; }
    .report-patti:hover { transform: translateY(-2px); box-shadow: 0 8px 20px rgba(16,185,129,0.2); border-color: #10B981 !important; }
    .editable-area .q-field__control { min-height: 48px !important; border-radius: 12px !important; }
    .editable-area input { font-weight: 700 !important; font-size: 14px !important; }
    .back-btn { background-color: #d4821e !important; color: black !important; border: 2px solid #b56a17 !important; border-radius: 20px !important; font-weight: bold !important; }
    .back-btn .q-btn__content { color: black !important; }
    .date-pill { background: white !important; border: 1.5px solid #e5e7eb !important; border-radius: 9999px !important; box-shadow: 0 1px 3px rgba(0,0,0,0.1) !important; padding: 6px 16px !important; display: flex !important; align-items: center !important; gap: 8px !important; min-width: 145px !important; }
    .date-pill input { border: none !important; outline: none !important; font-weight: 700 !important; font-size: 13px !important; color: #1f2937 !important; background: transparent !important; width: 100px !important; text-align: center !important; cursor: pointer !important; }
    .date-pill .q-field__control { background: transparent !important; border: none !important; box-shadow: none !important; min-height: auto !important; height: auto !important; padding: 0 !important; }
    .date-pill .q-field__control:before, .date-pill .q-field__control:after { display: none !important; }
    .profile-card { background: white !important; border-radius: 24px !important; box-shadow: 0 10px 30px rgba(0,0,0,0.08) !important; border: 1.5px solid #e0f2e9 !important; }
    .delete-btn { background: white !important; color: #dc2626 !important; border: 1.5px solid #fecaca !important; border-radius: 9999px !important; font-weight: 700 !important; }
    .edit-mini-btn { background: white !important; color: #2563eb !important; border: 1.2px solid #bfdbfe !important; border-radius: 12px !important; font-weight: 700 !important; font-size: 11px !important; }
    .del-mini-btn { background: white !important; color: #dc2626 !important; border: 1.2px solid #fecaca !important; border-radius: 12px !important; font-weight: 700 !important; font-size: 11px !important; }
    .patti-click-area { cursor: pointer; }
    .forgot-link { color: #2563eb !important; font-weight: 700 !important; font-size: 13px !important; cursor: pointer !important; }
""", shared=True)

@ui.page("/reset")
def reset_page_with_query():
    try:
        request = ui.context.client.request
        token = request.query_params.get("token", "")
        if not token:
            token = str(request.url).split("token=")[-1].split("&")[0] if "token=" in str(request.url) else ""
    except Exception:
        token = ""
    return build_reset_content(token)

@ui.page("/reset/{token}")
def reset_page_with_path(token: str):
    return build_reset_content(token)

def build_reset_content(token: str):
    with ui.column().classes("w-full min-h-screen items-center justify-center bg-gradient-to-br from-indigo-900 via-purple-900 to-slate-900 p-3"):
        with ui.card().classes("w-full max-w-sm rounded-3xl shadow-2xl overflow-hidden p-0"):
            with ui.column().classes("w-full bg-gradient-to-r from-emerald-500 via-teal-600 to-cyan-600 p-5 items-center text-white"):
                ui.icon("lock_reset", size="2.5rem")
                ui.label("Reset Password (6-digit)").classes("text-xl font-extrabold")
            with ui.column().classes("w-full p-5 bg-white gap-3") as content_col:
                db_token_obj = None
                user = None
                email = None
                try:
                    if HAS_TOKEN_MODEL:
                        db_token_obj = PasswordResetToken.objects.get(token=token)
                        age = (timezone.now() - db_token_obj.created_at).total_seconds()
                        if age > 900:
                            db_token_obj.delete()
                            ui.label("Link Expired! (15 min over)").classes("text-red-600 font-bold text-center w-full")
                            ui.button("Go to Login", icon="login", on_click=lambda: ui.navigate.to("/")).props("rounded no-caps").classes("w-full mt-2 bg-blue-600 text-white font-bold")
                            return
                        user = db_token_obj.user
                        email = user.email
                    else:
                        raise Exception("No DB model")
                except Exception as e:
                    ui.label("Invalid or Expired Link!").classes("text-red-600 font-bold text-center w-full")
                    ui.button("Go to Login", icon="login", on_click=lambda: ui.navigate.to("/")).props("rounded no-caps").classes("w-full mt-3 bg-blue-600 text-white font-bold")
                    return
                ui.label(f"Welcome {user.username}").classes("text-lg font-extrabold text-slate-900 text-center w-full")
                ui.label(f"For: {email}").classes("text-xs font-bold text-slate-600 text-center w-full break-all")
                ui.label("Change Password (6-digit only)").classes("text-sm font-bold text-indigo-700 mt-2 w-full text-center")
                new_pwd = ui.input("Enter new password (6 digits)", placeholder="Ex: 123456", password=True, password_toggle_button=True).props("outlined rounded dense maxlength=6").classes("w-full")
                re_new_pwd = ui.input("Re-enter new password (6 digits)", placeholder="Ex: 123456", password=True, password_toggle_button=True).props("outlined rounded dense maxlength=6").classes("w-full")
                status_lbl = ui.label("").classes("text-xs font-bold text-center w-full")
                def do_confirm_reset():
                    p1 = (new_pwd.value or "").strip()
                    p2 = (re_new_pwd.value or "").strip()
                    if not is_valid_6digit(p1):
                        status_lbl.set_text("❌ Password must be exactly 6 digits!")
                        return
                    if p1 != p2:
                        status_lbl.set_text("❌ Both passwords not same!")
                        return
                    try:
                        user.password = make_password(p1)
                        user.save(update_fields=['password'])
                        CACHE["users"].pop(email, None)
                        CACHE["pwd_verified"] = {k:v for k,v in CACHE["pwd_verified"].items() if v != user.id}
                        if db_token_obj:
                            db_token_obj.delete()
                        content_col.clear()
                        with content_col:
                            ui.icon("check_circle", size="3rem", color="green")
                            ui.label("Successfully changed password!").classes("text-base font-extrabold text-green-700 text-center w-full mt-2")
                            ui.button("Go to Login", icon="login", on_click=lambda: ui.navigate.to("/")).props("rounded no-caps").classes("w-full mt-4 bg-gradient-to-r from-emerald-600 to-green-600 text-white font-bold py-2.5 shadow-lg")
                    except Exception as e:
                        status_lbl.set_text(f"❌ Failed: {e}")
                ui.button("Confirm (6-digit)", icon="check", on_click=do_confirm_reset).props("rounded no-caps").classes("w-full mt-2 bg-gradient-to-r from-emerald-600 to-green-600 text-white font-bold py-2.5 shadow-lg")

@ui.page("/")
def main_spa_page():
    print("🚀 FINAL VERAVAL TRACKER - 63,90,110,150", flush=True)
    state = {"user": None, "selected_report": None}
    with ui.column().classes("w-full min-h-screen p-0 m-0 gap-0") as root:
        login_view = ui.column().classes("w-full min-h-screen items-center justify-center bg-gradient-to-br from-indigo-900 via-purple-900 to-slate-900 p-3")
        with login_view:
            with ui.card().classes("w-full max-w-sm rounded-3xl shadow-2xl overflow-hidden p-0 border-2 border-green-400/50"):
                with ui.column().classes("w-full bg-gradient-to-r from-emerald-500 via-green-600 to-teal-600 p-4 items-center text-white"):
                    ui.icon("bolt", size="2.5rem")
                    ui.label("VERAVAL SITE TRACKER").classes("text-xl font-extrabold")
                    ui.label("PipeLine Progress").classes("text-xs")
                with ui.column().classes("w-full p-5 bg-white gap-3"):
                    saved_email = app.storage.user.get("saved_email", "")
                    saved_pwd = app.storage.user.get("saved_password", "")
                    email_input = ui.input("Email ID", value=saved_email).props("outlined rounded dense").classes("w-full")
                    pass_input = ui.input("Password (6 digits)", value=saved_pwd, placeholder="6 digits only", password=True, password_toggle_button=True).props("outlined rounded dense maxlength=6").classes("w-full")
                    login_btn = ui.button("⚡ Log In", icon="bolt").props("rounded no-caps").classes("w-full py-2.5 bg-gradient-to-r from-emerald-600 to-green-600 text-white font-bold shadow-lg")
                    status_label = ui.label("").classes("text-xs text-center font-bold text-green-600")
                    
                    # FAST LOGIN: Check as typing - like 5*6=30 instant - Email+Pwd cached? Instant home
                    def fast_check_login():
                        e = (email_input.value or "").strip()
                        p = (pass_input.value or "").strip()
                        if len(p)==6 and p.isdigit() and e:
                            pwd_key = hashlib.sha256(f"{e}:{p}".encode()).hexdigest()
                            if pwd_key in CACHE["pwd_verified"] and e in CACHE["users"]:
                                status_label.set_text("✅ Ready - Click Login for instant home!")
                                login_btn.classes(add="bg-green-700", remove="bg-gradient-to-r from-emerald-600 to-green-600")
                            else:
                                status_label.set_text("⏳ 6-digit entered - Click to verify")
                        elif len(p)>0 and len(p)<6:
                            status_label.set_text(f"⏳ {len(p)}/6 digits...")
                        elif len(p)==6 and not p.isdigit():
                            status_label.set_text("❌ Only digits allowed")
                        else:
                            status_label.set_text("")
                    
                    email_input.on_value_change(lambda _: fast_check_login())
                    pass_input.on_value_change(lambda _: fast_check_login())
                    # Auto-check on load if saved credentials exist
                    def auto_check_saved():
                        if saved_email and saved_pwd and is_valid_6digit(saved_pwd):
                            fast_check_login()
                    ui.timer(0.5, auto_check_saved, once=True)
                    with ui.row().classes("w-full justify-center mt-1"):
                        forgot_link = ui.label("Forgot password?").classes("forgot-link")
                    reg_btn = ui.button("Register New Account", icon="person_add").props("outline rounded no-caps").classes("w-full text-emerald-600 font-bold text-sm border-emerald-500 mt-2")

        home_view = ui.column().classes("w-full min-h-screen bg-gradient-to-br from-indigo-100 via-purple-50 to-pink-100 py-2 px-1.5 sm:px-4 items-center spa-hidden")
        filter_view = ui.column().classes("w-full min-h-screen bg-gradient-to-br from-indigo-100 via-purple-50 to-pink-100 py-2 px-1.5 sm:px-4 items-center spa-hidden")
        filter_detail_view = ui.column().classes("w-full min-h-screen bg-gradient-to-br from-indigo-100 via-purple-50 to-pink-100 py-2 px-1.5 sm:px-4 items-center spa-hidden")
        profile_view = ui.column().classes("w-full min-h-screen bg-gradient-to-br from-indigo-100 via-purple-50 to-pink-100 p-3 items-center justify-center spa-hidden")
        register_view = ui.column().classes("w-full min-h-screen items-center justify-center bg-gradient-to-br from-indigo-900 via-purple-900 to-slate-900 p-3 spa-hidden")
        forgot_view = ui.column().classes("w-full min-h-screen items-center justify-center bg-gradient-to-br from-indigo-900 via-purple-900 to-slate-900 p-3 spa-hidden")

        def show_login():
            state["user"] = None
            login_view.classes(remove="spa-hidden")
            home_view.classes(add="spa-hidden")
            filter_view.classes(add="spa-hidden")
            filter_detail_view.classes(add="spa-hidden")
            profile_view.classes(add="spa-hidden")
            register_view.classes(add="spa-hidden")
            forgot_view.classes(add="spa-hidden")

        def show_login_as_logout():
            state["user"] = None
            saved_e = app.storage.user.get("saved_email", "")
            saved_p = app.storage.user.get("saved_password", "")
            app.storage.user.clear()
            app.storage.user["saved_email"] = saved_e
            app.storage.user["saved_password"] = saved_p
            show_login()

        def show_home():
            login_view.classes(add="spa-hidden")
            home_view.classes(remove="spa-hidden")
            filter_view.classes(add="spa-hidden")
            filter_detail_view.classes(add="spa-hidden")
            profile_view.classes(add="spa-hidden")
            register_view.classes(add="spa-hidden")
            forgot_view.classes(add="spa-hidden")
            build_home()

        def show_filter():
            # INSTANT UI: Show filter view immediately - No waiting 1-2 sec - UI first, DB later (parallel)
            login_view.classes(add="spa-hidden")
            home_view.classes(add="spa-hidden")
            filter_view.classes(remove="spa-hidden")
            filter_detail_view.classes(add="spa-hidden")
            profile_view.classes(add="spa-hidden")
            register_view.classes(add="spa-hidden")
            forgot_view.classes(add="spa-hidden")
            # Show loading skeleton instantly
            filter_view.clear()
            with filter_view:
                with ui.column().classes("w-full max-w-md items-center gap-2"):
                    with ui.card().classes("w-full rounded-3xl shadow-2xl bg-white p-5 border-2 border-green-200 items-center"):
                        ui.spinner(size="lg", color="green")
                        ui.label("Loading reports...").classes("text-sm font-bold text-green-700 mt-2")
            # Load real data in background - UI + DB parallel
            async def load_filter_bg():
                await asyncio.sleep(0.05)  # Let UI render first
                build_filter()
            ui.timer(0.05, lambda: asyncio.create_task(load_filter_bg()), once=True)

        def show_filter_detail(report):
            state["selected_report"] = report
            login_view.classes(add="spa-hidden")
            home_view.classes(add="spa-hidden")
            filter_view.classes(add="spa-hidden")
            filter_detail_view.classes(remove="spa-hidden")
            profile_view.classes(add="spa-hidden")
            register_view.classes(add="spa-hidden")
            forgot_view.classes(add="spa-hidden")
            build_filter_detail(report)

        def show_profile():
            login_view.classes(add="spa-hidden")
            home_view.classes(add="spa-hidden")
            filter_view.classes(add="spa-hidden")
            filter_detail_view.classes(add="spa-hidden")
            profile_view.classes(remove="spa-hidden")
            register_view.classes(add="spa-hidden")
            forgot_view.classes(add="spa-hidden")
            build_profile()

        def show_register():
            login_view.classes(add="spa-hidden")
            home_view.classes(add="spa-hidden")
            filter_view.classes(add="spa-hidden")
            filter_detail_view.classes(add="spa-hidden")
            profile_view.classes(add="spa-hidden")
            register_view.classes(remove="spa-hidden")
            forgot_view.classes(add="spa-hidden")

        def show_forgot():
            login_view.classes(add="spa-hidden")
            home_view.classes(add="spa-hidden")
            filter_view.classes(add="spa-hidden")
            filter_detail_view.classes(add="spa-hidden")
            profile_view.classes(add="spa-hidden")
            register_view.classes(add="spa-hidden")
            forgot_view.classes(remove="spa-hidden")
            build_forgot()

        def build_forgot():
            forgot_view.clear()
            with forgot_view:
                with ui.card().classes("w-full max-w-sm rounded-3xl shadow-2xl overflow-hidden p-0"):
                    with ui.column().classes("w-full bg-gradient-to-r from-emerald-500 via-teal-600 to-cyan-600 p-5 items-center text-white"):
                        ui.icon("lock_reset", size="2.5rem")
                        ui.label("Direct Reset - No Email!").classes("text-xl font-extrabold")
                        ui.label("ID nakho, tyaj password badli jase").classes("text-xs opacity-90")
                    with ui.column().classes("w-full p-5 bg-white gap-3"):
                        forgot_email = ui.input("Email ID / User ID", placeholder="Enter registered Email").props("outlined rounded dense").classes("w-full")
                        forgot_status = ui.label("").classes("text-sm font-bold text-center w-full py-1")
                        reset_area = ui.column().classes("w-full gap-3 mt-1")
                        
                        async def do_direct_reset(new_pwd_input, re_new_pwd_input, reset_status_label, verified_email):
                            p1 = (new_pwd_input.value or "").strip()
                            p2 = (re_new_pwd_input.value or "").strip()
                            email = verified_email
                            if not is_valid_6digit(p1):
                                reset_status_label.set_text("❌ Password must be exactly 6 digits! Ex: 123456")
                                ui.notify("Password must be exactly 6 digits!", type="negative", position="top")
                                return
                            if p1 != p2:
                                reset_status_label.set_text("❌ Both passwords not same!")
                                return
                            reset_status_label.set_text("⏳ Changing password...")
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
                                    u.save(update_fields=['password'])
                                    return u
                                user = await run.io_bound(update_pwd)
                                if not user:
                                    reset_status_label.set_text("❌ User not found!")
                                    return
                                CACHE["users"].pop(email, None)
                                CACHE["users"][user.email] = user
                                keys_to_del = [k for k in list(CACHE["pwd_verified"].keys()) if email in k]
                                for k in keys_to_del:
                                    CACHE["pwd_verified"].pop(k, None)
                                pwd_key = hashlib.sha256(f"{user.email}:{p1}".encode()).hexdigest()
                                CACHE["pwd_verified"][pwd_key] = user.id
                                app.storage.user["saved_email"] = user.email
                                app.storage.user["saved_password"] = p1
                                reset_status_label.set_text("✅ Password changed! Going to login...")
                                ui.notify("✅ Password changed! Login now", type="positive", position="top")
                                await asyncio.sleep(1.2)
                                show_login()
                            except Exception as e:
                                reset_status_label.set_text(f"❌ Error: {e}")

                        async def verify_id():
                            email = (forgot_email.value or "").strip()
                            if not email:
                                forgot_status.set_text("❌ Enter Email ID / User ID!")
                                return
                            forgot_status.set_text("⏳ Checking ID...")
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
                                    forgot_status.set_text("❌ ID not registered! Check Email/Username")
                                    reset_area.clear()
                                    return
                                forgot_status.set_text(f"✅ Found: {user.username} ({user.email})")
                                reset_area.clear()
                                with reset_area:
                                    ui.separator().classes("my-2")
                                    ui.label("✅ ID Verified! New password nakho:").classes("text-[13px] font-extrabold text-green-700 bg-green-50 px-3 py-1.5 rounded-full text-center w-full")
                                    new_pwd_input = ui.input("New Password (6 digits)", placeholder="Ex: 123456", password=True, password_toggle_button=True).props("outlined rounded dense maxlength=6 color=green").classes("w-full font-bold")
                                    re_new_pwd_input = ui.input("Retype Password (6 digits)", placeholder="Ex: 123456", password=True, password_toggle_button=True).props("outlined rounded dense maxlength=6 color=green").classes("w-full font-bold")
                                    reset_status_label = ui.label("").classes("text-xs font-bold text-center w-full")
                                    ui.button("Change Password - Confirm (6-digit)", icon="check_circle", on_click=lambda: do_direct_reset(new_pwd_input, re_new_pwd_input, reset_status_label, email)).props("rounded no-caps").classes("w-full py-2.5 bg-gradient-to-r from-emerald-600 to-green-600 text-white font-bold shadow-lg mt-1")
                            except Exception as e:
                                forgot_status.set_text(f"❌ Error: {e}")
                        
                        ui.button("Verify ID & Reset Direct", icon="verified_user", on_click=verify_id).props("rounded no-caps").classes("w-full py-2.5 bg-gradient-to-r from-blue-600 to-indigo-600 text-white font-bold shadow-lg mt-2")
                        ui.button("Back to Login", icon="arrow_back", on_click=show_login).props("flat rounded no-caps").classes("w-full text-blue-600 font-bold text-sm mt-1")



        def build_home():
            home_view.clear()
            user = state["user"]
            if not user:
                show_login()
                return
            try:
                fresh_user = AppUser.objects.get(id=user.id)
                CACHE["users"][fresh_user.email] = fresh_user
                state["user"] = fresh_user
                user = fresh_user
            except Exception:
                pass
            with home_view:
                with ui.column().classes("w-full max-w-md items-center gap-0"):
                    with ui.card().classes("w-full rounded-2xl shadow-xl bg-white p-1.5 border-2 border-green-200"):
                        with ui.row().classes("w-full justify-between items-center mb-1 px-1 py-0.5 bg-slate-50 rounded-full border"):
                            ui.button("Back", icon="arrow_back", on_click=show_login_as_logout).props("flat rounded dense no-caps").classes("back-btn text-[11px] shadow-sm")
                            today_str = today_ist().isoformat()
                            with ui.row().classes("date-pill-compact items-center justify-center"):
                                home_date_input = ui.input(value=today_str).props("type=date borderless dense").classes("text-[11px] font-bold")
                            with ui.button(icon="account_circle").props("round unelevated dense").classes("bg-gradient-to-r from-indigo-600 to-purple-600 text-white shadow-md"):
                                with ui.menu().classes("rounded-xl shadow-xl border border-purple-200"):
                                    with ui.menu_item(on_click=show_profile).classes("hover:bg-purple-50 font-semibold"):
                                        with ui.row().classes("items-center gap-2"): ui.icon("person", color="purple"); ui.label("Profile")
                                    ui.separator()
                                    with ui.menu_item(on_click=show_filter).classes("hover:bg-purple-50 font-semibold"):
                                        with ui.row().classes("items-center gap-2"): ui.icon("filter_alt", color="indigo"); ui.label("Filter")
                        
                        with ui.row().classes("w-full justify-center mb-1 mt-0.5"):
                            title_input = ui.input(value=user.default_report_title or "Veraval site").props("borderless dense input-class='text-center font-extrabold text-[13px] text-slate-900'").classes("w-full px-2 py-0.5 rounded-full bg-gradient-to-r from-cyan-200 via-purple-200 to-fuchsia-300 shadow-md border-2 border-purple-300")
                            def save_title_persist():
                                try:
                                    new_title = (title_input.value or "").strip()
                                    if not new_title:
                                        return
                                    if new_title == user.default_report_title:
                                        return
                                    user.default_report_title = new_title
                                    user.save(update_fields=['default_report_title'])
                                    CACHE["users"][user.email] = user
                                    state["user"] = user
                                    ui.notify(f"✅ Title Saved", type="positive", position="top", timeout=2000)
                                except Exception as ex:
                                    print(f"Title save fail: {ex}")
                            title_input.on("blur", lambda _: save_title_persist())
                            title_input.on("keydown.enter", lambda _: save_title_persist())
                        def get_areas():
                            if user.id in CACHE["areas"]:
                                return CACHE["areas"][user.id]
                            areas = list(SavedArea.objects.filter(user=user).order_by("-id").values_list("area_name", flat=True)[:100])
                            CACHE["areas"][user.id] = areas
                            return areas
                        def get_labours():
                            if "labours" not in CACHE:
                                CACHE["labours"] = {}
                            if user.id in CACHE["labours"]:
                                return CACHE["labours"][user.id]
                            if HAS_LABOUR_MODEL:
                                try:
                                    labours = list(SavedLabour.objects.filter(user=user).order_by("-id").values_list("labour_name", flat=True)[:100])
                                except:
                                    labours = []
                            else:
                                labours = []
                            CACHE["labours"][user.id] = labours
                            return labours
                        saved_areas = get_areas()
                        saved_labours = get_labours()
                        def get_default_area():
                            try:
                                stored = app.storage.user.get("default_area_name", "")
                                if stored:
                                    return stored
                                if hasattr(user, 'default_area_name') and user.default_area_name:
                                    return user.default_area_name
                                last = DailyReport.objects.filter(user=user).order_by("-id").first()
                                if last and last.area_name:
                                    return last.area_name
                            except:
                                pass
                            return ""
                        def get_default_labour():
                            try:
                                stored = app.storage.user.get("default_labour_name", "")
                                if stored:
                                    return stored
                                if hasattr(user, 'default_labour_name') and user.default_labour_name:
                                    return user.default_labour_name
                                last = DailyReport.objects.filter(user=user).order_by("-id").first()
                                if last and last.labour_name:
                                    return last.labour_name
                            except:
                                pass
                            return ""
                        def save_default_area():
                            try:
                                val = (area_input.value or "").strip()
                                if not val:
                                    return
                                app.storage.user["default_area_name"] = val
                                if val != getattr(user, 'default_area_name', ''):
                                    try:
                                        user.default_area_name = val
                                        user.save(update_fields=['default_area_name'])
                                        CACHE["users"][user.email] = user
                                    except:
                                        pass
                            except Exception as e:
                                print(f"Area save fail: {e}")
                        def save_default_labour():
                            try:
                                val = (labour_input.value or "").strip()
                                if not val:
                                    return
                                app.storage.user["default_labour_name"] = val
                                if val != getattr(user, 'default_labour_name', ''):
                                    try:
                                        user.default_labour_name = val
                                        user.save(update_fields=['default_labour_name'])
                                        CACHE["users"][user.email] = user
                                    except:
                                        pass
                            except Exception as e:
                                print(f"Labour save fail: {e}")
                        with ui.row().classes("w-full mb-1 gap-2"):
                            with ui.column().classes("flex-1 gap-0.5"):
                                ui.label("Enter Area *").classes("text-[12px] font-extrabold text-green-700 ml-1")
                                area_input = ui.input(placeholder="Type area...", value=get_default_area()).props("outlined rounded dense color=green input-class='text-[13px]'").classes("editable-area w-full bg-white font-bold text-[13px] shadow-sm")
                                area_input.on("blur", lambda _: save_default_area())
                                area_input.on("keydown.enter", lambda _: save_default_area())
                            with ui.column().classes("flex-1 gap-0.5"):
                                ui.label("Enter Labour Name").classes("text-[12px] font-extrabold text-blue-700 ml-1")
                                labour_input = ui.input(placeholder="Type labour...", value=get_default_labour()).props("outlined rounded dense color=blue input-class='text-[13px]'").classes("editable-area w-full bg-white font-bold text-[13px] shadow-sm")
                                labour_input.on("blur", lambda _: save_default_labour())
                                labour_input.on("keydown.enter", lambda _: save_default_labour())
                        pipe_mtr_state = {"63": 6.0, "90": 6.0, "110": 6.0, "150": 5.5}
                        
                        with ui.row().classes("w-full justify-center items-center gap-2 mb-2 mt-1"):
                            pipe_logic_btn = ui.button("PIPE MTR LOGIC", icon="info").props("dense rounded outline color=purple").classes("text-[10px] font-bold px-2 py-1 border-purple-300")
                            with ui.row().classes("items-center gap-1"):
                                ui.icon("bolt", color="green", size="1.1rem"); ui.label("PipeLine Progress").classes("text-[14px] font-extrabold text-slate-800 text-center")
                        
                        with ui.dialog() as pipe_logic_dialog, ui.card().classes("rounded-2xl p-0 w-full max-w-sm shadow-2xl overflow-hidden"):
                            with ui.column().classes("w-full p-0 gap-0"):
                                with ui.row().classes("w-full bg-gradient-to-r from-purple-600 to-indigo-600 p-3 items-center justify-between text-white"):
                                    ui.label("📏 PIPE MTR LOGIC").classes("font-extrabold text-[13px] text-white")
                                    ui.button(icon="close", on_click=pipe_logic_dialog.close).props("flat round dense color=white").classes("text-white")
                                with ui.column().classes("w-full p-3 gap-2 bg-white"):
                                    ui.label("Per Pipe MTR Details - View Only").classes("text-[11px] font-bold text-purple-700 text-center w-full bg-purple-50 px-2 py-1 rounded-full")
                                    with ui.column().classes("w-full rounded-xl overflow-hidden border-2 border-indigo-900 shadow-md mt-1"):
                                        with ui.grid(columns=4).classes("w-full bg-gradient-to-r from-emerald-500 to-teal-500 text-white font-extrabold text-center"):
                                            ui.label("63MM").classes("py-2 text-[11px]"); ui.label("90MM").classes("py-2 text-[11px] border-x border-white/30"); ui.label("110MM").classes("py-2 text-[11px] border-r border-white/30"); ui.label("150MM").classes("py-2 text-[11px]")
                                        with ui.grid(columns=4).classes("w-full bg-slate-100 text-center border-y border-indigo-900"):
                                            ui.label("per pipe MTR").classes("py-1 text-[9px] font-bold text-slate-600"); ui.label("per pipe MTR").classes("py-1 text-[9px] font-bold text-slate-600 border-x border-gray-300"); ui.label("per pipe MTR").classes("py-1 text-[9px] font-bold text-slate-600 border-r border-gray-300"); ui.label("per pipe MTR").classes("py-1 text-[9px] font-bold text-slate-600")
                                        with ui.grid(columns=4).classes("w-full bg-white text-center"):
                                            with ui.column().classes("w-full p-1"):
                                                ui.input(value="6MTR").props("outlined dense readonly input-class='text-center font-extrabold text-[13px]'").classes("w-full bg-green-50")
                                            with ui.column().classes("w-full p-1 border-x border-gray-200"):
                                                ui.input(value="6MTR").props("outlined dense readonly input-class='text-center font-extrabold text-[13px]'").classes("w-full bg-green-50")
                                            with ui.column().classes("w-full p-1 border-r border-gray-200"):
                                                ui.input(value="6MTR").props("outlined dense readonly input-class='text-center font-extrabold text-[13px]'").classes("w-full bg-green-50")
                                            with ui.column().classes("w-full p-1"):
                                                ui.input(value="5.5MTR").props("outlined dense readonly input-class='text-center font-extrabold text-[13px]'").classes("w-full bg-purple-50")
                                    with ui.column().classes("w-full bg-amber-50 rounded-xl p-2 border border-amber-200 mt-2"):
                                        ui.label("Logic: Total MTR = Count × Per Pipe MTR + Extra MTR").classes("text-[10px] font-bold text-amber-800 text-center w-full")
                                        ui.label("Example: 63MM Count 5 × 6MTR = 30MTR").classes("text-[9px] font-bold text-slate-600 text-center w-full mt-1")
                                    ui.button("Close", icon="close", on_click=pipe_logic_dialog.close).props("rounded").classes("w-full mt-2 bg-slate-100 text-slate-700 font-bold text-[12px]")
                        pipe_logic_btn.on_click(pipe_logic_dialog.open)

                        extra_state = {"63": 0.0, "90": 0.0, "110": 0.0, "150": 0.0}
                        
                        with ui.column().classes("w-full items-center justify-center py-10 gap-3 mt-1 bg-slate-50 rounded-2xl border-2 border-dashed border-green-200"):
                            ui.icon("assignment_add", size="2.5rem", color="green")
                            ui.label("No active report - Start new").classes("text-[11px] font-bold text-slate-500")
                            new_report_btn = ui.button("+New Report", icon="add").props("rounded").classes("w-3/5 py-3 bg-gradient-to-r from-emerald-500 to-teal-600 text-white font-extrabold text-[14px] shadow-xl")
                        
                        with ui.dialog() as new_report_dialog, ui.card().classes("rounded-3xl p-0 w-full max-w-md shadow-2xl overflow-hidden"):
                            with ui.column().classes("w-full p-0 gap-0"):
                                with ui.row().classes("w-full bg-gradient-to-r from-indigo-600 via-purple-600 to-emerald-600 p-3 items-center justify-between text-white"):
                                    ui.label("📝 New Report").classes("font-extrabold text-[14px] text-white")
                                    ui.button(icon="close", on_click=new_report_dialog.close).props("flat round dense color=white").classes("text-white")
                                with ui.row().classes("w-full justify-around items-center bg-slate-50 p-3 border-b-2 border-indigo-100"):
                                    nav_pipe_btn = ui.button(icon="pie_chart").props("round dense").classes("bg-blue-600 text-white shadow-lg w-12 h-12")
                                    nav_conn_btn = ui.button(icon="link").props("round dense").classes("bg-slate-200 text-slate-600 w-12 h-12")
                                    nav_save_btn = ui.button(icon="save").props("round dense").classes("bg-slate-200 text-slate-600 w-12 h-12")
                                
                                pipe_section = ui.column().classes("w-full p-3 gap-0")
                                conn_section = ui.column().classes("w-full p-4 gap-3 hidden")
                                save_section = ui.column().classes("w-full p-4 gap-3 hidden")
                                
                                def show_section(name):
                                    pipe_section.classes(add="hidden"); conn_section.classes(add="hidden"); save_section.classes(add="hidden")
                                    nav_pipe_btn.classes(replace="bg-blue-600 text-white shadow-lg", add="bg-slate-200 text-slate-600")
                                    nav_conn_btn.classes(replace="bg-blue-600 text-white shadow-lg", add="bg-slate-200 text-slate-600")
                                    nav_save_btn.classes(replace="bg-green-600 text-white shadow-lg", add="bg-slate-200 text-slate-600")
                                    nav_pipe_btn.classes(replace="bg-green-600 text-white shadow-lg", add="bg-slate-200 text-slate-600")
                                    nav_conn_btn.classes(replace="bg-green-600 text-white shadow-lg", add="bg-slate-200 text-slate-600")
                                    nav_save_btn.classes(replace="bg-blue-600 text-white shadow-lg", add="bg-slate-200 text-slate-600")
                                    if name == "pipe":
                                        pipe_section.classes(remove="hidden")
                                        nav_pipe_btn.classes(replace="bg-slate-200 text-slate-600", add="bg-blue-600 text-white shadow-lg")
                                    elif name == "conn":
                                        conn_section.classes(remove="hidden")
                                        nav_conn_btn.classes(replace="bg-slate-200 text-slate-600", add="bg-blue-600 text-white shadow-lg")
                                    elif name == "save":
                                        save_section.classes(remove="hidden")
                                        nav_save_btn.classes(replace="bg-slate-200 text-slate-600", add="bg-green-600 text-white shadow-lg")
                                
                                nav_pipe_btn.on_click(lambda: show_section("pipe"))
                                nav_conn_btn.on_click(lambda: show_section("conn"))
                                nav_save_btn.on_click(lambda: show_section("save"))
                                
                                with pipe_section:
                                    with ui.column().classes("w-full rounded-2xl overflow-hidden shadow-lg border-2 border-indigo-900 gap-0"):
                                        with ui.grid(columns=4).classes("w-full bg-gradient-to-r from-emerald-500 via-green-500 to-teal-500 text-white font-extrabold text-center"):
                                            ui.label("63MM PVC").classes("py-2 text-[10px]"); ui.label("90MM PVC").classes("py-2 text-[10px] border-x border-white/30"); ui.label("110MM PVC").classes("py-2 text-[10px] border-r border-white/30"); ui.label("150MM DI").classes("py-2 text-[10px]")
                                        with ui.grid(columns=4).classes("w-full bg-white text-center items-center"):
                                            with ui.column().classes("p-1 items-center w-full"): c63 = ui.input(placeholder="Count").props("type=number outlined dense color=green input-class='text-center font-bold text-[13px]' step=0.1").classes("w-full h-10")
                                            with ui.column().classes("p-1 items-center border-x-2 border-indigo-900 w-full"): c90 = ui.input(placeholder="Count").props("type=number outlined dense color=green input-class='text-center font-bold text-[13px]' step=0.1").classes("w-full h-10")
                                            with ui.column().classes("p-1 items-center border-r-2 border-indigo-900 w-full"): c110 = ui.input(placeholder="Count").props("type=number outlined dense color=green input-class='text-center font-bold text-[13px]' step=0.1").classes("w-full h-10")
                                            with ui.column().classes("p-1 items-center w-full"): c150 = ui.input(placeholder="Count").props("type=number outlined dense color=green input-class='text-center font-bold text-[13px]' step=0.1").classes("w-full h-10")
                                        with ui.grid(columns=4).classes("w-full bg-white text-center items-center border-t border-indigo-900"):
                                            with ui.column().classes("p-0.5 items-center w-full"):
                                                add_63_btn = ui.button("+ADD MTR").props("flat dense").classes("text-[9px] bg-red-50 text-red-600 font-bold border border-red-200 px-1 py-0.5 rounded-full")
                                            with ui.column().classes("p-0.5 items-center border-x-2 border-indigo-900 w-full"):
                                                add_90_btn = ui.button("+ADD MTR").props("flat dense").classes("text-[9px] bg-red-50 text-red-600 font-bold border border-red-200 px-1 py-0.5 rounded-full")
                                            with ui.column().classes("p-0.5 items-center border-r-2 border-indigo-900 w-full"):
                                                add_110_btn = ui.button("+ADD MTR").props("flat dense").classes("text-[9px] bg-red-50 text-red-600 font-bold border border-red-200 px-1 py-0.5 rounded-full")
                                            with ui.column().classes("p-0.5 items-center w-full"):
                                                add_150_btn = ui.button("+ADD MTR").props("flat dense").classes("text-[9px] bg-red-50 text-red-600 font-bold border border-red-200 px-1 py-0.5 rounded-full")
                                        with ui.grid(columns=4).classes("w-full bg-amber-50 text-center border-b-2 border-indigo-900 items-center"):
                                            m63_lbl = ui.label("0 MTR").classes("py-2 font-extrabold text-amber-800 text-[11px]")
                                            m90_lbl = ui.label("0 MTR").classes("py-2 font-extrabold text-amber-800 text-[11px] border-x-2 border-indigo-900")
                                            m110_lbl = ui.label("0 MTR").classes("py-2 font-extrabold text-amber-800 text-[11px] border-r-2 border-indigo-900")
                                            m150_lbl = ui.label("0 MTR").classes("py-2 font-extrabold text-amber-800 text-[11px]")
                                        with ui.grid(columns=4).classes("w-full bg-orange-50 text-center border-b border-indigo-900 items-center"):
                                            e63_lbl = ui.label("").classes("py-1 font-bold text-orange-600 text-[10px]")
                                            e90_lbl = ui.label("").classes("py-1 font-bold text-orange-600 text-[10px] border-x-2 border-indigo-900")
                                            e110_lbl = ui.label("").classes("py-1 font-bold text-orange-600 text-[10px] border-r-2 border-indigo-900")
                                            e150_lbl = ui.label("").classes("py-1 font-bold text-orange-600 text-[10px]")
                                        with ui.column().classes("w-full gap-0"):
                                            with ui.grid(columns=1).classes("w-full bg-gradient-to-r from-slate-900 via-indigo-950 to-slate-900 text-center"):
                                                pvc_total_lbl = ui.label("Total PVC Pipes : 0 Quantity").classes("py-2 font-bold text-green-300 text-[12px] border-b border-white/10")
                                            with ui.grid(columns=1).classes("w-full bg-gradient-to-r from-slate-800 via-slate-900 to-slate-800 text-center"):
                                                di_total_lbl = ui.label("Total DI Pipes : 0 Quantity").classes("py-2 font-bold text-cyan-300 text-[12px]")
                                            with ui.grid(columns=1).classes("w-full bg-gradient-to-r from-amber-900 to-yellow-900 text-center"):
                                                mtr_total_lbl = ui.label("Total MTR: 0 MTR").classes("py-2.5 font-bold text-yellow-200 text-[12px]")
                                    with ui.row().classes("w-full justify-end mt-2"):
                                        ui.button("Next: Connection", icon="arrow_forward", on_click=lambda: show_section("conn")).props("rounded dense").classes("bg-blue-600 text-white text-[11px] font-bold")
                                with conn_section:
                                    ui.label("Enter Connection").classes("text-[13px] font-extrabold text-orange-700 w-full text-center bg-orange-50 px-3 py-2 rounded-full border border-orange-200")
                                    # State for connections list for this report
                                    conn_list_state = {"items": []}
                                    conn_list_container = ui.column().classes("w-full gap-1 mt-2")
                                    conn_total_lbl = ui.label("Total Connections Today: 0").classes("text-[11px] font-extrabold text-green-700 bg-green-50 px-2 py-1 rounded-full text-center w-full border border-green-200 mt-1")
                                    
                                    def refresh_conn_list():
                                        conn_list_container.clear()
                                        total_sum = 0
                                        try:
                                            for it in conn_list_state["items"]:
                                                try:
                                                    total_sum += float(str(it.get('conn','0') or 0).strip() or 0)
                                                except:
                                                    pass
                                        except:
                                            total_sum = 0
                                        with conn_list_container:
                                            if not conn_list_state["items"]:
                                                ui.label("No connections added yet - Click +Add").classes("text-[10px] text-slate-400 text-center w-full py-2")
                                            else:
                                                for idx, item in enumerate(conn_list_state["items"], 1):
                                                    with ui.row().classes("w-full bg-white rounded-xl p-2 border border-orange-100 shadow-sm items-center"):
                                                        ui.label(f"{idx}. {item['conn']},{item['name']},{item['mobile']}").classes("text-[11px] font-bold text-slate-800 flex-1")
                                        # Show sum, not count
                                        if total_sum == int(total_sum):
                                            conn_total_lbl.set_text(f"Total Connections Today: {int(total_sum)}")
                                        else:
                                            conn_total_lbl.set_text(f"Total Connections Today: {total_sum}")
                                        try:
                                            if total_sum == int(total_sum):
                                                live_conn_lbl.set_text(f"Connection: {int(total_sum)}")
                                                live_total_lbl.set_text(f"Total MTR: - | Conn: {int(total_sum)}")
                                            else:
                                                live_conn_lbl.set_text(f"Connection: {total_sum}")
                                                live_total_lbl.set_text(f"Total MTR: - | Conn: {total_sum}")
                                        except:
                                            pass
                                    
                                    with ui.dialog() as add_conn_dialog, ui.card().classes("rounded-2xl p-4 w-full max-w-sm bg-white shadow-2xl"):
                                        ui.label("Add Connection").classes("text- font-extrabold text-orange-700 w-full text-center bg-orange-50 px-3 py-2 rounded-full border border-orange-200")
                                        conn_no_input = ui.input("Connection", placeholder="Ex: 56").props("outlined dense").classes("w-full mt-2 font-bold")
                                        conn_name_input = ui.input("Enter Name", placeholder="Ex: Mohanlal").props("outlined dense").classes("w-full mt-1 font-bold")
                                        conn_mobile_input = ui.input("Mobile No", placeholder="Ex: 9988779988").props("outlined dense type=tel").classes("w-full mt-1 font-bold")
                                        with ui.row().classes("w-full justify-between gap-2 mt-4"):
                                            ui.button("Done", icon="check", on_click=add_conn_dialog.close).props("flat rounded").classes("flex-1 bg-slate-100 text-slate-700 font-bold")
                                            def do_add_conn():
                                                cno = (conn_no_input.value or "").strip()
                                                cname = (conn_name_input.value or "").strip()
                                                cmob = (conn_mobile_input.value or "").strip()
                                                if not cno:
                                                    ui.notify("Connection No required!", type="warning", position="top")
                                                    return
                                                conn_list_state["items"].append({"conn": cno, "name": cname, "mobile": cmob})
                                                # AUTO CLEAR - Main fix
                                                conn_no_input.value = ""
                                                conn_name_input.value = ""
                                                conn_mobile_input.value = ""
                                                try:
                                                    conn_no_input.update()
                                                    conn_name_input.update()
                                                    conn_mobile_input.update()
                                                except:
                                                    pass
                                                refresh_conn_list()
                                                ui.notify(f"✅ Added: {cno} | Total: {len(conn_list_state['items'])}", type="positive", position="top", timeout=1200)
                                                # Dialog khullo rakho - bijo entry mate
                                                try:
                                                    conn_no_input.run_method('focus')
                                                except:
                                                    pass
                                            ui.button("Add", icon="add", on_click=do_add_conn).props("rounded").classes("flex-1 bg-gradient-to-r from-orange-500 to-red-500 text-white font-bold")
                                    
                                    with ui.row().classes("w-full justify-center mt-3"):
                                        ui.button("+Add Connection", icon="add", on_click=add_conn_dialog.open).props("rounded").classes("w-full py-2.5 bg-gradient-to-r from-orange-500 to-amber-600 text-white font-extrabold text-[12px] shadow-lg")
                                    
                                    refresh_conn_list()
                                    
                                    with ui.row().classes("w-full justify-between gap-2 mt-4"):
                                        ui.button("Back to Pipes", icon="arrow_back", on_click=lambda: show_section("pipe")).props("flat rounded dense").classes("text-[11px] bg-slate-100")
                                        ui.button("Next: Save", icon="arrow_forward", on_click=lambda: show_section("save")).props("rounded dense").classes("text-[11px] bg-blue-600 text-white font-bold")
                                with save_section:
                                    ui.label("Save Report").classes("text-[13px] font-extrabold text-green-700 w-full text-center bg-green-50 px-3 py-2 rounded-full border border-green-200")
                                    with ui.column().classes("w-full bg-slate-50 rounded-xl p-3 gap-1 mt-2 border"):
                                        live_area_lbl = ui.label("Area: -").classes("text-[11px] font-bold text-slate-700")
                                        live_labour_lbl = ui.label("Labour: -").classes("text-[11px] font-bold text-slate-700")
                                        live_conn_lbl = ui.label("Connection: -").classes("text-[11px] font-bold text-orange-700")
                                        live_total_lbl = ui.label("Total MTR: 0 MTR").classes("text-[12px] font-extrabold text-green-700 mt-1")
                                    save_btn = ui.button("⚡ Save", icon="save").props("rounded").classes("w-full mt-3 py-3 bg-gradient-to-r from-blue-600 to-indigo-600 text-white font-extrabold text-[13px] shadow-lg")
                                    with ui.row().classes("w-full justify-between gap-2 mt-2"):
                                        ui.button("Back to Connection", icon="arrow_back", on_click=lambda: show_section("conn")).props("flat rounded dense").classes("text-[11px] bg-slate-100")
                                        ui.button("Back to Pipes", icon="pie_chart", on_click=lambda: show_section("pipe")).props("flat rounded dense").classes("text-[11px] bg-slate-100")
                        
                        new_report_btn.on_click(new_report_dialog.open)
                        
                        with ui.dialog() as extra_63_dialog, ui.card().classes("rounded-2xl p-4 w-full max-w-xs bg-white shadow-2xl"):
                            ui.label("Enter Extra Meter for 63MM Pipe").classes("text-sm font-extrabold text-slate-800 text-center w-full")
                            extra_63_input = ui.input(placeholder="Ex: 5", value="").props("type=number outlined dense autofocus").classes("w-full font-bold text-center")
                            with ui.row().classes("w-full justify-between gap-2 mt-3"):
                                ui.button("Cancel", on_click=extra_63_dialog.close).props("flat rounded").classes("flex-1 bg-slate-100")
                                def set_extra_63():
                                    try:
                                        v = float(extra_63_input.value or 0)
                                        extra_state["63"] = v
                                        extra_63_dialog.close()
                                        update_live_preview()
                                        ui.notify(f"Extra 63MM: {v} MTR added", type="positive", timeout=2000)
                                    except:
                                        ui.notify("Enter valid number", type="warning")
                                ui.button("Add", icon="check", on_click=set_extra_63).props("rounded").classes("flex-1 bg-red-500 text-white font-bold")
                        
                        with ui.dialog() as extra_90_dialog, ui.card().classes("rounded-2xl p-4 w-full max-w-xs bg-white shadow-2xl"):
                            ui.label("Enter Extra Meter for 90MM Pipe").classes("text-sm font-extrabold text-slate-800 text-center w-full")
                            extra_90_input = ui.input(placeholder="Ex: 5", value="").props("type=number outlined dense autofocus").classes("w-full font-bold text-center")
                            with ui.row().classes("w-full justify-between gap-2 mt-3"):
                                ui.button("Cancel", on_click=extra_90_dialog.close).props("flat rounded").classes("flex-1 bg-slate-100")
                                def set_extra_90():
                                    try:
                                        v = float(extra_90_input.value or 0)
                                        extra_state["90"] = v
                                        extra_90_dialog.close()
                                        update_live_preview()
                                        ui.notify(f"Extra 90MM: {v} MTR added", type="positive", timeout=2000)
                                    except:
                                        ui.notify("Enter valid number", type="warning")
                                ui.button("Add", icon="check", on_click=set_extra_90).props("rounded").classes("flex-1 bg-red-500 text-white font-bold")
                        
                        with ui.dialog() as extra_110_dialog, ui.card().classes("rounded-2xl p-4 w-full max-w-xs bg-white shadow-2xl"):
                            ui.label("Enter Extra Meter for 110MM Pipe").classes("text-sm font-extrabold text-slate-800 text-center w-full")
                            extra_110_input = ui.input(placeholder="Ex: 5", value="").props("type=number outlined dense autofocus").classes("w-full font-bold text-center")
                            with ui.row().classes("w-full justify-between gap-2 mt-3"):
                                ui.button("Cancel", on_click=extra_110_dialog.close).props("flat rounded").classes("flex-1 bg-slate-100")
                                def set_extra_110():
                                    try:
                                        v = float(extra_110_input.value or 0)
                                        extra_state["110"] = v
                                        extra_110_dialog.close()
                                        update_live_preview()
                                        ui.notify(f"Extra 110MM: {v} MTR added", type="positive", timeout=2000)
                                    except:
                                        ui.notify("Enter valid number", type="warning")
                                ui.button("Add", icon="check", on_click=set_extra_110).props("rounded").classes("flex-1 bg-red-500 text-white font-bold")
                        
                        with ui.dialog() as extra_150_dialog, ui.card().classes("rounded-2xl p-4 w-full max-w-xs bg-white shadow-2xl"):
                            ui.label("Enter Extra Meter for 150MM DI Pipe").classes("text-sm font-extrabold text-slate-800 text-center w-full")
                            extra_150_input = ui.input(placeholder="Ex: 5", value="").props("type=number outlined dense autofocus").classes("w-full font-bold text-center")
                            with ui.row().classes("w-full justify-between gap-2 mt-3"):
                                ui.button("Cancel", on_click=extra_150_dialog.close).props("flat rounded").classes("flex-1 bg-slate-100")
                                def set_extra_150():
                                    try:
                                        v = float(extra_150_input.value or 0)
                                        extra_state["150"] = v
                                        extra_150_dialog.close()
                                        update_live_preview()
                                        ui.notify(f"Extra 150MM: {v} MTR added", type="positive", timeout=2000)
                                    except:
                                        ui.notify("Enter valid number", type="warning")
                                ui.button("Add", icon="check", on_click=set_extra_150).props("rounded").classes("flex-1 bg-red-500 text-white font-bold")
                        
                        add_63_btn.on_click(extra_63_dialog.open)
                        add_90_btn.on_click(extra_90_dialog.open)
                        add_110_btn.on_click(extra_110_dialog.open)
                        add_150_btn.on_click(extra_150_dialog.open)
                        def parse_qty(val):
                            try:
                                if val in (None, ""):
                                    return 0
                                s = str(val).strip()
                                if s.startswith("-"):
                                    return 0
                                v = float(s)
                                if v < 0:
                                    return 0
                                return v
                            except:
                                return 0
                        def update_live_preview():
                            def fast_parse(v):
                                try:
                                    if not v: return 0
                                    s=str(v).strip()
                                    if s.startswith("-"): return 0
                                    return float(s) if s else 0
                                except: return 0
                            q63 = fast_parse(c63.value); q90 = fast_parse(c90.value); q110 = fast_parse(c110.value); q150 = fast_parse(c150.value)
                            ex63 = extra_state.get("63",0); ex90 = extra_state.get("90",0); ex110 = extra_state.get("110",0); ex150 = extra_state.get("150",0)
                            pm63 = pipe_mtr_state.get("63",6.0); pm90 = pipe_mtr_state.get("90",6.0); pm110 = pipe_mtr_state.get("110",6.0); pm150 = pipe_mtr_state.get("150",5.5)
                            m63 = q63*pm63 + ex63; m90 = q90*pm90 + ex90; m110 = q110*pm110 + ex110; m150 = q150*pm150 + ex150
                            total_mtr = m63+m90+m110+m150
                            total_extra = ex63+ex90+ex110+ex150
                            pvc_total_lbl.set_text(f"Total PVC Pipes : {q63+q90+q110} Quantity")
                            di_total_lbl.set_text(f"Total DI Pipes : {q150} Quantity")
                            if total_extra>0:
                                mtr_total_lbl.set_text(f"Total MTR: {total_mtr} MTR (Pipe:{total_mtr-total_extra} + Extra:{total_extra})")
                            else:
                                mtr_total_lbl.set_text(f"Total MTR: {total_mtr} MTR")
                            m63_lbl.set_text(f"{m63:.1f} MTR" if m63!=int(m63) else f"{int(m63)} MTR")
                            m90_lbl.set_text(f"{m90:.1f} MTR" if m90!=int(m90) else f"{int(m90)} MTR")
                            m110_lbl.set_text(f"{m110:.1f} MTR" if m110!=int(m110) else f"{int(m110)} MTR")
                            m150_lbl.set_text(f"{m150:.1f} MTR" if m150!=int(m150) else f"{int(m150)} MTR")
                            e63_lbl.set_text(f"+{ex63} Extra" if ex63>0 else "")
                            e90_lbl.set_text(f"+{ex90} Extra" if ex90>0 else "")
                            e110_lbl.set_text(f"+{ex110} Extra" if ex110>0 else "")
                            e150_lbl.set_text(f"+{ex150} Extra" if ex150>0 else "")
                            add_63_btn.set_text(f"+{ex63} MTR" if ex63>0 else "+ADD MTR")
                            add_90_btn.set_text(f"+{ex90} MTR" if ex90>0 else "+ADD MTR")
                            add_110_btn.set_text(f"+{ex110} MTR" if ex110>0 else "+ADD MTR")
                            add_150_btn.set_text(f"+{ex150} MTR" if ex150>0 else "+ADD MTR")
                            try:
                                live_area_lbl.set_text(f"Area: {(area_input.value or '').strip() or '-'}")
                                live_labour_lbl.set_text(f"Labour: {(labour_input.value or '').strip() or '-'}")
                                live_conn_lbl.set_text(f"Connection: {(connection_input.value or '').strip() or '-'}")
                                live_total_lbl.set_text(f"Total MTR: {total_mtr} MTR")
                            except:
                                pass
                        
                        c63.on_value_change(lambda _: update_live_preview())
                        c90.on_value_change(lambda _: update_live_preview())
                        c110.on_value_change(lambda _: update_live_preview())
                        c150.on_value_change(lambda _: update_live_preview())
                        c63.on("input", lambda _: update_live_preview())
                        c90.on("input", lambda _: update_live_preview())
                        c110.on("input", lambda _: update_live_preview())
                        c150.on("input", lambda _: update_live_preview())
                        def save_daily_report():
                            q63 = parse_qty(c63.value); q90 = parse_qty(c90.value); q110 = parse_qty(c110.value); q150 = parse_qty(c150.value)
                            ex63 = extra_state.get("63",0); ex90 = extra_state.get("90",0); ex110 = extra_state.get("110",0); ex150 = extra_state.get("150",0)
                            pm63 = pipe_mtr_state.get("63",6.0); pm90 = pipe_mtr_state.get("90",6.0); pm110 = pipe_mtr_state.get("110",6.0); pm150 = pipe_mtr_state.get("150",5.5)
                            total_mtr_calc = (q63*pm63+ex63)+(q90*pm90+ex90)+(q110*pm110+ex110)+(q150*pm150+ex150)
                            try:
                                selected_date = datetime.datetime.strptime((home_date_input.value or "").strip(), "%Y-%m-%d").date()
                            except Exception:
                                selected_date = today_ist()
                            area_val = (area_input.value or "").strip()
                            labour_val = (labour_input.value or "").strip()
                            # New: connections list - sum of connection numbers
                            conn_items = []
                            try:
                                conn_items = list(conn_list_state.get("items", []))
                            except:
                                conn_items = []
                            conn_sum = 0
                            try:
                                for it in conn_items:
                                    try:
                                        conn_sum += float(str(it.get('conn','0') or 0).strip() or 0)
                                    except:
                                        pass
                            except:
                                conn_sum = 0
                            if conn_sum == int(conn_sum):
                                conn_val = str(int(conn_sum)) if conn_sum!=0 else ""
                            else:
                                conn_val = str(conn_sum) if conn_sum!=0 else ""
                            conn_detail_str = ""
                            try:
                                if conn_items:
                                    conn_detail_str = "; ".join([f"{it.get('conn','')},{it.get('name','')},{it.get('mobile','')}" for it in conn_items])
                            except:
                                conn_detail_str = ""
                            if not area_val: ui.notify("Please Enter Area!", type="warning", position="top"); return
                            if area_val not in (CACHE["areas"].get(user.id, [])):
                                SavedArea.objects.get_or_create(user=user, area_name=area_val)
                                CACHE["areas"].pop(user.id, None)
                            if labour_val:
                                if HAS_LABOUR_MODEL:
                                    try:
                                        SavedLabour.objects.get_or_create(user=user, labour_name=labour_val)
                                    except:
                                        pass
                                if "labours" in CACHE and user.id in CACHE["labours"]:
                                    CACHE["labours"].pop(user.id, None)
                            current_title = (title_input.value or "").strip()
                            if not current_title:
                                current_title = "Veraval site"
                            if current_title != user.default_report_title:
                                user.default_report_title = current_title
                                user.save(update_fields=['default_report_title'])
                                CACHE["users"][user.email] = user
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
                                            connection_no=str(it.get('conn','')).strip(),
                                            name=str(it.get('name','')).strip(),
                                            mobile=str(it.get('mobile','')).strip(),
                                            area_name=area_val
                                        )
                                except Exception as ce:
                                    print(f"ConnectionEntry save fail: {ce}")
                            
                            except Exception as ex:
                                print(f"Save with extra failed: {ex}")
                                try:
                                    if report_obj is None:
                                        report_obj = DailyReport.objects.create(user=user, report_title=current_title, report_date=selected_date, area_name=area_val, labour_name=labour_val, connection=conn_val, qty_63mm=q63, qty_90mm=q90, qty_110mm=q110, qty_150mm=q150, total_pvc=q63+q90+q110, total_di=q150, total_qty=q63+q90+q110+q150, total_mtr=total_mtr_calc, price_sum=float(total_mtr_calc))
                                        try:
                                            from models_app.models import ConnectionEntry
                                            for it in conn_items:
                                                ConnectionEntry.objects.create(user=user, report=report_obj, report_date=selected_date, connection_no=str(it.get('conn','')).strip(), name=str(it.get('name','')).strip(), mobile=str(it.get('mobile','')).strip(), area_name=area_val)
                                        except Exception as ce2:
                                            print(f"Conn save fail2: {ce2}")
                                except Exception as ex2:
                                    if report_obj is None:
                                        report_obj = DailyReport.objects.create(user=user, report_title=current_title, report_date=selected_date, area_name=area_val, qty_63mm=q63, qty_90mm=q90, qty_110mm=q110, qty_150mm=q150, total_qty=q63+q90+q110+q150, price_sum=float(total_mtr_calc))
                                        try:
                                            from models_app.models import ConnectionEntry
                                            for it in conn_items:
                                                ConnectionEntry.objects.create(user=user, report=report_obj, report_date=selected_date, connection_no=str(it.get('conn','')).strip(), name=str(it.get('name','')).strip(), mobile=str(it.get('mobile','')).strip(), area_name=area_val)
                                        except:
                                            pass
                            c63.value = ""; c90.value = ""; c110.value = ""; c150.value = ""; 
                            try:
                                conn_list_state["items"] = []
                                refresh_conn_list()
                            except:
                                pass
                            extra_state["63"]=0; extra_state["90"]=0; extra_state["110"]=0; extra_state["150"]=0;
                            extra_63_input.value=""; extra_90_input.value=""; extra_110_input.value=""; extra_150_input.value="";
                            update_live_preview()
                            try:
                                app.storage.user["default_area_name"] = area_val
                                app.storage.user["default_labour_name"] = labour_val
                                user.default_area_name = area_val
                                user.default_labour_name = labour_val
                                user.save(update_fields=['default_area_name', 'default_labour_name'])
                                CACHE["users"][user.email] = user
                            except Exception as e:
                                print(f"Persist area/labour fail: {e}")
                                try:
                                    app.storage.user["default_area_name"] = area_val
                                    app.storage.user["default_labour_name"] = labour_val
                                except:
                                    pass
                            ui.notify(f"✅ Saved! Area:{area_val} MTR:{total_mtr_calc} (Extra:{ex63+ex90+ex110+ex150})", type="positive", position="top", timeout=3000)
                            try:
                                new_report_dialog.close()
                            except:
                                pass
                        save_btn.on_click(save_daily_report)

        def build_filter():

            filter_view.clear()
            user = state["user"]
            if not user:
                show_login()
                return
            try:
                fresh = AppUser.objects.get(id=user.id)
                user.default_report_title = fresh.default_report_title
                state["user"] = fresh
                user = fresh
            except:
                pass
            today = today_ist(); months = {1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun", 7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec"}; years = {y: str(y) for y in range(today.year - 5, today.year + 2)}
            with filter_view:
                with ui.column().classes("w-full max-w-md items-center gap-2"):
                    with ui.card().classes("w-full rounded-3xl shadow-2xl bg-white p-3 sm:p-5 border-2 border-green-200"):
                        with ui.row().classes("w-full justify-between items-center mb-2"):
                            ui.button("Back to Home", icon="arrow_back", on_click=show_home).props("flat rounded no-caps").classes("back-btn text-xs")
                        with ui.row().classes("w-full justify-center my-1.5"): 
                            ui.label(user.default_report_title).classes("w-full px-2 py-1.5 rounded-full bg-gradient-to-r from-cyan-200 via-purple-200 to-fuchsia-300 text-slate-900 font-extrabold text-center text-xs")
                        with ui.grid(columns=3).classes("w-full gap-1.5 my-2.5 bg-green-50 p-2 rounded-2xl border border-green-200"):
                            date_options = {"": "Select Date", **{str(d): f"{d:02d}" for d in range(1, 32)}}; day_select = ui.select(options=date_options, value="", label="Date").props("outlined rounded dense color=green").classes("w-full bg-white font-semibold text-xs")
                            month_select = ui.select(options=months, value=today.month, label="Month").props("outlined rounded dense color=green").classes("w-full bg-white font-semibold text-xs")
                            year_select = ui.select(options=years, value=today.year, label="Year").props("outlined rounded dense color=green").classes("w-full bg-white font-semibold text-xs")
                        table_container = ui.column().classes("w-full mt-1 gap-2")
                        def load_table_data():
                            table_container.clear()
                            sel_month = int(month_select.value); sel_year = int(year_select.value); sel_day = day_select.value
                            base_qs = DailyReport.objects.filter(user=user, report_date__year=sel_year, report_date__month=sel_month)
                            if not base_qs.exists():
                                with table_container:
                                    with ui.card().classes("w-full p-5 rounded-2xl bg-red-50 border-2 border-red-200 items-center text-center shadow-sm"):
                                        ui.icon("info", size="2.2rem", color="red"); ui.label("No Data").classes("text-sm font-extrabold text-red-700 mt-1")
                                return
                            if sel_day:
                                qs = base_qs.filter(report_date__day=int(sel_day)).order_by('-id')
                                period_text = f"Date: {int(sel_day):02d} {months[sel_month]} {sel_year}"
                                with table_container:
                                    if not qs.exists():
                                        with ui.card().classes("w-full p-5 rounded-2xl bg-red-50 border-2 border-red-200 items-center text-center shadow-sm"):
                                            ui.icon("info", size="2.2rem", color="red"); ui.label("No Data").classes("text-sm font-extrabold text-red-700 mt-1")
                                        return
                                    agg = qs.aggregate(t=Sum('total_qty')); grand_total = agg['t'] or 0
                                    day_total_conn = 0
                                    try:
                                        from models_app.models import ConnectionEntry
                                        if qs.exists():
                                            entries = ConnectionEntry.objects.filter(user=user, report_date=qs.first().report_date)
                                            for ce in entries:
                                                try:
                                                    day_total_conn += float(str(ce.connection_no or 0).strip() or 0)
                                                except:
                                                    pass
                                        if day_total_conn == 0:
                                            for r in qs:
                                                try:
                                                    cv = getattr(r, 'connection', '') or ''
                                                    if cv:
                                                        day_total_conn += float(str(cv).strip() or 0)
                                                except:
                                                    pass
                                    except Exception as e:
                                        print(f"Daily conn sum fail: {e}")
                                    with ui.row().classes("w-full justify-between items-center mb-2 px-1"):
                                        ui.badge(period_text, color="green").classes("text-xs font-bold px-2 py-1"); ui.badge(f"Total: {grand_total} Qty", color="green").classes("text-xs font-bold px-2 py-1"); ui.badge(f"Conn: {day_total_conn}", color="orange").classes("text-xs font-bold px-2 py-1")
                                    for report in qs[:50]:
                                        area_display = report.area_name or "No Area"
                                        with ui.card().classes("report-patti w-full rounded-2xl border-2 border-green-200 bg-gradient-to-r from-white to-green-50 p-0 overflow-hidden shadow-md"):
                                            with ui.column().classes("patti-click-area w-full p-3 pb-1").on("click", lambda r=report: show_filter_detail(r)):
                                                with ui.row().classes("w-full justify-between items-center"):
                                                    with ui.row().classes("items-center gap-2"): ui.icon("location_on", color="green", size="1.1rem"); ui.label(area_display).classes("font-extrabold text-[15px] text-indigo-900")
                                                    ui.badge(f"{report.report_date.strftime('%d-%m-%Y')}", color="grey").classes("text-[10px]")
                                                ui.label(report.report_title).classes("text-xs font-semibold text-slate-700 mt-1 w-full truncate")
                                                # Show connection if exists
                                                conn_disp = get_q(report, 'connection', '')
                                                if conn_disp:
                                                    ui.label(f"🔌 Connection: {conn_disp}").classes("text-[11px] font-extrabold text-orange-700 bg-orange-50 px-2 py-0.5 rounded-full mt-1")
                                                with ui.row().classes("w-full justify-between items-center mt-1"):
                                                    ui.label(f"63:{get_q(report,'qty_63mm')} | 90:{get_q(report,'qty_90mm')} | 110:{get_q(report,'qty_110mm')} | 150DI:{get_q(report,'qty_150mm')}").classes("text-[13px] font-bold text-slate-700")
                                                    ui.label(f"Total: {report.total_qty} Qty").classes("text-[14px] font-extrabold text-emerald-600")
                                            with ui.row().classes("w-full justify-end gap-2 px-3 pb-3 pt-1"):
                                                edit_btn = ui.button("Edit", icon="edit").props("dense rounded").classes("px-4 py-1.5 bg-yellow-400 text-black font-extrabold text-[13px] border-2 border-yellow-500 shadow-sm")
                                                del_btn = ui.button("Delete", icon="delete").props("dense rounded").classes("px-4 py-1.5 bg-red-600 text-yellow-200 font-extrabold text-[13px] border-2 border-red-700 shadow-md")
                                                with ui.dialog() as edit_dialog, ui.card().classes("rounded-2xl p-0 w-full max-w-md shadow-2xl max-h-[80vh] flex flex-col"):
                                                    with ui.column().classes("w-full p-0 gap-0 flex flex-col h-full"):
                                                        with ui.row().classes("w-full bg-gradient-to-r from-blue-500 to-blue-600 p-2.5 items-center justify-between text-white shrink-0"):
                                                            ui.label(f"✏ Edit - {area_display}").classes("font-extrabold text-[12px] text-white")
                                                            ui.button(icon="close", on_click=edit_dialog.close).props("flat round dense color=white size=sm").classes("text-white")
                                                        with ui.column().classes("w-full p-2.5 gap-1.5 bg-white overflow-y-auto flex-1"):
                                                            ui.label("Date").classes("text-[11px] font-bold text-slate-700")
                                                            e_date = ui.input(value=report.report_date.isoformat()).props("type=date outlined dense").classes("w-full")
                                                            ui.label("Area Name").classes("text-[11px] font-bold text-slate-700")
                                                            e_area = ui.input(value=report.area_name).props("outlined dense").classes("w-full font-bold")
                                                            ui.label("Labour Name").classes("text-[11px] font-bold text-slate-700")
                                                            e_labour = ui.input(value=get_q(report,'labour_name','')).props("outlined dense").classes("w-full font-bold")
                                                            ui.label("Connection (Sum)").classes("text-[11px] font-bold text-orange-700")
                                                            edit_conn_state = {"items": []}
                                                            try:
                                                                from models_app.models import ConnectionEntry
                                                                existing = list(ConnectionEntry.objects.filter(report=report).order_by('id'))
                                                                if not existing:
                                                                    existing = list(ConnectionEntry.objects.filter(user=report.user, report_date=report.report_date, area_name=report.area_name).order_by('id'))
                                                                for ce in existing:
                                                                    edit_conn_state["items"].append({"conn": ce.connection_no, "name": ce.name, "mobile": ce.mobile, "id": ce.id})
                                                            except Exception as ee:
                                                                print(f"Edit conn load fail: {ee}")
                                                            
                                                            edit_conn_total = ui.label("Total: 0").classes("text-[11px] font-bold text-green-700 bg-green-50 px-2 py-1 rounded-full text-center w-full border mt-1")
                                                            
                                                            del_target = {"idx": -1}
                                                            
                                                            # Delete confirmation dialog (single, reused)
                                                            with ui.dialog() as del_confirm_dialog, ui.card().classes("rounded-2xl p-0 w-full max-w-sm shadow-2xl overflow-hidden"):
                                                                with ui.column().classes("w-full p-0 gap-0"):
                                                                    with ui.row().classes("w-full bg-gradient-to-r from-red-500 to-orange-600 p-3 items-center text-white"):
                                                                        ui.icon("warning", size="1.2rem")
                                                                        ui.label("Confirm Delete").classes("font-extrabold text-[13px] text-white")
                                                                    with ui.column().classes("w-full p-4 gap-3 bg-white"):
                                                                        del_msg = ui.label("This data will be deleted").classes("text-[12px] font-bold text-slate-700 w-full text-center bg-red-50 p-3 rounded-xl border border-red-200")
                                                                        ui.label("Are you sure you want to delete this connection?").classes("text-[11px] text-slate-500 w-full text-center")
                                                                        with ui.row().classes("w-full justify-between gap-2 mt-1"):
                                                                            ui.button("Cancel", icon="close", on_click=del_confirm_dialog.close).props("flat rounded").classes("flex-1 bg-slate-100 text-slate-700 font-bold text-[12px]")
                                                                            def do_confirm_delete():
                                                                                idx = del_target["idx"]
                                                                                if 0 <= idx < len(edit_conn_state["items"]):
                                                                                    edit_conn_state["items"].pop(idx)
                                                                                    del_confirm_dialog.close()
                                                                                    refresh_edit_conn_list.refresh()
                                                                                    ui.notify("🗑️ Deleted! Now click main Edit to save.", type="positive", position="top", timeout=2000)
                                                                                else:
                                                                                    del_confirm_dialog.close()
                                                                            ui.button("Delete", icon="delete", on_click=do_confirm_delete).props("rounded").classes("flex-1 bg-gradient-to-r from-red-600 to-red-700 text-white font-bold text-[12px]")
                                                            
                                                            @ui.refreshable
                                                            def refresh_edit_conn_list():
                                                                total = 0
                                                                for it in edit_conn_state["items"]:
                                                                    try:
                                                                        c = str(it.get('conn','0') or 0).replace(',','').strip()
                                                                        if '+' in c:
                                                                            c = c.split('+')[0]
                                                                        total += float(c or 0)
                                                                    except:
                                                                        pass
                                                                if total == int(total):
                                                                    edit_conn_total.set_text(f"Total Connections Today: {int(total)}")
                                                                else:
                                                                    edit_conn_total.set_text(f"Total Connections Today: {total}")
                                                                
                                                                if not edit_conn_state["items"]:
                                                                    ui.label("No connections").classes("text-[10px] text-slate-400 text-center w-full py-2")
                                                                else:
                                                                    for idx, item in enumerate(edit_conn_state["items"]):
                                                                        with ui.row().classes("w-full bg-white rounded-lg p-2 border border-orange-100 items-center justify-between shadow-sm mb-1"):
                                                                            ui.label(f"{idx+1}. {item['conn']},{item['name']},{item['mobile']}").classes("text-[11px] font-bold text-slate-800 flex-1")
                                                                            with ui.row().classes("gap-0"):
                                                                                def make_edit(i=idx):
                                                                                    def edit_fn():
                                                                                        # Create fresh dialog with current item's data - ensures correct data shows
                                                                                        cur = edit_conn_state["items"][i]
                                                                                        print(f"EDIT click idx={i} data={cur}")
                                                                                        with ui.dialog() as dyn_edit_dialog, ui.card().classes("rounded-2xl p-4 w-full max-w-sm bg-white shadow-2xl"):
                                                                                            ui.label("Edit Connection").classes("text-[14px] font-extrabold text-blue-700 w-full text-center bg-blue-50 px-3 py-2 rounded-full border")
                                                                                            # Pre-fill with CURRENT row data
                                                                                            e_conn = ui.input("Connection", value=str(cur.get('conn',''))).props("outlined dense").classes("w-full mt-2 font-bold")
                                                                                            e_name = ui.input("Enter Name", value=str(cur.get('name',''))).props("outlined dense").classes("w-full mt-1 font-bold")
                                                                                            e_mob = ui.input("Mobile No", value=str(cur.get('mobile',''))).props("outlined dense").classes("w-full mt-1 font-bold")
                                                                                            with ui.row().classes("w-full justify-between gap-2 mt-4"):
                                                                                                ui.button("Cancel", on_click=dyn_edit_dialog.close).props("flat rounded").classes("flex-1 bg-slate-100 font-bold")
                                                                                                def do_update():
                                                                                                    cno = (e_conn.value or "").strip()
                                                                                                    if not cno:
                                                                                                        ui.notify("Connection required!", type="warning")
                                                                                                        return
                                                                                                    edit_conn_state["items"][i] = {"conn": cno, "name": (e_name.value or "").strip(), "mobile": (e_mob.value or "").strip(), "id": edit_conn_state["items"][i].get("id")}
                                                                                                    dyn_edit_dialog.close()
                                                                                                    refresh_edit_conn_list.refresh()
                                                                                                    ui.notify(f"✏️ Updated! Now click main Edit to save.", type="positive", position="top", timeout=1500)
                                                                                                ui.button("Update", icon="check", on_click=do_update).props("rounded").classes("flex-1 bg-blue-600 text-white font-bold")
                                                                                        dyn_edit_dialog.open()
                                                                                    return edit_fn
                                                                                def make_del(i=idx):
                                                                                    def del_fn():
                                                                                        del_target["idx"] = i
                                                                                        try:
                                                                                            p = edit_conn_state["items"][i]
                                                                                            del_msg.set_text(f"This data will be deleted: {p.get('conn','')},{p.get('name','')},{p.get('mobile','')}")
                                                                                        except:
                                                                                            del_msg.set_text("This data will be deleted")
                                                                                        del_confirm_dialog.open()
                                                                                    return del_fn
                                                                                ui.button(icon="edit", on_click=make_edit()).props("flat round dense color=blue size=sm").classes("text-blue-600")
                                                                                ui.button(icon="delete", on_click=make_del()).props("flat round dense color=red size=sm").classes("text-red-600")
                                                            
                                                            refresh_edit_conn_list()
                                                            
                                                            e_connection = ui.input(value=get_q(report,'connection','')).props("outlined dense color=orange").classes("w-full font-bold bg-orange-50 hidden")
                                                            # Keep old e_connection for backward compat but hidden
                                                            # Keep old e_connection for backward compat but hidden
                                                            e_connection = ui.input(value=get_q(report,'connection','')).props("outlined dense color=orange").classes("w-full font-bold bg-orange-50 hidden")
                                                            ui.label("Report Title").classes("text-[11px] font-bold text-slate-700")
                                                            e_title = ui.input(value=report.report_title).props("outlined dense").classes("w-full")
                                                            ui.label("PVC & DI Quantity").classes("text-[13px] font-extrabold text-green-700 mt-2")
                                                            with ui.grid(columns=4).classes("w-full gap-2"):
                                                                with ui.column().classes("gap-1"):
                                                                    ui.label("63MM PVC").classes("text-[12px] font-bold text-center")
                                                                    e_63 = ui.input(value=str(get_q(report,'qty_63mm'))).props("type=number outlined dense").classes("w-full font-bold text-[14px]")
                                                                with ui.column().classes("gap-1"):
                                                                    ui.label("90MM PVC").classes("text-[12px] font-bold text-center")
                                                                    e_90 = ui.input(value=str(get_q(report,'qty_90mm'))).props("type=number outlined dense").classes("w-full font-bold text-[14px]")
                                                                with ui.column().classes("gap-1"):
                                                                    ui.label("110MM PVC").classes("text-[12px] font-bold text-center")
                                                                    e_110 = ui.input(value=str(get_q(report,'qty_110mm'))).props("type=number outlined dense").classes("w-full font-bold text-[14px]")
                                                                with ui.column().classes("gap-1"):
                                                                    ui.label("150MM DI").classes("text-[12px] font-bold text-center")
                                                                    e_150 = ui.input(value=str(get_q(report,'qty_150mm'))).props("type=number outlined dense").classes("w-full font-bold text-[14px]")
                                                            ui.label("Extra MTR (Additional Meters)").classes("text-[13px] font-extrabold text-orange-700 mt-3 bg-orange-50 px-2 py-1 rounded-full")
                                                            with ui.grid(columns=4).classes("w-full gap-2 mt-1"):
                                                                with ui.column().classes("gap-1"):
                                                                    ui.label("63MM Extra").classes("text-[11px] font-bold text-center text-orange-600")
                                                                    e_extra_63 = ui.input(value=str(get_q(report,'extra_63mm',0))).props("type=number outlined dense color=orange").classes("w-full font-bold text-[14px] bg-orange-50")
                                                                with ui.column().classes("gap-1"):
                                                                    ui.label("90MM Extra").classes("text-[11px] font-bold text-center text-orange-600")
                                                                    e_extra_90 = ui.input(value=str(get_q(report,'extra_90mm',0))).props("type=number outlined dense color=orange").classes("w-full font-bold text-[14px] bg-orange-50")
                                                                with ui.column().classes("gap-1"):
                                                                    ui.label("110MM Extra").classes("text-[11px] font-bold text-center text-orange-600")
                                                                    e_extra_110 = ui.input(value=str(get_q(report,'extra_110mm',0))).props("type=number outlined dense color=orange").classes("w-full font-bold text-[14px] bg-orange-50")
                                                                with ui.column().classes("gap-1"):
                                                                    ui.label("150MM Extra").classes("text-[11px] font-bold text-center text-orange-600")
                                                                    e_extra_150 = ui.input(value=str(get_q(report,'extra_150mm',0))).props("type=number outlined dense color=orange").classes("w-full font-bold text-[14px] bg-orange-50")
                                                        with ui.row().classes("w-full justify-between gap-2 p-2 bg-white border-t shrink-0"):
                                                            ui.button("Cancel", icon="close", on_click=edit_dialog.close).props("flat rounded dense").classes("flex-1 bg-slate-100 text-[12px]")
                                                            save_edit_btn = ui.button("OK", icon="check").props("rounded dense").classes("flex-1 bg-blue-600 text-white font-bold text-[12px]")
                                                            def make_save_edit(rpt=report, ed=e_date, ea=e_area, et=e_title, e63=e_63, e90=e_90, e110=e_110, e150=e_150, el=e_labour, ec=e_connection, dlg=edit_dialog, ex63=e_extra_63, ex90=e_extra_90, ex110=e_extra_110, ex150=e_extra_150):
                                                                def do_save():
                                                                    try:
                                                                        try:
                                                                            new_date = datetime.datetime.strptime((ed.value or "").strip(), "%Y-%m-%d").date()
                                                                        except:
                                                                            new_date = rpt.report_date
                                                                        new_area = (ea.value or "").strip() or rpt.area_name
                                                                        new_labour = (el.value or "").strip() or get_q(rpt,'labour_name','')
                                                                        # Calculate sum from edit_conn_state items
                                                                        new_conn_sum = 0
                                                                        try:
                                                                            for it in edit_conn_state.get("items", []):
                                                                                try:
                                                                                    new_conn_sum += float(str(it.get('conn','0') or 0).strip() or 0)
                                                                                except:
                                                                                    pass
                                                                        except:
                                                                            new_conn_sum = 0
                                                                        # If no items, fallback to old ec field
                                                                        if new_conn_sum == 0:
                                                                            try:
                                                                                new_conn_sum = float((ec.value or "").strip() or 0)
                                                                            except:
                                                                                new_conn_sum = 0
                                                                        if new_conn_sum == int(new_conn_sum):
                                                                            new_conn = str(int(new_conn_sum)) if new_conn_sum!=0 else ""
                                                                        else:
                                                                            new_conn = str(new_conn_sum) if new_conn_sum!=0 else ""
                                                                        new_title = (et.value or "").strip() or rpt.report_title
                                                                        def pq(v):
                                                                            try: return float(v) if v not in (None, "") else 0
                                                                            except: return 0
                                                                        q63 = pq(e63.value); q90 = pq(e90.value); q110 = pq(e110.value); q150 = pq(e150.value)
                                                                        ex_63 = pq(ex63.value); ex_90 = pq(ex90.value); ex_110 = pq(ex110.value); ex_150 = pq(ex150.value)
                                                                        total_mtr = (q63*6+ex_63)+(q90*6+ex_90)+(q110*6+ex_110)+(q150*5.5+ex_150)
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
                                                                        rpt.qty_63mm = q63; rpt.qty_90mm = q90; rpt.qty_110mm = q110
                                                                        try: rpt.qty_150mm = q150
                                                                        except: pass
                                                                        try: 
                                                                            rpt.extra_63mm = ex_63; rpt.extra_90mm = ex_90; rpt.extra_110mm = ex_110; rpt.extra_150mm = ex_150
                                                                            rpt.total_mtr = total_mtr
                                                                            rpt.total_pvc = q63+q90+q110; rpt.total_di = q150
                                                                        except: pass
                                                                        rpt.total_qty = q63+q90+q110+q150
                                                                        rpt.price_sum = float(total_mtr)
                                                                        rpt.save()
                                                                        # Save ConnectionEntry: delete old and recreate from edit_conn_state
                                                                        try:
                                                                            from models_app.models import ConnectionEntry
                                                                            # Delete all old entries for this report and also by date for safety
                                                                            ConnectionEntry.objects.filter(report=rpt).delete()
                                                                            try:
                                                                                ConnectionEntry.objects.filter(user=rpt.user, report_date=rpt.report_date, area_name=rpt.area_name).exclude(report=rpt).delete()
                                                                            except:
                                                                                pass
                                                                            for it in edit_conn_state.get("items", []):
                                                                                ConnectionEntry.objects.create(
                                                                                    user=rpt.user, report=rpt, report_date=new_date,
                                                                                    connection_no=str(it.get('conn','')).strip(),
                                                                                    name=str(it.get('name','')).strip(),
                                                                                    mobile=str(it.get('mobile','')).strip(),
                                                                                    area_name=new_area
                                                                                )
                                                                        except Exception as ce:
                                                                            print(f"Edit conn save fail: {ce}")
                                                                            import traceback; traceback.print_exc()
                                                                        ui.notify(f"✅ Updated! MTR:{total_mtr} Conn Sum:{new_conn_sum}", type="positive", position="top", timeout=2000)
                                                                        dlg.close()
                                                                        # Instant refresh without Loading screen - only update detail view
                                                                        try:
                                                                            # Rebuild detail view directly with updated report, no loading spinner
                                                                            build_filter_detail(rpt)
                                                                        except Exception as e:
                                                                            print(f"Refresh detail fail: {e}")
                                                                            # Fallback: just close, don't show loading
                                                                            pass
                                                                        load_table_data()
                                                                    except Exception as ex:
                                                                        import traceback; traceback.print_exc()
                                                                        ui.notify(f"Edit failed: {ex}", type="negative")
                                                                return do_save
                                                            save_edit_btn.on_click(make_save_edit())
                                                edit_btn.on_click(edit_dialog.open)
                                                with ui.dialog() as del_dialog, ui.card().classes("rounded-3xl p-0 w-full max-w-sm overflow-hidden shadow-2xl"):
                                                    with ui.column().classes("w-full p-0 gap-0"):
                                                        with ui.row().classes("w-full bg-gradient-to-r from-red-500 to-red-600 p-4 items-center gap-3 text-white"):
                                                            ui.icon("warning", size="1.5rem"); ui.label("Delete?").classes("font-extrabold text-sm text-white")
                                                        with ui.column().classes("w-full p-5 gap-3 bg-white"):
                                                            ui.label("This report will be permanently deleted!").classes("text-sm font-bold")
                                                            ui.label(f"Area: {report.area_name} | Labour: {get_q(report,'labour_name','') or 'No Labour'} | Date: {report.report_date.strftime('%d-%m-%Y')} | Total: {report.total_qty} Qty").classes("text-xs text-slate-600")
                                                            with ui.row().classes("w-full justify-between gap-3 mt-2"):
                                                                ui.button("Cancel", icon="close", on_click=del_dialog.close).props("flat rounded").classes("flex-1 bg-slate-100")
                                                                confirm_del_btn = ui.button("Delete", icon="delete_forever").props("rounded").classes("flex-1 bg-red-600 text-white font-bold")
                                                                def make_del(rpt=report, dlg=del_dialog):
                                                                    def do_del():
                                                                        try:
                                                                            rpt.delete()
                                                                            ui.notify("🗑️ Data Deleted!", type="positive", position="top", timeout=2000)
                                                                            dlg.close()
                                                                            load_table_data()
                                                                        except Exception as ex:
                                                                            ui.notify(f"Failed: {ex}", type="negative")
                                                                    return do_del
                                                                confirm_del_btn.on_click(make_del())
                                                del_btn.on_click(del_dialog.open)
                            else:
                                agg = base_qs.aggregate(s63=Sum('qty_63mm'), s90=Sum('qty_90mm'), s110=Sum('qty_110mm'), s150=Sum('qty_150mm'), ex63=Sum('extra_63mm'), ex90=Sum('extra_90mm'), ex110=Sum('extra_110mm'), ex150=Sum('extra_150mm'), tmtr=Sum('total_mtr')); t63 = agg['s63'] or 0; t90 = agg['s90'] or 0; t110 = agg['s110'] or 0; t150 = agg['s150'] or 0; te63 = agg['ex63'] or 0; te90 = agg['ex90'] or 0; te110 = agg['ex110'] or 0; te150 = agg['ex150'] or 0; tmtr = agg['tmtr'] or 0; period_text = f"Full Month: {months[sel_month]} {sel_year}"
                                total_connections = 0
                                try:
                                    from models_app.models import ConnectionEntry
                                    # Sum of connection_no values, not count
                                    entries = ConnectionEntry.objects.filter(user=user, report_date__year=sel_year, report_date__month=sel_month)
                                    for ce in entries:
                                        try:
                                            total_connections += float(str(ce.connection_no or 0).strip() or 0)
                                        except:
                                            pass
                                    if total_connections == 0:
                                        for r in base_qs:
                                            cv = getattr(r, 'connection', '') or ''
                                            try:
                                                if cv:
                                                    total_connections += float(str(cv).strip() or 0)
                                            except:
                                                pass
                                except Exception as e:
                                    print(f"Monthly conn sum fail: {e}")
                                    try:
                                        for r in base_qs:
                                            cv = getattr(r, 'connection', '') or ''
                                            try:
                                                if cv:
                                                    total_connections += float(str(cv).strip() or 0)
                                            except:
                                                pass
                                    except:
                                        pass
                                with table_container:
                                    with ui.row().classes("w-full justify-between items-center mb-2 px-1"):
                                        ui.badge(period_text, color="green").classes("text-xs font-bold px-2 py-1"); ui.badge(f"Total: {t63+t90+t110+t150} Qty", color="green").classes("text-xs font-bold px-2 py-1")
                                    tm63 = t63*6 + te63; tm90 = t90*6 + te90; tm110 = t110*6 + te110; tm150 = t150*5.5 + te150
                                    rows = [{"sr_no": 1, "pipe_dia": "63MM PVC", "quantity": t63, "extra": te63, "unit": "6MTR per PIPES", "total_mtr": tm63}, {"sr_no": 2, "pipe_dia": "90MM PVC", "quantity": t90, "extra": te90, "unit": "6MTR per PIPES", "total_mtr": tm90}, {"sr_no": 3, "pipe_dia": "110MM PVC", "quantity": t110, "extra": te110, "unit": "6MTR per PIPES", "total_mtr": tm110}, {"sr_no": 4, "pipe_dia": "150MM DI", "quantity": t150, "extra": te150, "unit": "5.5MTR", "total_mtr": tm150}]
                                    columns = [{"name": "sr_no", "label": "Sr.No", "field": "sr_no", "align": "center"}, {"name": "pipe_dia", "label": "Pipe Dia", "field": "pipe_dia", "align": "center"}, {"name": "quantity", "label": "Qty", "field": "quantity", "align": "center"}, {"name": "extra", "label": "Extra", "field": "extra", "align": "center"}, {"name": "unit", "label": "UNIT", "field": "unit", "align": "center"}, {"name": "total_mtr", "label": "Total MTR", "field": "total_mtr", "align": "center"}]
                                    ui.table(columns=columns, rows=rows).props("dense flat bordered").classes("w-full rounded-xl shadow-sm border border-green-200 text-xs font-semibold")
                                    with ui.row().classes("w-full justify-center gap-2 mt-2 flex-wrap"):
                                        ui.badge(f"PVC: {t63+t90+t110} Qty | Extra:{te63+te90+te110} MTR | Total MTR:{tm63+tm90+tm110}", color="blue").classes("text-[10px] font-bold px-2 py-1")
                                        ui.badge(f"DI: {t150} Qty | Extra:{te150} MTR | Total MTR:{tm150}", color="purple").classes("text-[10px] font-bold px-2 py-1")
                                        ui.badge(f"Grand Extra: {te63+te90+te110+te150} MTR | Grand Total MTR: {tm63+tm90+tm110+tm150}", color="green").classes("text-[10px] font-bold px-2 py-1")
                                        ui.badge(f"Total Connections: {total_connections}", color="orange").classes("text-[10px] font-bold px-2 py-1")
                                    with ui.dialog() as month_download_dialog, ui.card().classes("rounded-3xl p-0 w-full max-w-xs overflow-hidden shadow-2xl relative"):
                                        with ui.row().classes("w-full justify-between items-center p-3 bg-gradient-to-r from-green-600 to-emerald-600 text-white"):
                                            ui.label(f"📥 Download {period_text}").classes("font-extrabold text-xs text-white")
                                            ui.button(icon="close", on_click=month_download_dialog.close).props("flat round dense color=white").classes("text-white")
                                        with ui.column().classes("w-full p-4 gap-2 bg-white"):
                                            ui.label(f"{period_text} - {t63+t90+t110+t150} Qty").classes("text-xs font-bold text-green-700 text-center w-full mb-1")
                                            def do_m_csv():
                                                data = generate_month_csv(user.default_report_title, period_text, t63, t90, t110, t150)
                                                ui.download(data, f"{period_text.replace(' ', '_')}_report.csv")
                                                month_download_dialog.close()
                                            def do_m_excel():
                                                data = generate_month_excel(user.default_report_title, period_text, t63, t90, t110, t150)
                                                ui.download(data, f"{period_text.replace(' ', '_')}_report.xlsx")
                                                month_download_dialog.close()
                                            def do_m_pdf():
                                                data = generate_month_pdf(user.default_report_title, period_text, t63, t90, t110, t150)
                                                ui.download(data, f"{period_text.replace(' ', '_')}_report.pdf")
                                                month_download_dialog.close()
                                            ui.button("As CSV", icon="table_view", on_click=do_m_csv).props("outline rounded").classes("w-full font-bold text-sm border-blue-500 text-blue-600")
                                            ui.button("As Excel", icon="description", on_click=do_m_excel).props("outline rounded").classes("w-full font-bold text-sm border-green-500 text-green-600")
                                            ui.button("As PDF", icon="picture_as_pdf", on_click=do_m_pdf).props("outline rounded").classes("w-full font-bold text-sm border-red-500 text-red-600")
                                    ui.button("📥 Download", icon="download", on_click=month_download_dialog.open).props("rounded no-caps").classes("w-full mt-3 bg-gradient-to-r from-blue-500 to-blue-600 text-white font-bold py-2.5 shadow-md")
                        def safe_load(*_):
                            try:
                                load_table_data()
                            except Exception as e:
                                print(f"Filter load error: {e}")
                                try:
                                    with table_container:
                                        ui.label(f"Load error: {e}").classes("text-xs text-red-500")
                                except:
                                    pass
                        day_select.on_value_change(safe_load)
                        month_select.on_value_change(safe_load)
                        year_select.on_value_change(safe_load)
                        ui.timer(0.15, safe_load, once=True)

        def build_filter_detail(report):
            filter_detail_view.clear()
            with filter_detail_view:
                with ui.column().classes("w-full max-w-md items-center gap-2"):
                    with ui.card().classes("w-full rounded-3xl shadow-2xl bg-white p-3 sm:p-5 border-2 border-green-200"):
                        with ui.row().classes("w-full justify-between items-center mb-3"):
                            ui.button("Back", icon="arrow_back", on_click=show_filter).props("flat rounded no-caps dense").classes("back-btn text-xs")
                            ui.badge(f"{report.report_date.strftime('%d-%m-%Y')}", color="green").classes("font-bold text-xs")
                        with ui.column().classes("w-full rounded-2xl bg-gradient-to-r from-green-200 via-emerald-200 to-teal-200 p-3 border-2 border-green-300 shadow-md mb-3"):
                            with ui.column().classes("w-full gap-1"):
                                with ui.row().classes("w-full items-center gap-2"):
                                    ui.icon("location_on", color="green"); ui.label(f"Area: {report.area_name or 'No Area'}").classes("font-extrabold text-base text-green-900")
                                with ui.row().classes("w-full items-center gap-2"):
                                    ui.icon("engineering", color="blue"); ui.label(f"Labour: {get_q(report,'labour_name','') or 'No Labour'}").classes("font-bold text-sm text-blue-900")
                                conn_det = get_q(report, 'connection', '')
                                conn_entries = []
                                try:
                                    from models_app.models import ConnectionEntry
                                    conn_entries = list(ConnectionEntry.objects.filter(report=report).order_by('id'))
                                    if not conn_entries:
                                        # Try by date and user if report link not set (old data)
                                        conn_entries = list(ConnectionEntry.objects.filter(user=report.user, report_date=report.report_date, area_name=report.area_name).order_by('id'))
                                except Exception as e:
                                    print(f"Conn fetch fail: {e}")
                                    conn_entries = []
                                if conn_det or conn_entries:
                                    with ui.column().classes("w-full gap-1 bg-orange-50 p-2 rounded-xl border border-orange-200"):
                                        with ui.row().classes("w-full items-center gap-2"):
                                            ui.icon("power", color="orange")
                                            total_c = len(conn_entries) if conn_entries else conn_det
                                            ui.label(f"Total Connections: {total_c}").classes("font-extrabold text-sm text-orange-800")
                                        # Show individual entries like 56,Mohanlal,9988779988
                                        if conn_entries:
                                            for ce in conn_entries:
                                                ui.label(f"{ce.connection_no},{ce.name},{ce.mobile}").classes("text-[11px] font-bold text-slate-700 bg-white px-2 py-1 rounded-full border border-orange-100 w-full")
                                        else:
                                            ui.label(f"Connection: {conn_det}").classes("font-bold text-sm text-orange-800")
                        with ui.column().classes("w-full rounded-2xl overflow-hidden shadow-lg border-2 border-indigo-900 gap-0 mb-4"):
                            # Header
                            with ui.grid(columns=4).classes("w-full bg-gradient-to-r from-emerald-500 via-green-500 to-teal-500 text-white font-extrabold text-center"):
                                ui.label("63MM PVC").classes("py-2 text-[10px]"); ui.label("90MM PVC").classes("py-2 text-[10px] border-x border-white/30"); ui.label("110MM PVC").classes("py-2 text-[10px] border-r border-white/30"); ui.label("150MM DI").classes("py-2 text-[10px]")
                            # Quantity Row
                            with ui.grid(columns=4).classes("w-full bg-white text-center items-center"):
                                ui.label(f"{get_q(report,'qty_63mm')}").classes("py-2 font-extrabold text-xs"); ui.label(f"{get_q(report,'qty_90mm')}").classes("py-2 font-extrabold text-xs border-x border-gray-200"); ui.label(f"{get_q(report,'qty_110mm')}").classes("py-2 font-extrabold text-xs border-r border-gray-200"); ui.label(f"{get_q(report,'qty_150mm')}").classes("py-2 font-extrabold text-xs bg-green-50 text-green-700")
                            # Pipe MTR + Extra MTR Row - NEW
                            with ui.grid(columns=4).classes("w-full bg-green-50 text-center border-y border-indigo-900 items-center"):
                                ex63 = get_q(report,'extra_63mm',0); ex90 = get_q(report,'extra_90mm',0); ex110 = get_q(report,'extra_110mm',0); ex150 = get_q(report,'extra_150mm',0)
                                m63 = get_q(report,'qty_63mm')*6 + ex63; m90 = get_q(report,'qty_90mm')*6 + ex90; m110 = get_q(report,'qty_110mm')*6 + ex110; m150 = get_q(report,'qty_150mm')*5.5 + ex150
                                def fmt(m, ex):
                                    if ex>0:
                                        return f"{m} MTR (+{ex})"
                                    return f"{m} MTR"
                                ui.label(fmt(m63, ex63)).classes("py-1.5 font-bold text-[10px]"); ui.label(fmt(m90, ex90)).classes("py-1.5 font-bold text-[10px] border-x border-gray-200"); ui.label(fmt(m110, ex110)).classes("py-1.5 font-bold text-[10px] border-r border-gray-200"); ui.label(fmt(m150, ex150)).classes("py-1.5 font-bold text-[10px] bg-green-50")
                            # Extra MTR Row Highlight
                            with ui.grid(columns=4).classes("w-full bg-orange-50 text-center border-b border-indigo-900 items-center"):
                                ex63 = get_q(report,'extra_63mm',0); ex90 = get_q(report,'extra_90mm',0); ex110 = get_q(report,'extra_110mm',0); ex150 = get_q(report,'extra_150mm',0)
                                has_extra = ex63+ex90+ex110+ex150 > 0
                                if has_extra:
                                    ui.label(f"+{ex63} Extra" if ex63>0 else "-").classes("py-1 font-bold text-[9px] text-orange-600")
                                    ui.label(f"+{ex90} Extra" if ex90>0 else "-").classes("py-1 font-bold text-[9px] text-orange-600 border-x border-gray-200")
                                    ui.label(f"+{ex110} Extra" if ex110>0 else "-").classes("py-1 font-bold text-[9px] text-orange-600 border-r border-gray-200")
                                    ui.label(f"+{ex150} Extra" if ex150>0 else "-").classes("py-1 font-bold text-[9px] text-orange-600")
                                else:
                                    ui.label("No Extra").classes("py-1 font-bold text-[9px] text-slate-400 col-span-4")
                            with ui.grid(columns=2).classes("w-full bg-gradient-to-r from-slate-900 via-indigo-950 to-slate-900 text-white text-center items-center"):
                                pvc = get_q(report,'qty_63mm')+get_q(report,'qty_90mm')+get_q(report,'qty_110mm')
                                di = get_q(report,'qty_150mm')
                                ex_total = get_q(report,'extra_63mm',0)+get_q(report,'extra_90mm',0)+get_q(report,'extra_110mm',0)+get_q(report,'extra_150mm',0)
                                total_mtr_val = get_q(report,'total_mtr',0)
                                if total_mtr_val==0:
                                    total_mtr_val = (get_q(report,'qty_63mm')*6+get_q(report,'qty_90mm')*6+get_q(report,'qty_110mm')*6+get_q(report,'qty_150mm')*5.5)+ex_total
                                ui.label(f"PVC: {pvc} Qty | DI: {di} Qty").classes("py-2 font-bold text-green-300 text-[10px] border-r border-white/10")
                                ui.label(f"Total MTR: {total_mtr_val}").classes("py-2 font-bold text-yellow-200 text-[10px]")
                            # Grand Total MTR Banner
                            with ui.grid(columns=1).classes("w-full bg-gradient-to-r from-amber-900 to-yellow-900 text-center"):
                                ex_total = get_q(report,'extra_63mm',0)+get_q(report,'extra_90mm',0)+get_q(report,'extra_110mm',0)+get_q(report,'extra_150mm',0)
                                if ex_total>0:
                                    ui.label(f"Extra MTR Added: {ex_total} MTR").classes("py-1.5 font-extrabold text-orange-200 text-[11px]")
                            # Grand Total REMOVED - Only PVC and DI separate as per user request
                            # with ui.grid(columns=1).classes("w-full bg-gradient-to-r from-emerald-900 to-teal-900 text-center"):
                            #     gt = pvc + di
                            #     ui.label(f"Grand Total: {gt} Quantity").classes("py-2.5 font-extrabold text-white text-sm")
                        with ui.column().classes("w-full bg-gray-50 rounded-xl p-3 border border-gray-200 mb-3"):
                            ui.label(f"📅 Date: {report.report_date.strftime('%d-%m-%Y')}").classes("text-xs font-bold text-slate-700")
                            ui.label(f"📍 Area: {report.area_name}").classes("text-xs font-bold text-slate-700")
                            ui.label(f"👷 Labour: {get_q(report,'labour_name','') or 'No Labour'}").classes("text-xs font-bold text-slate-700")
                            ui.label(f"🔌 Connection: {get_q(report,'connection','') or 'No Connection'}").classes("text-xs font-bold text-orange-700")
                            ui.label(f"📄 Title: {report.report_title}").classes("text-xs font-bold text-slate-700")
                        with ui.dialog() as detail_download_dialog, ui.card().classes("rounded-3xl p-0 w-full max-w-xs overflow-hidden shadow-2xl relative"):
                            with ui.row().classes("w-full justify-between items-center p-3 bg-gradient-to-r from-green-600 to-emerald-600 text-white"):
                                ui.label(f"📥 Download {report.area_name}").classes("font-extrabold text-xs text-white")
                                ui.button(icon="close", on_click=detail_download_dialog.close).props("flat round dense color=white").classes("text-white bg-white/20")
                            with ui.column().classes("w-full p-4 gap-2 bg-white"):
                                def do_csv():
                                    ui.download(generate_single_csv(report), f"{report.area_name}_{report.report_date}_report.csv")
                                    detail_download_dialog.close()
                                def do_excel():
                                    ui.download(generate_single_excel(report), f"{report.area_name}_{report.report_date}_report.xlsx")
                                    detail_download_dialog.close()
                                def do_pdf():
                                    ui.download(generate_single_pdf(report), f"{report.area_name}_{report.report_date}_report.pdf")
                                    detail_download_dialog.close()
                                ui.button("As CSV", icon="table_view", on_click=do_csv).props("outline rounded no-caps").classes("w-full font-bold text-sm border-blue-500 text-blue-600 py-2")
                                ui.button("As Excel", icon="description", on_click=do_excel).props("outline rounded no-caps").classes("w-full font-bold text-sm border-green-500 text-green-600 py-2")
                                ui.button("As PDF", icon="picture_as_pdf", on_click=do_pdf).props("outline rounded no-caps").classes("w-full font-bold text-sm border-red-500 text-red-600 py-2")
                        ui.button("📥 Download", icon="download", on_click=detail_download_dialog.open).props("rounded no-caps").classes("w-full py-3 bg-gradient-to-r from-green-500 to-emerald-600 text-white font-extrabold text-base shadow-xl")

        def build_profile():
            profile_view.clear()
            user = state["user"]
            if not user:
                show_login()
                return
            with profile_view:
                with ui.column().classes("w-full max-w-sm items-center gap-3"):
                    with ui.card().classes("profile-card w-full p-0 overflow-hidden"):
                        with ui.row().classes("w-full justify-start p-4 pb-2"):
                            ui.button("Back to Home", icon="arrow_back", on_click=show_home).props("flat rounded dense no-caps").classes("back-btn text-xs")
                        with ui.column().classes("w-full items-center gap-1 px-6 pb-4"):
                            with ui.element("div").classes("w-20 h-20 rounded-full bg-gradient-to-br from-green-500 to-emerald-600 flex items-center justify-center shadow-lg"):
                                ui.icon("person", size="3rem").classes("text-white")
                            ui.label(user.username or "aj").classes("text-xl font-extrabold text-slate-900 mt-2 tracking-tight")
                            ui.label(user.email).classes("text-sm font-semibold text-emerald-600 text-center break-all")
                        with ui.column().classes("w-full px-6 pb-6 gap-3"):
                            delete_btn = ui.button("Delete Account", icon="delete_forever").props("outline rounded no-caps").classes("delete-btn w-full py-2.5 shadow-sm")
                            logout_btn = ui.button("LOGOUT", icon="logout").props("outline rounded no-caps").classes("w-full py-2 font-bold text-sm border-blue-300 text-blue-600 hover:bg-blue-50")
                            with ui.dialog() as delete_dialog, ui.card().classes("rounded-3xl p-0 w-full max-w-sm overflow-hidden shadow-2xl"):
                                with ui.column().classes("w-full p-0 gap-0"):
                                    with ui.row().classes("w-full bg-gradient-to-r from-red-500 to-red-600 p-4 items-center gap-3 text-white"):
                                        ui.icon("warning", size="1.8rem").classes("text-white")
                                        ui.label("Delete Account?").classes("font-extrabold text-base text-white")
                                    with ui.column().classes("w-full p-5 gap-3 bg-white"):
                                        ui.label("All your data will be permanently deleted!").classes("text-sm font-bold text-slate-800")
                                        with ui.row().classes("w-full justify-between gap-3 mt-2"):
                                            cancel_btn = ui.button("Cancel", icon="close").props("flat rounded no-caps").classes("flex-1 font-bold text-slate-600 bg-slate-100")
                                            ok_btn = ui.button("OK, Delete", icon="check").props("rounded no-caps").classes("flex-1 bg-red-600 text-white font-bold shadow-md")
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
                                                CACHE["users"].pop(email, None)
                                                CACHE["areas"].pop(user_id, None)
                                                app.storage.user.clear()
                                                ui.notify(f"Account {email} deleted!", type="positive", position="top")
                                                delete_dialog.close()
                                                show_login()
                                            except Exception as e:
                                                ui.notify(f"Delete failed: {e}", type="negative", position="top")
                                        cancel_btn.on_click(do_cancel)
                                        ok_btn.on_click(do_delete)
                            delete_btn.on_click(delete_dialog.open)
                            def do_logout():
                                state["user"] = None
                                saved_e = app.storage.user.get("saved_email", "")
                                saved_p = app.storage.user.get("saved_password", "")
                                app.storage.user.clear()
                                app.storage.user["saved_email"] = saved_e
                                app.storage.user["saved_password"] = saved_p
                                show_login()
                            logout_btn.on_click(do_logout)

        with register_view:
            with ui.card().classes("w-full max-w-sm rounded-3xl shadow-2xl overflow-hidden p-0"):
                with ui.column().classes("w-full bg-gradient-to-r from-emerald-500 via-teal-600 to-cyan-600 p-5 items-center text-white"):
                    ui.icon("person_add", size="2.5rem"); ui.label("Create Account (6-digit)").classes("text-xl font-extrabold")
                with ui.column().classes("w-full p-5 bg-white gap-3"):
                    uname = ui.input("User name").props("outlined rounded dense").classes("w-full")
                    email = ui.input("Email id").props("outlined rounded dense").classes("w-full")
                    pwd = ui.input("Password (6 digits)", placeholder="Ex: 123456", password=True, password_toggle_button=True).props("outlined rounded dense maxlength=6").classes("w-full")
                    re_pwd = ui.input("Retype password (6 digits)", placeholder="Ex: 123456", password=True, password_toggle_button=True).props("outlined rounded dense maxlength=6").classes("w-full")
                    def handle_register():
                        u_val = (uname.value or "").strip(); e_val = (email.value or "").strip(); p_val = (pwd.value or "").strip(); rp_val = (re_pwd.value or "").strip()
                        if not u_val or not e_val: ui.notify("Enter User name and Email!", type="warning", position="top"); return
                        if not is_valid_6digit(p_val):
                            ui.notify("Password must be exactly 6 digits! e.g., 123456", type="negative", position="top"); return
                        if p_val != rp_val: ui.notify("Passwords not same!", type="negative", position="top"); return
                        if AppUser.objects.filter(email=e_val).exists(): ui.notify("Already registered!", type="negative", position="top"); return
                        user = AppUser.objects.create(username=u_val, email=e_val, password=make_password(p_val), default_report_title="Veraval site daily progress report")
                        CACHE["users"][e_val] = user
                        pwd_key = hashlib.sha256(f"{e_val}:{p_val}".encode()).hexdigest()
                        CACHE["pwd_verified"][pwd_key] = user.id
                        app.storage.user["saved_email"] = e_val
                        app.storage.user["saved_password"] = p_val
                        ui.notify("Account created!", type="positive", position="top")
                        show_login()
                    ui.button("Register (6-digit)", icon="check_circle", on_click=handle_register).props("rounded no-caps").classes("w-full py-2.5 mt-1 bg-gradient-to-r from-emerald-500 to-teal-600 text-white font-bold text-base shadow-lg")
                    ui.button("Back", icon="arrow_back", on_click=show_login).props("flat no-caps").classes("back-btn w-full font-semibold text-sm mt-1")

        async def handle_login():
            email = (email_input.value or "").strip()
            pwd = (pass_input.value or "").strip()
            if not email or not pwd:
                ui.notify("Enter Email & Password!", type="warning", position="top")
                return
            if not is_valid_6digit(pwd):
                ui.notify("Password must be exactly 6 digits!", type="warning", position="top")
                return
            pwd_key = hashlib.sha256(f"{email}:{pwd}".encode()).hexdigest()
            if pwd_key in CACHE["pwd_verified"]:
                user_id = CACHE["pwd_verified"][pwd_key]
                cached_user = CACHE["users"].get(email)
                if cached_user and cached_user.id == user_id:
                    state["user"] = cached_user
                    app.storage.user["logged_in_user_id"] = cached_user.id
                    app.storage.user["saved_email"] = email
                    app.storage.user["saved_password"] = pwd
                    status_label.set_text("✅ Logged in (cached)")
                    show_home()
                    return
            status_label.set_text("⏳ Verifying...")
            login_btn.props("loading")
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
                    status_label.set_text("❌ User not found")
                    ui.notify("User not found! Register first.", type="negative", position="top")
                    return
                if not is_valid:
                    status_label.set_text("❌ Invalid password")
                    ui.notify("❌ Invalid password!", type="negative", position="top")
                    return
                CACHE["users"][email] = quick_user
                CACHE["pwd_verified"][pwd_key] = quick_user.id
                state["user"] = quick_user
                app.storage.user["logged_in_user_id"] = quick_user.id
                app.storage.user["saved_email"] = email
                app.storage.user["saved_password"] = pwd
                status_label.set_text("✅ Logged in")
                show_home()
            except Exception as e:
                print(f"❌ Login error: {e}\n{traceback.format_exc()}", flush=True)
                status_label.set_text(f"❌ Error: {str(e)[:80]}")
                ui.notify(f"Login failed: {e}", type="negative", position="top")
            finally:
                login_btn.props(remove="loading")

        login_btn.on_click(handle_login)
        reg_btn.on_click(show_register)
        forgot_link.on("click", show_forgot)
        show_login()

if __name__ in {"__main__", "__mp_main__"}:
    print(f"🚀 FINAL SIMPLE 4-PIPE Starting on 0.0.0.0:{PORT}", flush=True)
    ui.run(host="0.0.0.0", port=PORT, title="VERAVAL TRACKER", storage_secret=STORAGE_SECRET, reload=False, show=False, dark=False)
