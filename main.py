import os, datetime, csv, io, secrets, hashlib, traceback, requests
print("🚀 FINAL 4-PIPE SIMPLE Loading...", flush=True)
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
    # SAFE VERSION - No ALTER TYPE that causes syntax error, use Django migration safe method
    try:
        with connection.cursor() as cursor:
            # Check if tables exist first
            cursor.execute("SELECT to_regclass('models_app_dailyreport');")
            table_exists = cursor.fetchone()[0] is not None
            if not table_exists:
                print("⏳ Tables not yet created - skipping ALTER, will be created by Django", flush=True)
                return
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_fast_email ON models_app_appuser (email);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_fast_user_date ON models_app_dailyreport (user_id, report_date);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_fast_date ON models_app_dailyreport (report_date);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_fast_area ON models_app_savedarea (user_id);")
            # SAFE: Add columns if not exists - no TYPE change that causes syntax error
            cursor.execute("ALTER TABLE models_app_dailyreport ADD COLUMN IF NOT EXISTS labour_name VARCHAR(150) DEFAULT '';")
            cursor.execute("ALTER TABLE models_app_dailyreport ADD COLUMN IF NOT EXISTS qty_150mm DOUBLE PRECISION DEFAULT 0;")
            cursor.execute("ALTER TABLE models_app_dailyreport ADD COLUMN IF NOT EXISTS total_pvc DOUBLE PRECISION DEFAULT 0;")
            cursor.execute("ALTER TABLE models_app_dailyreport ADD COLUMN IF NOT EXISTS total_di DOUBLE PRECISION DEFAULT 0;")
            # For point values, we don't ALTER TYPE in code - we handle in models as FloatField
            # Old integer data will still work as float in Django
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS models_app_savedlabour (
                    id BIGSERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL REFERENCES models_app_appuser(id) ON DELETE CASCADE,
                    labour_name VARCHAR(150) NOT NULL,
                    UNIQUE(user_id, labour_name)
                );
            """)
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

def send_gmail_smtp(to_email, username, reset_link):
    """FREE method - sends to ALL emails using Gmail - No domain needed!"""
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    gmail_user = os.getenv("GMAIL_USER", "").strip() or os.getenv("EMAIL_FROM_GMAIL", "").strip()
    gmail_pass = os.getenv("GMAIL_APP_PASSWORD", "").strip() or os.getenv("GMAIL_PASSWORD", "").strip()
    if not gmail_user or not gmail_pass:
        return False, "GMAIL_NOT_SET"
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"Reset Password - {username}"
        msg["From"] = gmail_user
        msg["To"] = to_email
        html = f"""<div style="font-family:Arial; max-width:500px; margin:0 auto; background:white; padding:30px; border-radius:16px; border:2px solid #10B981;">
        <h2 style="color:#059669;">Hi {username}!</h2>
        <p>Reset for: <b>{to_email}</b></p>
        <p>Click below (15 min valid):</p>
        <a href="{reset_link}" style="display:inline-block; background:#059669; color:white; padding:14px 28px; text-decoration:none; border-radius:9999px; font-weight:bold; margin:20px 0;">Reset Password</a>
        <p style="font-size:12px; color:#666;">Link: {reset_link}</p></div>"""
        msg.attach(MIMEText(html, "html"))
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(gmail_user, gmail_pass)
            server.sendmail(gmail_user, to_email, msg.as_string())
        return True, f"Gmail sent to {to_email}"
    except Exception as e:
        return False, f"Gmail failed: {e}"

def send_reset_email_resend_http(to_email, username, reset_link):
    # First try Gmail (FREE - ALL emails) if configured
    gmail_user = os.getenv("GMAIL_USER", "").strip()
    gmail_pass = os.getenv("GMAIL_APP_PASSWORD", "").strip()
    if gmail_user and gmail_pass:
        success, msg = send_gmail_smtp(to_email, username, reset_link)
        if success:
            print(f"✅ Gmail sent to {to_email}", flush=True)
            return True, msg
        print(f"Gmail failed, trying Resend: {msg}", flush=True)
    
    # Fallback to Resend
    api_key = os.getenv("RESEND_API_KEY", "").strip()
    from_email = os.getenv("EMAIL_FROM", "onboarding@resend.dev").strip()
    if not api_key:
        return False, "RESEND_API_KEY nathi! Gmail pan set nathi"
    try:
        html = f"""<div style="font-family:Arial; max-width:500px; margin:0 auto; background:white; padding:30px; border-radius:16px; border:2px solid #10B981;">
        <h2>Hi {username}!</h2><p>Reset for: <b>{to_email}</b></p>
        <a href="{reset_link}" style="display:inline-block; background:#059669; color:white; padding:14px 28px; text-decoration:none; border-radius:9999px; font-weight:bold; margin:20px 0;">Reset Password</a>
        <p style="font-size:12px;">Link 15 min: {reset_link}</p></div>"""
        payload = {"from": from_email, "to": [to_email], "subject": f"Reset Password - {username}", "html": html}
        r = requests.post("https://api.resend.com/emails", headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}, json=payload, timeout=20)
        print(f"Resend {r.status_code} FROM:{from_email} TO:{to_email} -> {r.text[:300]}", flush=True)
        if r.status_code in (200,201):
            return True, f"Sent ID: {r.json().get('id','')}"
        else:
            txt = r.text
            if "only send testing emails to your own" in txt:
                return False, f"FREE_LIMIT::Onboarding only sends to owner ajbhai192837465@gmail.com. To send to ALL (ajbhai917325846@gmail.com etc) FREE: Use Gmail method (see steps) OR verify domain at resend.com/domains and set EMAIL_FROM=noreply@yourdomain.com"
            return False, f"Failed {r.status_code}: {txt[:500]}"
    except Exception as e:
        return False, f"Failed: {e}"

def is_valid_6digit(pwd):
    return pwd and len(pwd)==6 and pwd.isdigit()

@app.get("/health")
def health_check():
    return {"status":"ok","mode":"4-PIPE SIMPLE - 63,90,110,150"}

def get_q(report, field, default=0):
    try:
        return getattr(report, field, default) or 0
    except:
        return default

def generate_single_csv(report):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([report.report_title])
    writer.writerow([f"Date: {report.report_date.strftime('%d-%m-%Y')}", f"Area: {report.area_name}", f"Labour: {get_q(report, 'labour_name', '')}"])
    writer.writerow([])
    writer.writerow(["PVC PIPES"])
    writer.writerow(["Sr.No", "Pipe Dia", "Quantity", "UNIT", "Total MTR"])
    writer.writerow([1, "63MM PVC", get_q(report,'qty_63mm'), "6MTR per PIPES", f"{get_q(report,'qty_63mm')*6} MTR"])
    writer.writerow([2, "90MM PVC", get_q(report,'qty_90mm'), "6MTR per PIPES", f"{get_q(report,'qty_90mm')*6} MTR"])
    writer.writerow([3, "110MM PVC", get_q(report,'qty_110mm'), "6MTR per PIPES", f"{get_q(report,'qty_110mm')*6} MTR"])
    pvc = get_q(report,'qty_63mm')+get_q(report,'qty_90mm')+get_q(report,'qty_110mm')
    pvc_mtr = (get_q(report,'qty_63mm')+get_q(report,'qty_90mm')+get_q(report,'qty_110mm'))*6
    writer.writerow([f"PVC Total: {pvc} Qty | {pvc_mtr} MTR"])
    writer.writerow([])
    writer.writerow(["DI PIPES"])
    writer.writerow(["Sr.No", "Pipe Dia", "Quantity", "UNIT", "Total MTR"])
    writer.writerow([1, "150MM DI", get_q(report,'qty_150mm'), "5.5MTR", f"{get_q(report,'qty_150mm')*5.5} MTR"])
    di = get_q(report,'qty_150mm')
    di_mtr = di*5.5
    writer.writerow([f"DI Total: {di} Qty | {di_mtr} MTR"])
    return output.getvalue().encode("utf-8")

def generate_single_excel(report):
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
        wb = Workbook(); ws = wb.active; ws.title = "Report"
        thin = Border(left=Side(style='thin'), right=Side(style='thin'), top=Side(style='thin'), bottom=Side(style='thin'))
        hdr_fill = PatternFill(start_color="10B981", end_color="10B981", fill_type="solid")
        hdr_font = Font(bold=True, color="FFFFFF", size=11)
        ws.merge_cells('A1:D1'); ws['A1'] = report.report_title; ws['A1'].font = Font(bold=True, size=14); ws['A1'].alignment = Alignment(horizontal='center')
        ws.merge_cells('A2:D2'); ws['A2'] = f"Date: {report.report_date.strftime('%d-%m-%Y')} | Area: {report.area_name}"; ws['A2'].alignment = Alignment(horizontal='center')
        ws.append([]); ws.append(["Sr.No", "Pipe Dia", "Quantity", "UNIT"])
        for col in range(1,5):
            cell = ws.cell(row=4, column=col); cell.fill = hdr_fill; cell.font = hdr_font; cell.alignment = Alignment(horizontal='center'); cell.border = thin
        for idx, (dia, qty, unit) in enumerate([("63MM PVC", get_q(report,'qty_63mm'), "6MTR"), ("90MM PVC", get_q(report,'qty_90mm'), "6MTR"), ("110MM PVC", get_q(report,'qty_110mm'), "6MTR"), ("150MM DI", get_q(report,'qty_150mm'), "5.5MTR")], start=1):
            ws.append([idx, dia, qty, unit])
            r = ws.max_row
            for c in range(1,5): ws.cell(row=r, column=c).alignment = Alignment(horizontal='center'); ws.cell(row=r, column=c).border = thin
        ws.append([]); pvc = get_q(report,'qty_63mm')+get_q(report,'qty_90mm')+get_q(report,'qty_110mm'); di = get_q(report,'qty_150mm')
        ws.append(["", "Total PVC", f"{pvc} Qty", ""]); ws.append(["", "Total DI", f"{di} Qty", ""]); ws.append(["", "Grand Total", f"{report.total_qty} Qty", ""])
        for rr in [ws.max_row-2, ws.max_row-1, ws.max_row]:
            for c in range(1,5): ws.cell(row=rr, column=c).font = Font(bold=True); ws.cell(row=rr, column=c).alignment = Alignment(horizontal='center'); ws.cell(row=rr, column=c).border = thin
        ws.column_dimensions['A'].width = 12; ws.column_dimensions['B'].width = 18; ws.column_dimensions['C'].width = 18; ws.column_dimensions['D'].width = 15
        out = io.BytesIO(); wb.save(out); return out.getvalue()
    except Exception:
        return generate_single_csv(report)

def generate_single_pdf(report):
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
        from reportlab.lib import colors
        output = io.BytesIO(); c = canvas.Canvas(output, pagesize=A4); width, height = A4
        # Title - BLACK color as per request
        c.setFillColor(colors.black)
        c.setFont("Helvetica-Bold", 16)
        c.drawCentredString(width/2, height-40, report.report_title)
        c.setFont("Helvetica", 11)
        c.setFillColor(colors.black)
        c.drawCentredString(width/2, height-60, f"Area: {report.area_name or 'No Area'} | Labour: {get_q(report,'labour_name','') or 'No Labour'}")
        c.drawCentredString(width/2, height-75, f"Date: {report.report_date.strftime('%d-%m-%Y')}")
        y = height - 110
        # PVC PIPES - Center - RED COLOR + Space
        y -= 10  # Space above
        c.setFillColor(colors.HexColor("#DC2626"))  # RED
        c.setFont("Helvetica-Bold", 14)
        c.drawCentredString(width/2, y, "PVC PIPES")
        y -= 25  # Space below
        # Header - FIX: UNIT per Pipe in heading, not in values + fix overlap
        c.setFillColor(colors.HexColor("#059669")); c.rect(50, y-5, 500, 25, fill=1, stroke=0)
        c.setFillColor(colors.white); c.setFont("Helvetica-Bold", 9)
        c.drawString(60, y+2, "Sr.No"); c.drawString(110, y+2, "Pipe Dia"); c.drawString(210, y+2, "Quantity"); c.drawString(280, y+2, "UNIT per Pipe"); c.drawString(400, y+2, "Total MTR")
        y -= 30; c.setFont("Helvetica", 11)
        pvc_total = 0
        pvc_mtr_total = 0
        for idx, (dia, qty, unit, mtr) in enumerate([
            ("63MM PVC", get_q(report,'qty_63mm'), "6MTR", get_q(report,'qty_63mm')*6),
            ("90MM PVC", get_q(report,'qty_90mm'), "6MTR", get_q(report,'qty_90mm')*6),
            ("110MM PVC", get_q(report,'qty_110mm'), "6MTR", get_q(report,'qty_110mm')*6)
        ], start=1):
            if idx % 2 == 0: c.setFillColor(colors.HexColor("#ECFDF5")); c.rect(50, y-5, 500, 22, fill=1, stroke=0)
            c.setFillColor(colors.black)
            c.drawString(60, y, str(idx)); c.drawString(110, y, dia); c.drawString(210, y, str(qty)); c.drawString(280, y, unit); c.drawString(400, y, f"{mtr} MTR")
            y -= 22
            pvc_total += qty
            pvc_mtr_total += mtr
        y -= 5
        c.setFillColor(colors.HexColor("#D1FAE5")); c.rect(50, y-5, 500, 22, fill=1, stroke=0)
        c.setFillColor(colors.HexColor("#059669")); c.setFont("Helvetica-Bold", 11)
        c.drawString(70, y+2, f"PVC Total: {pvc_total} Qty | {pvc_mtr_total} MTR")
        y -= 30
        # DI PIPES - Center - RED COLOR + Space
        y -= 15  # Space above
        c.setFillColor(colors.HexColor("#DC2626"))  # RED
        c.setFont("Helvetica-Bold", 14)
        c.drawCentredString(width/2, y, "DI PIPES")
        y -= 25  # Space below
        # DI Header - FIX: UNIT per Pipe
        c.setFillColor(colors.HexColor("#059669")); c.rect(50, y-5, 500, 25, fill=1, stroke=0)
        c.setFillColor(colors.white); c.setFont("Helvetica-Bold", 9)
        c.drawString(60, y+2, "Sr.No"); c.drawString(110, y+2, "Pipe Dia"); c.drawString(210, y+2, "Quantity"); c.drawString(280, y+2, "UNIT per Pipe"); c.drawString(400, y+2, "Total MTR")
        y -= 30; c.setFont("Helvetica", 11)
        di_qty = get_q(report,'qty_150mm')
        di_mtr = di_qty * 5.5
        c.setFillColor(colors.HexColor("#ECFDF5")); c.rect(50, y-5, 500, 22, fill=1, stroke=0)
        c.setFillColor(colors.black)
        c.drawString(70, y, "1"); c.drawString(140, y, "150MM DI"); c.drawString(260, y, str(di_qty)); c.drawString(350, y, "5.5MTR"); c.drawString(430, y, f"{di_mtr} MTR")
        y -= 22
        y -= 5
        c.setFillColor(colors.HexColor("#D1FAE5")); c.rect(50, y-5, 500, 22, fill=1, stroke=0)
        c.setFillColor(colors.HexColor("#059669")); c.setFont("Helvetica-Bold", 11)
        c.drawString(70, y+2, f"DI Total: {di_qty} Qty | {di_mtr} MTR")
        # No Grand Total as per request
        c.showPage(); c.save(); return output.getvalue()
    except Exception as e:
        print(f"PDF error: {e}")
        return generate_single_csv(report)

def generate_month_csv(title, period_text, t63, t90, t110, t150=0):
    output = io.StringIO(); writer = csv.writer(output)
    writer.writerow([title]); writer.writerow([period_text]); writer.writerow([]); writer.writerow(["Sr.No", "Pipe Dia", "Quantity", "UNIT"])
    writer.writerow([1, "63MM PVC", t63, "6MTR per PIPES"]); writer.writerow([2, "90MM PVC", t90, "6MTR per PIPES"]); writer.writerow([3, "110MM PVC", t110, "6MTR per PIPES"]); writer.writerow([4, "150MM DI", t150, "5.5MTR"]); writer.writerow([])
    writer.writerow([f"Total PVC: {t63+t90+t110} Qty"]); writer.writerow([f"Total DI: {t150} Qty"]); writer.writerow([f"Grand Total: {t63+t90+t110+t150} Qty"])
    return output.getvalue().encode("utf-8")

def generate_month_excel(title, period_text, t63, t90, t110, t150=0):
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
        wb = Workbook(); ws = wb.active; ws.title = "Monthly"
        thin = Border(left=Side(style='thin'), right=Side(style='thin'), top=Side(style='thin'), bottom=Side(style='thin'))
        hdr_fill = PatternFill(start_color="10B981", end_color="10B981", fill_type="solid")
        hdr_font = Font(bold=True, color="FFFFFF", size=11)
        ws.merge_cells('A1:D1'); ws['A1'] = title; ws['A1'].font = Font(bold=True, size=14); ws['A1'].alignment = Alignment(horizontal='center')
        ws.merge_cells('A2:D2'); ws['A2'] = period_text; ws['A2'].alignment = Alignment(horizontal='center')
        ws.append([]); ws.append(["Sr.No", "Pipe Dia", "Quantity", "UNIT"])
        r = ws.max_row
        for col in range(1,5): cell = ws.cell(row=r, column=col); cell.fill = hdr_fill; cell.font = hdr_font; cell.alignment = Alignment(horizontal='center'); cell.border = thin
        for idx, (dia, qty, unit) in enumerate([("63MM PVC", t63, "6MTR per PIPES"), ("90MM PVC", t90, "6MTR per PIPES"), ("110MM PVC", t110, "6MTR per PIPES"), ("150MM DI", t150, "5.5MTR")], start=1):
            ws.append([idx, dia, qty, unit]); rr = ws.max_row
            for col in range(1,5): ws.cell(row=rr, column=col).alignment = Alignment(horizontal='center'); ws.cell(row=rr, column=col).border = thin
        ws.append([]); ws.append(["", "Total PVC", f"{t63+t90+t110} Qty", ""]); ws.append(["", "Total DI", f"{t150} Qty", ""]); ws.append(["", "Grand Total", f"{t63+t90+t110+t150} Qty", ""])
        for rr in [ws.max_row-2, ws.max_row-1, ws.max_row]:
            for col in range(1,5): ws.cell(row=rr, column=col).font = Font(bold=True); ws.cell(row=rr, column=col).alignment = Alignment(horizontal='center'); ws.cell(row=rr, column=col).border = thin
        ws.column_dimensions['A'].width = 12; ws.column_dimensions['B'].width = 18; ws.column_dimensions['C'].width = 18; ws.column_dimensions['D'].width = 15
        out = io.BytesIO(); wb.save(out); return out.getvalue()
    except Exception:
        return generate_month_csv(title, period_text, t63, t90, t110, t150)

def generate_month_pdf(title, period_text, t63, t90, t110, t150=0):
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
        c.setFillColor(colors.white); c.setFont("Helvetica-Bold", 11); c.drawString(70, y+2, "Sr.No"); c.drawString(150, y+2, "Pipe Dia"); c.drawString(270, y+2, "Quantity"); c.drawString(390, y+2, "UNIT")
        y -= 30; c.setFont("Helvetica", 11)
        for idx, (dia, qty, unit) in enumerate([("63MM PVC", t63, "6MTR per PIPES"), ("90MM PVC", t90, "6MTR per PIPES"), ("110MM PVC", t110, "6MTR per PIPES"), ("150MM DI", t150, "5.5MTR")], start=1):
            if idx % 2 == 0: c.setFillColor(colors.HexColor("#ECFDF5")); c.rect(50, y-5, 500, 22, fill=1, stroke=0)
            c.setFillColor(colors.black); c.drawString(70, y, str(idx)); c.drawString(150, y, dia); c.drawString(270, y, str(qty)); c.drawString(390, y, unit); y -= 22
        y -= 10; c.setFillColor(colors.HexColor("#D1FAE5")); c.rect(50, y-5, 500, 25, fill=1, stroke=0)
        c.setFillColor(colors.HexColor("#059669")); c.setFont("Helvetica-Bold", 11); c.drawString(70, y+2, f"PVC: {t63+t90+t110} | DI: {t150} | Grand: {t63+t90+t110+t150}")
        c.showPage(); c.save(); return output.getvalue()
    except Exception:
        return generate_month_csv(title, period_text, t63, t90, t110, t150)

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
    print("🚀 FINAL 4-PIPE SIMPLE - 63,90,110,150", flush=True)
    state = {"user": None, "selected_report": None}
    with ui.column().classes("w-full min-h-screen p-0 m-0 gap-0") as root:
        login_view = ui.column().classes("w-full min-h-screen items-center justify-center bg-gradient-to-br from-indigo-900 via-purple-900 to-slate-900 p-3")
        with login_view:
            with ui.card().classes("w-full max-w-sm rounded-3xl shadow-2xl overflow-hidden p-0 border-2 border-green-400/50"):
                with ui.column().classes("w-full bg-gradient-to-r from-emerald-500 via-green-600 to-teal-600 p-4 items-center text-white"):
                    ui.icon("bolt", size="2.5rem")
                    ui.label("6-DIGIT SECURE LOGIN").classes("text-xl font-extrabold")
                    ui.label("4-PIPE PVC+DI").classes("text-xs")
                with ui.column().classes("w-full p-5 bg-white gap-3"):
                    saved_email = app.storage.user.get("saved_email", "")
                    saved_pwd = app.storage.user.get("saved_password", "")
                    email_input = ui.input("Email ID", value=saved_email).props("outlined rounded dense").classes("w-full")
                    pass_input = ui.input("Password (6 digits)", value=saved_pwd, placeholder="6 digits only", password=True, password_toggle_button=True).props("outlined rounded dense maxlength=6").classes("w-full")
                    login_btn = ui.button("⚡ Log In", icon="bolt").props("rounded no-caps").classes("w-full py-2.5 bg-gradient-to-r from-emerald-600 to-green-600 text-white font-bold shadow-lg")
                    status_label = ui.label("").classes("text-xs text-center font-bold text-green-600")
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
            login_view.classes(add="spa-hidden")
            home_view.classes(add="spa-hidden")
            filter_view.classes(remove="spa-hidden")
            filter_detail_view.classes(add="spa-hidden")
            profile_view.classes(add="spa-hidden")
            register_view.classes(add="spa-hidden")
            forgot_view.classes(add="spa-hidden")
            build_filter()

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
                    with ui.column().classes("w-full bg-gradient-to-r from-blue-500 via-indigo-600 to-purple-600 p-5 items-center text-white"):
                        ui.icon("lock_reset", size="2.5rem")
                        ui.label("Forgot Password - FREE").classes("text-xl font-extrabold")
                    with ui.column().classes("w-full p-5 bg-white gap-3"):
                        forgot_email = ui.input("Email ID", placeholder="Enter registered Email").props("outlined rounded dense").classes("w-full")
                        forgot_status = ui.label("").classes("text-xs font-bold text-center w-full")
                        async def send_reset_link():
                            email = (forgot_email.value or "").strip()
                            if not email:
                                forgot_status.set_text("❌ Enter Email ID!")
                                return
                            try:
                                def get_user():
                                    try:
                                        return AppUser.objects.get(email=email)
                                    except AppUser.DoesNotExist:
                                        return None
                                user = await run.io_bound(get_user)
                                if not user:
                                    forgot_status.set_text("❌ Email not registered!")
                                    return
                            except Exception as e:
                                forgot_status.set_text(f"❌ DB Error: {e}")
                                return
                            token = secrets.token_urlsafe(32)
                            if HAS_TOKEN_MODEL:
                                try:
                                    def create_token():
                                        PasswordResetToken.objects.filter(user=user).delete()
                                        PasswordResetToken.objects.create(user=user, token=token)
                                    await run.io_bound(create_token)
                                except Exception as ex:
                                    print(f"Token create fail: {ex}")
                            base_url = os.getenv("RENDER_EXTERNAL_URL", os.getenv("BASE_URL", "https://site-collection.onrender.com"))
                            if "localhost" in base_url or not base_url:
                                base_url = "https://site-collection.onrender.com"
                            reset_link = f"{base_url}/reset/{token}"
                            forgot_status.set_text(f"⏳ Sending mail to {email}... (Gmail FREE)")
                            try:
                                # Run email in background thread - no blocking UI
                                success, msg = await run.io_bound(lambda: send_reset_email_resend_http(email, user.username, reset_link))
                            except Exception as e:
                                success, msg = False, f"Exception: {e}"
                            if success:
                                forgot_status.set_text(f"✅ Mail sent to {email}! Check inbox & spam")
                                ui.notify(f"✅ Mail sent to {email} via Gmail FREE", type="positive", position="top")
                            else:
                                if "FREE_LIMIT" in msg:
                                    forgot_status.set_text(f"✅ Link ready (FREE): {reset_link}")
                                    print(f"FREE LIMIT Link: {reset_link}", flush=True)
                                    try:
                                        with ui.dialog() as dlg, ui.card().classes("p-4 rounded-xl max-w-md"):
                                            ui.label("✅ Reset Link Ready!").classes("font-bold text-green-600")
                                            ui.label(f"FREE method: Link for {email} (15 min valid)").classes("text-xs mt-2")
                                            ui.label(reset_link).classes("text-xs break-all text-blue-600 mt-2 border p-2 rounded bg-blue-50")
                                            ui.button("Open Reset Link", icon="open_in_new", on_click=lambda: ui.navigate.to(reset_link)).props("rounded").classes("bg-blue-600 text-white w-full mt-3")
                                            ui.button("Copy Link", on_click=lambda: ui.clipboard.write(reset_link)).props("outline rounded").classes("w-full mt-1")
                                            ui.button("Close", on_click=dlg.close).props("flat").classes("w-full")
                                        dlg.open()
                                    except Exception as ex:
                                        print(f"Dialog fail: {ex}")
                                else:
                                    forgot_status.set_text(f"❌ {msg}")
                                    print(f"Email fail: {msg}", flush=True)
                        ui.button("Send Reset Link - FREE", icon="send", on_click=send_reset_link).props("rounded no-caps").classes("w-full py-2.5 bg-gradient-to-r from-blue-600 to-indigo-600 text-white font-bold shadow-lg")
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
                with ui.column().classes("w-full max-w-md items-center gap-2"):
                    with ui.row().classes("w-full justify-between items-center mb-2 px-1"):
                        ui.button("Back", icon="arrow_back", on_click=show_login_as_logout).props("flat rounded dense no-caps").classes("back-btn text-xs shadow-sm")
                        today_str = today_ist().isoformat()
                        with ui.row().classes("date-pill items-center justify-center"):
                            home_date_input = ui.input(value=today_str).props("type=date borderless dense").classes("text-xs font-bold")
                        with ui.button(icon="account_circle").props("round unelevated dense").classes("bg-gradient-to-r from-indigo-600 to-purple-600 text-white shadow-md"):
                            with ui.menu().classes("rounded-xl shadow-xl border border-purple-200"):
                                with ui.menu_item(on_click=show_profile).classes("hover:bg-purple-50 font-semibold"):
                                    with ui.row().classes("items-center gap-2"): ui.icon("person", color="purple"); ui.label("Profile")
                                ui.separator()
                                with ui.menu_item(on_click=show_filter).classes("hover:bg-purple-50 font-semibold"):
                                    with ui.row().classes("items-center gap-2"): ui.icon("filter_alt", color="indigo"); ui.label("Filter")
                    with ui.card().classes("w-full rounded-3xl shadow-2xl bg-white/95 p-3 sm:p-5 border-2 border-green-200"):
                        with ui.row().classes("w-full justify-center mb-2.5"):
                            title_input = ui.input(value=user.default_report_title or "Veraval site").props("borderless dense input-class='text-center font-extrabold text-slate-900'").classes("w-full px-2 py-1 rounded-full bg-gradient-to-r from-cyan-200 via-purple-200 to-fuchsia-300 shadow-md border-2 border-purple-300")
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
                                    ui.notify(f"Title saved: {new_title}", type="positive", position="top")
                                except Exception as ex:
                                    print(f"Title save fail: {ex}")
                            # FIXED: Only save on blur or Enter, not on every keystroke - no page reload
                            title_input.on("blur", lambda _: save_title_persist())
                            title_input.on("keydown.enter", lambda _: save_title_persist())
                        def get_areas():
                            if user.id in CACHE["areas"]:
                                return CACHE["areas"][user.id]
                            areas = list(SavedArea.objects.filter(user=user).values_list("area_name", flat=True)[:100])
                            CACHE["areas"][user.id] = areas
                            return areas
                        def get_labours():
                            if "labours" not in CACHE:
                                CACHE["labours"] = {}
                            if user.id in CACHE["labours"]:
                                return CACHE["labours"][user.id]
                            if HAS_LABOUR_MODEL:
                                try:
                                    labours = list(SavedLabour.objects.filter(user=user).values_list("labour_name", flat=True)[:100])
                                except:
                                    labours = []
                            else:
                                labours = []
                            CACHE["labours"][user.id] = labours
                            return labours
                        saved_areas = get_areas()
                        saved_labours = get_labours()
                        # Area + Labour Name side by side - FIXED: No live filtering while typing
                        with ui.row().classes("w-full mb-2.5 gap-2"):
                            with ui.column().classes("flex-1 gap-1"):
                                ui.label("Enter Area *").classes("text-xs font-bold text-green-700 ml-1")
                                area_input = ui.input(placeholder="Type area name...", value="").props("outlined rounded dense color=green").classes("editable-area w-full bg-white font-bold text-sm shadow-sm")
                                with ui.row().classes("w-full gap-1 flex-wrap") as suggestions_row:
                                    def refresh_suggestions():
                                        # FIXED: Show only saved full names, no live filtering on typing
                                        # Suggestion only after save, not while typing S, Su, Sur...
                                        current_saved = get_areas()
                                        suggestions_row.clear()
                                        with suggestions_row:
                                            for area in current_saved[:12]:
                                                def make_click(a=area):
                                                    def click():
                                                        area_input.value = a
                                                        area_input.update()
                                                    return click
                                                ui.button(area, on_click=make_click()).props("flat dense rounded").classes("text-[10px] bg-indigo-50 border border-indigo-200 text-indigo-700 font-bold px-2 py-0")
                                    refresh_suggestions()
                                # NO on_value_change live filtering - Only show after save
                            with ui.column().classes("flex-1 gap-1"):
                                ui.label("Enter Labour Name").classes("text-xs font-bold text-blue-700 ml-1")
                                labour_input = ui.input(placeholder="Type labour name...", value="").props("outlined rounded dense color=blue").classes("editable-area w-full bg-white font-bold text-sm shadow-sm")
                                with ui.row().classes("w-full gap-1 flex-wrap") as labour_suggestions_row:
                                    def refresh_labour_suggestions():
                                        # FIXED: Show only saved full names after save, no live filtering
                                        current_saved = get_labours()
                                        labour_suggestions_row.clear()
                                        with labour_suggestions_row:
                                            for lab in current_saved[:12]:
                                                def make_click(a=lab):
                                                    def click():
                                                        labour_input.value = a
                                                        labour_input.update()
                                                    return click
                                                ui.button(lab, on_click=make_click()).props("flat dense rounded").classes("text-[10px] bg-blue-50 border border-blue-200 text-blue-700 font-bold px-2 py-0")
                                    refresh_labour_suggestions()
                                # NO on_value_change live filtering for labour
                        with ui.row().classes("w-full justify-center items-center gap-1.5 mb-1.5"):
                            ui.icon("bolt", color="green", size="1.3rem"); ui.label("4-PIPE PVC+DI").classes("text-base font-extrabold text-slate-800")
                        with ui.column().classes("w-full rounded-2xl overflow-hidden shadow-lg border-2 border-indigo-900 gap-0"):
                            with ui.grid(columns=4).classes("w-full bg-gradient-to-r from-emerald-500 via-green-500 to-teal-500 text-white font-extrabold text-center"):
                                ui.label("63MM PVC").classes("py-2 text-[10px]"); ui.label("90MM PVC").classes("py-2 text-[10px] border-x-2 border-indigo-900"); ui.label("110MM PVC").classes("py-2 text-[10px] border-r-2 border-indigo-900"); ui.label("150MM DI").classes("py-2 text-[10px]")
                            with ui.grid(columns=4).classes("w-full bg-white text-center items-center"):
                                with ui.column().classes("p-1.5 items-center w-full"): c63 = ui.input(placeholder="Count").props("type=number outlined dense color=green input-class='text-center font-bold text-[11px]' step=0.1").classes("w-full")
                                with ui.column().classes("p-1.5 items-center border-x-2 border-indigo-900 w-full"): c90 = ui.input(placeholder="Count").props("type=number outlined dense color=green input-class='text-center font-bold text-[11px]' step=0.1").classes("w-full")
                                with ui.column().classes("p-1.5 items-center border-r-2 border-indigo-900 w-full"): c110 = ui.input(placeholder="Count").props("type=number outlined dense color=green input-class='text-center font-bold text-[11px]' step=0.1").classes("w-full")
                                with ui.column().classes("p-1.5 items-center w-full"): c150 = ui.input(placeholder="Count").props("type=number outlined dense color=green input-class='text-center font-bold text-[11px]' step=0.1").classes("w-full")
                            with ui.grid(columns=4).classes("w-full bg-green-50 text-center border-y-2 border-indigo-900 items-center"):
                                ui.label("6MTR per PIPES").classes("py-2.5 font-extrabold text-indigo-900 text-[8px]")
                                ui.label("6MTR per PIPES").classes("py-2.5 font-extrabold text-indigo-900 text-[8px] border-x-2 border-indigo-900")
                                ui.label("6MTR per PIPES").classes("py-2.5 font-extrabold text-indigo-900 text-[8px] border-r-2 border-indigo-900")
                                ui.label("5.5MTR").classes("py-2.5 font-extrabold text-indigo-900 text-[8px]")
                            # NEW ROW - Count * MTR = Total MTR - Live multiplication
                            with ui.grid(columns=4).classes("w-full bg-amber-50 text-center border-b-2 border-indigo-900 items-center"):
                                m63_lbl = ui.label("0 MTR").classes("py-2 font-extrabold text-amber-800 text-[10px]")
                                m90_lbl = ui.label("0 MTR").classes("py-2 font-extrabold text-amber-800 text-[10px] border-x-2 border-indigo-900")
                                m110_lbl = ui.label("0 MTR").classes("py-2 font-extrabold text-amber-800 text-[10px] border-r-2 border-indigo-900")
                                m150_lbl = ui.label("0 MTR").classes("py-2 font-extrabold text-amber-800 text-[10px]")
                            with ui.column().classes("w-full gap-0"):
                                with ui.grid(columns=1).classes("w-full bg-gradient-to-r from-slate-900 via-indigo-950 to-slate-900 text-center"):
                                    pvc_total_lbl = ui.label("Total PVC Pipes : 0 Quantity").classes("py-2 font-bold text-green-300 text-[11px] border-b border-white/10")
                                with ui.grid(columns=1).classes("w-full bg-gradient-to-r from-slate-800 via-slate-900 to-slate-800 text-center"):
                                    di_total_lbl = ui.label("Total DI Pipes : 0 Quantity").classes("py-2 font-bold text-cyan-300 text-[11px]")
                                with ui.grid(columns=1).classes("w-full bg-gradient-to-r from-amber-900 to-yellow-900 text-center"):
                                    mtr_total_lbl = ui.label("Total MTR: 0 MTR").classes("py-2 font-bold text-yellow-200 text-[11px]")
                        def parse_qty(val):
                            try:
                                if val in (None, ""):
                                    return 0
                                s = str(val).strip()
                                # Reject negative only, allow decimal like 3.2, 9.9
                                if s.startswith("-"):
                                    return 0
                                v = float(s)
                                if v < 0:
                                    return 0
                                return v
                            except:
                                return 0
                        def is_valid_int(val):
                            # Only integer allowed: 4,7,48,8 - not 3.2
                            try:
                                if val in (None, ""):
                                    return True
                                s = str(val).strip()
                                if "." in s:
                                    return False
                                int(s)
                                return True
                            except:
                                return False
                        def update_live_preview():
                            # Allow decimal like 3.2, 9.9 + No negative check
                            for c in [c63, c90, c110, c150]:
                                if c.value and c.value not in (None, ""):
                                    s = str(c.value).strip()
                                    if s.startswith("-"):
                                        ui.notify("Negative not allowed! -5 not allowed", type="warning", position="top")
                                        c.value = "0"
                                        c.update()
                            q63 = parse_qty(c63.value); q90 = parse_qty(c90.value); q110 = parse_qty(c110.value); q150 = parse_qty(c150.value)
                            pvc_total_lbl.set_text(f"Total PVC Pipes : {q63+q90+q110} Quantity")
                            di_total_lbl.set_text(f"Total DI Pipes : {q150} Quantity")
                            # MTR calculation - NEW: 63,90,110 all 6*count, 150 only 5.5*count
                            m63 = q63 * 6
                            m90 = q90 * 6
                            m110 = q110 * 6
                            m150 = q150 * 5.5
                            total_mtr = m63 + m90 + m110 + m150
                            mtr_total_lbl.set_text(f"Total MTR: {total_mtr} MTR")
                            m63_lbl.set_text(f"{int(m63)} MTR")
                            m90_lbl.set_text(f"{int(m90)} MTR")
                            m110_lbl.set_text(f"{int(m110)} MTR")
                            if m150 == int(m150):
                                m150_lbl.set_text(f"{int(m150)} MTR")
                            else:
                                m150_lbl.set_text(f"{m150} MTR")
                        c63.on_value_change(lambda: update_live_preview()); c90.on_value_change(lambda: update_live_preview()); c110.on_value_change(lambda: update_live_preview()); c150.on_value_change(lambda: update_live_preview())
                        def save_daily_report():
                            q63 = parse_qty(c63.value); q90 = parse_qty(c90.value); q110 = parse_qty(c110.value); q150 = parse_qty(c150.value)
                            try:
                                selected_date = datetime.datetime.strptime((home_date_input.value or "").strip(), "%Y-%m-%d").date()
                            except Exception:
                                selected_date = today_ist()
                            area_val = (area_input.value or "").strip()
                            labour_val = (labour_input.value or "").strip()
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
                            try:
                                DailyReport.objects.create(user=user, report_title=current_title, report_date=selected_date, area_name=area_val, labour_name=labour_val, qty_63mm=q63, qty_90mm=q90, qty_110mm=q110, qty_150mm=q150, total_pvc=q63+q90+q110, total_di=q150, total_qty=q63+q90+q110+q150, price_sum=float(q63+q90+q110+q150))
                            except Exception as ex:
                                print(f"Save with labour failed: {ex}, trying without labour")
                                try:
                                    DailyReport.objects.create(user=user, report_title=current_title, report_date=selected_date, area_name=area_val, qty_63mm=q63, qty_90mm=q90, qty_110mm=q110, qty_150mm=q150, total_pvc=q63+q90+q110, total_di=q150, total_qty=q63+q90+q110+q150, price_sum=float(q63+q90+q110+q150))
                                except Exception as ex2:
                                    DailyReport.objects.create(user=user, report_title=current_title, report_date=selected_date, area_name=area_val, qty_63mm=q63, qty_90mm=q90, qty_110mm=q110, total_qty=q63+q90+q110+q150, price_sum=float(q63+q90+q110+q150))
                            c63.value = ""; c90.value = ""; c110.value = ""; c150.value = ""; area_input.value = ""; labour_input.value = ""; update_live_preview()
                            get_areas(); get_labours(); refresh_suggestions(); refresh_labour_suggestions()
                            ui.notify(f"Saved! Area:{area_val} Labour:{labour_val} PVC:{q63+q90+q110} DI:{q150}", type="positive", position="top")
                        ui.button("⚡ Save", icon="bolt", on_click=save_daily_report).props("rounded no-caps").classes("w-full py-2.5 mt-3 bg-gradient-to-r from-emerald-600 via-green-600 to-teal-600 text-white font-extrabold text-sm shadow-xl")

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
                                    with ui.row().classes("w-full justify-between items-center mb-2 px-1"):
                                        ui.badge(period_text, color="green").classes("text-xs font-bold px-2 py-1"); ui.badge(f"Total: {grand_total} Qty", color="green").classes("text-xs font-bold px-2 py-1")
                                    for report in qs[:50]:
                                        area_display = report.area_name or "No Area"
                                        with ui.card().classes("report-patti w-full rounded-2xl border-2 border-green-200 bg-gradient-to-r from-white to-green-50 p-0 overflow-hidden shadow-md"):
                                            with ui.column().classes("patti-click-area w-full p-3 pb-1").on("click", lambda r=report: show_filter_detail(r)):
                                                with ui.row().classes("w-full justify-between items-center"):
                                                    with ui.row().classes("items-center gap-2"): ui.icon("location_on", color="green", size="1.1rem"); ui.label(area_display).classes("font-extrabold text-sm text-indigo-900")
                                                    ui.badge(f"{report.report_date.strftime('%d-%m-%Y')}", color="grey").classes("text-[10px]")
                                                ui.label(report.report_title).classes("text-xs font-semibold text-slate-700 mt-1 w-full truncate")
                                                with ui.row().classes("w-full justify-between items-center mt-1"):
                                                    ui.label(f"63:{get_q(report,'qty_63mm')} | 90:{get_q(report,'qty_90mm')} | 110:{get_q(report,'qty_110mm')} | 150DI:{get_q(report,'qty_150mm')}").classes("text-[11px] font-bold text-slate-600")
                                                    ui.label(f"Total: {report.total_qty} Qty").classes("text-xs font-extrabold text-emerald-600")
                                            with ui.row().classes("w-full justify-end gap-2 px-3 pb-3 pt-1"):
                                                edit_btn = ui.button("Edit", icon="edit").props("dense flat").classes("edit-mini-btn px-3 py-1")
                                                del_btn = ui.button("Delete", icon="delete").props("dense flat").classes("del-mini-btn px-3 py-1")
                                                with ui.dialog() as edit_dialog, ui.card().classes("rounded-3xl p-0 w-full max-w-md overflow-hidden shadow-2xl max-h-[90vh] overflow-y-auto"):
                                                    with ui.column().classes("w-full p-0 gap-0"):
                                                        with ui.row().classes("w-full bg-gradient-to-r from-blue-500 to-blue-600 p-3 items-center justify-between text-white"):
                                                            ui.label(f"✏ Edit - {area_display}").classes("font-extrabold text-sm text-white")
                                                            ui.button(icon="close", on_click=edit_dialog.close).props("flat round dense color=white").classes("text-white")
                                                        with ui.column().classes("w-full p-4 gap-3 bg-white"):
                                                            ui.label("Date").classes("text-xs font-bold text-slate-700")
                                                            e_date = ui.input(value=report.report_date.isoformat()).props("type=date outlined dense").classes("w-full")
                                                            ui.label("Area Name").classes("text-xs font-bold text-slate-700")
                                                            e_area = ui.input(value=report.area_name).props("outlined dense").classes("w-full font-bold")
                                                            ui.label("Labour Name").classes("text-xs font-bold text-slate-700")
                                                            e_labour = ui.input(value=get_q(report,'labour_name','')).props("outlined dense").classes("w-full font-bold")
                                                            ui.label("Report Title").classes("text-xs font-bold text-slate-700")
                                                            e_title = ui.input(value=report.report_title).props("outlined dense").classes("w-full")
                                                            with ui.grid(columns=4).classes("w-full gap-2"):
                                                                with ui.column().classes("gap-1"):
                                                                    ui.label("63MM PVC").classes("text-xs font-bold text-center")
                                                                    e_63 = ui.input(value=str(get_q(report,'qty_63mm'))).props("type=number outlined dense").classes("w-full")
                                                                with ui.column().classes("gap-1"):
                                                                    ui.label("90MM PVC").classes("text-xs font-bold text-center")
                                                                    e_90 = ui.input(value=str(get_q(report,'qty_90mm'))).props("type=number outlined dense").classes("w-full")
                                                                with ui.column().classes("gap-1"):
                                                                    ui.label("110MM PVC").classes("text-xs font-bold text-center")
                                                                    e_110 = ui.input(value=str(get_q(report,'qty_110mm'))).props("type=number outlined dense").classes("w-full")
                                                                with ui.column().classes("gap-1"):
                                                                    ui.label("150MM DI").classes("text-xs font-bold text-center")
                                                                    e_150 = ui.input(value=str(get_q(report,'qty_150mm'))).props("type=number outlined dense").classes("w-full")
                                                            with ui.row().classes("w-full justify-between gap-3 mt-2"):
                                                                ui.button("Cancel", icon="close", on_click=edit_dialog.close).props("flat rounded").classes("flex-1 bg-slate-100")
                                                                save_edit_btn = ui.button("OK", icon="check").props("rounded").classes("flex-1 bg-blue-600 text-white font-bold")
                                                            def make_save_edit(rpt=report, ed=e_date, ea=e_area, et=e_title, e63=e_63, e90=e_90, e110=e_110, e150=e_150, el=e_labour, dlg=edit_dialog):
                                                                def do_save():
                                                                    try:
                                                                        try:
                                                                            new_date = datetime.datetime.strptime((ed.value or "").strip(), "%Y-%m-%d").date()
                                                                        except:
                                                                            new_date = rpt.report_date
                                                                        new_area = (ea.value or "").strip() or rpt.area_name
                                                                        new_labour = (el.value or "").strip() or get_q(rpt,'labour_name','')
                                                                        new_title = (et.value or "").strip() or rpt.report_title
                                                                        def pq(v):
                                                                            try: return int(float(v)) if v not in (None, "") else 0
                                                                            except: return 0
                                                                        q63 = pq(e63.value); q90 = pq(e90.value); q110 = pq(e110.value); q150 = pq(e150.value)
                                                                        rpt.report_date = new_date
                                                                        rpt.area_name = new_area
                                                                        try:
                                                                            rpt.labour_name = new_labour
                                                                        except:
                                                                            pass
                                                                        rpt.report_title = new_title
                                                                        rpt.qty_63mm = q63; rpt.qty_90mm = q90; rpt.qty_110mm = q110
                                                                        try: rpt.qty_150mm = q150
                                                                        except: pass
                                                                        try: rpt.total_pvc = q63+q90+q110; rpt.total_di = q150
                                                                        except: pass
                                                                        rpt.total_qty = q63+q90+q110+q150
                                                                        rpt.price_sum = float(q63+q90+q110+q150)
                                                                        rpt.save()
                                                                        ui.notify("Updated!", type="positive")
                                                                        dlg.close()
                                                                        load_table_data()
                                                                    except Exception as ex:
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
                                                                            ui.notify("Deleted!", type="positive")
                                                                            dlg.close()
                                                                            load_table_data()
                                                                        except Exception as ex:
                                                                            ui.notify(f"Failed: {ex}", type="negative")
                                                                    return do_del
                                                                confirm_del_btn.on_click(make_del())
                                                del_btn.on_click(del_dialog.open)
                            else:
                                agg = base_qs.aggregate(s63=Sum('qty_63mm'), s90=Sum('qty_90mm'), s110=Sum('qty_110mm'), s150=Sum('qty_150mm')); t63 = agg['s63'] or 0; t90 = agg['s90'] or 0; t110 = agg['s110'] or 0; t150 = agg['s150'] or 0; period_text = f"Full Month: {months[sel_month]} {sel_year}"
                                with table_container:
                                    with ui.row().classes("w-full justify-between items-center mb-2 px-1"):
                                        ui.badge(period_text, color="green").classes("text-xs font-bold px-2 py-1"); ui.badge(f"Total: {t63+t90+t110+t150} Qty", color="green").classes("text-xs font-bold px-2 py-1")
                                    rows = [{"sr_no": 1, "pipe_dia": "63MM PVC", "quantity": t63, "unit": "6MTR per PIPES"}, {"sr_no": 2, "pipe_dia": "90MM PVC", "quantity": t90, "unit": "6MTR per PIPES"}, {"sr_no": 3, "pipe_dia": "110MM PVC", "quantity": t110, "unit": "6MTR per PIPES"}, {"sr_no": 4, "pipe_dia": "150MM DI", "quantity": t150, "unit": "5.5MTR"}]
                                    columns = [{"name": "sr_no", "label": "Sr.No", "field": "sr_no", "align": "center"}, {"name": "pipe_dia", "label": "Pipe Dia", "field": "pipe_dia", "align": "center"}, {"name": "quantity", "label": "Quantity", "field": "quantity", "align": "center"}, {"name": "unit", "label": "UNIT", "field": "unit", "align": "center"}]
                                    ui.table(columns=columns, rows=rows).props("dense flat bordered").classes("w-full rounded-xl shadow-sm border border-green-200 text-xs font-semibold")
                                    with ui.row().classes("w-full justify-center gap-2 mt-2"):
                                        ui.badge(f"Total PVC Pipes: {t63+t90+t110} Qty", color="blue").classes("text-xs font-bold px-2 py-1")
                                        ui.badge(f"Total DI Pipes: {t150} Qty", color="purple").classes("text-xs font-bold px-2 py-1")
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
                        day_select.on_value_change(lambda: load_table_data()); month_select.on_value_change(lambda: load_table_data()); year_select.on_value_change(lambda: load_table_data()); load_table_data()

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
                        with ui.column().classes("w-full rounded-2xl overflow-hidden shadow-lg border-2 border-indigo-900 gap-0 mb-4"):
                            with ui.grid(columns=4).classes("w-full bg-gradient-to-r from-emerald-500 via-green-500 to-teal-500 text-white font-extrabold text-center"):
                                ui.label("63MM PVC").classes("py-2 text-[10px]"); ui.label("90MM PVC").classes("py-2 text-[10px] border-x border-white/30"); ui.label("110MM PVC").classes("py-2 text-[10px] border-r border-white/30"); ui.label("150MM DI").classes("py-2 text-[10px]")
                            with ui.grid(columns=4).classes("w-full bg-white text-center items-center"):
                                ui.label(f"{get_q(report,'qty_63mm')}").classes("py-2 font-extrabold text-xs"); ui.label(f"{get_q(report,'qty_90mm')}").classes("py-2 font-extrabold text-xs border-x border-gray-200"); ui.label(f"{get_q(report,'qty_110mm')}").classes("py-2 font-extrabold text-xs border-r border-gray-200"); ui.label(f"{get_q(report,'qty_150mm')}").classes("py-2 font-extrabold text-xs bg-green-50 text-green-700")
                            with ui.grid(columns=4).classes("w-full bg-green-50 text-center border-y border-indigo-900 items-center"):
                                ui.label(f"{int(get_q(report,'qty_63mm')*6)} MTR").classes("py-1.5 font-bold text-[10px]"); ui.label(f"{int(get_q(report,'qty_90mm')*6)} MTR").classes("py-1.5 font-bold text-[10px] border-x border-gray-200"); ui.label(f"{int(get_q(report,'qty_110mm')*6)} MTR").classes("py-1.5 font-bold text-[10px] border-r border-gray-200"); ui.label(f"{get_q(report,'qty_150mm')*5.5} MTR").classes("py-1.5 font-bold text-[10px] bg-green-50")
                            with ui.grid(columns=2).classes("w-full bg-gradient-to-r from-slate-900 via-indigo-950 to-slate-900 text-white text-center items-center"):
                                pvc = get_q(report,'qty_63mm')+get_q(report,'qty_90mm')+get_q(report,'qty_110mm')
                                di = get_q(report,'qty_150mm')
                                ui.label(f"Total PVC Pipes: {pvc} Qty").classes("py-2 font-bold text-green-300 text-[10px] border-r border-white/10")
                                ui.label(f"Total DI Pipes: {di} Qty").classes("py-2 font-bold text-cyan-300 text-[10px]")
                            # Grand Total REMOVED - Only PVC and DI separate as per user request
                            # with ui.grid(columns=1).classes("w-full bg-gradient-to-r from-emerald-900 to-teal-900 text-center"):
                            #     gt = pvc + di
                            #     ui.label(f"Grand Total: {gt} Quantity").classes("py-2.5 font-extrabold text-white text-sm")
                        with ui.column().classes("w-full bg-gray-50 rounded-xl p-3 border border-gray-200 mb-3"):
                            ui.label(f"📅 Date: {report.report_date.strftime('%d-%m-%Y')}").classes("text-xs font-bold text-slate-700")
                            ui.label(f"📍 Area: {report.area_name}").classes("text-xs font-bold text-slate-700")
                            ui.label(f"👷 Labour: {get_q(report,'labour_name','') or 'No Labour'}").classes("text-xs font-bold text-slate-700")
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
    ui.run(host="0.0.0.0", port=PORT, title="4-PIPE SIMPLE", storage_secret=STORAGE_SECRET, reload=False, show=False, dark=False)
