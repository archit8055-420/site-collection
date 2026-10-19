import os, datetime, csv, io, secrets, hashlib, traceback, requests
print("🚀 FINAL RESEND HTTP Loading...", flush=True)
os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"
from nicegui import ui, app, run
CACHE = {"users": {}, "areas": {}, "pwd_verified": {}}
from db_setup import init_django
init_django()
from zoneinfo import ZoneInfo
IST = ZoneInfo("Asia/Kolkata")  # India
from models_app.models import AppUser, SavedArea, DailyReport
# ================= FAST INDEX - 30ms - Biju naam =================
from django.db import connection

def ensure_neon_fast():
    """Neon ma Index - Data na ude - Fakt FAST - 30ms"""
    try:
        with connection.cursor() as cursor:
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_fast_email ON models_app_appuser (email);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_fast_user_date ON models_app_dailyreport (user_id, report_date);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_fast_date ON models_app_dailyreport (report_date);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_fast_area ON models_app_savedarea (user_id);")
            print("✅ FAST INDEX OK - 30ms", flush=True)
    except Exception as e:
        print(f"Index skip: {e}", flush=True)

# Auto run - Table na banave - Fakt Index
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

def send_reset_email_resend_http(to_email, username, reset_link):
    api_key = os.getenv("RESEND_API_KEY", "").strip()
    from_email = os.getenv("EMAIL_FROM", "onboarding@resend.dev").strip()
    print(f"📧 RESEND HTTP: FROM={from_email} TO={to_email} KEY={bool(api_key)}", flush=True)
    if not api_key:
        return False, "RESEND_API_KEY nathi! https://resend.com thi free key lo ane Render Env ma nakho"
    try:
        html = f"""<div style="font-family:Arial; max-width:500px; margin:0 auto; background:white; padding:30px; border-radius:16px; border:1px solid #e5e7eb;">
<h2 style="color:#059669;">Hi {username}!</h2>
<p>Reset your <b>6-digit password</b> for: <b>{to_email}</b></p>
<a href="{reset_link}" style="display:inline-block; background:#059669; color:white; padding:14px 28px; text-decoration:none; border-radius:9999px; font-weight:bold; margin:20px 0;">Reset Password</a>
<p style="font-size:12px; color:#666;">Valid 15 min. 6-digit only.</p>
</div>"""
        payload = {"from": from_email, "to": [to_email], "subject": f"Reset Password - {username}", "html": html}
        r = requests.post("https://api.resend.com/emails", headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}, json=payload, timeout=20)
        print(f"Resend {r.status_code} {r.text[:500]}", flush=True)
        if r.status_code in (200,201):
            return True, f"Sent via Resend HTTP ID: {r.json().get('id','')}"
        else:
            return False, f"Resend Failed {r.status_code}: {r.text[:500]}"
    except Exception as e:
        return False, f"Resend HTTP Failed: {e} {traceback.format_exc()[:800]}"

def is_valid_6digit(pwd):
    return pwd and len(pwd)==6 and pwd.isdigit()

from fastapi import Request
@app.get("/health")
def health_check():
    return {"status":"ok","mode":"Resend HTTP - 100% Working on Render Free - Like Supabase","resend_configured": bool(os.getenv("RESEND_API_KEY","").strip()), "gmail_configured": True, "token_model": HAS_TOKEN_MODEL}

@app.get("/test-email-debug")
def test_email_debug(to: str = "ajbhai192837465@gmail.com"):
    link = f"{os.getenv('BASE_URL','https://site-collection.onrender.com')}/reset/TEST123?email={to}"
    ok, msg = send_reset_email_resend_http(to, "Test", link)
    return {"to": to, "success": ok, "message": msg, "resend_key_set": bool(os.getenv("RESEND_API_KEY","").strip()), "email_from": os.getenv("EMAIL_FROM","onboarding@resend.dev"), "mode":"Resend HTTP API"}


def is_valid_6digit(pwd):
    return pwd and len(pwd)==6 and pwd.isdigit()

    return pwd and len(pwd) == 6 and pwd.isdigit()

def generate_single_csv(report):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([report.report_title])
    writer.writerow([f"Date: {report.report_date.strftime('%d-%m-%Y')}", f"Area: {report.area_name}"])
    writer.writerow(["Sr.No", "Pipe Dia", "Quantity", "UNIT"])
    writer.writerow([1, "63MM", report.qty_63mm, f"{report.qty_63mm} MTR"])
    writer.writerow([2, "90MM", report.qty_90mm, f"{report.qty_90mm} MTR"])
    writer.writerow([3, "110MM", report.qty_110mm, f"{report.qty_110mm} MTR"])
    writer.writerow([])
    writer.writerow(["Grand Total", "", report.total_qty, f"{report.total_qty} MTR"])
    return output.getvalue().encode("utf-8")

def generate_single_excel(report):
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
        wb = Workbook(); ws = wb.active; ws.title = "Report"
        thin_border = Border(left=Side(style='thin'), right=Side(style='thin'), top=Side(style='thin'), bottom=Side(style='thin'))
        header_fill = PatternFill(start_color="10B981", end_color="10B981", fill_type="solid")
        header_font = Font(bold=True, color="FFFFFF", size=11)
        ws.merge_cells('A1:D1'); ws['A1'] = report.report_title; ws['A1'].font = Font(bold=True, size=14); ws['A1'].alignment = Alignment(horizontal='center', vertical='center')
        ws.merge_cells('A2:D2'); ws['A2'] = f"Date: {report.report_date.strftime('%d-%m-%Y')} | Area: {report.area_name or 'No Area'}"; ws['A2'].font = Font(bold=True, size=10); ws['A2'].alignment = Alignment(horizontal='center', vertical='center')
        ws.append([]); ws.append(["Sr.No", "Pipe Dia", "Quantity", "UNIT"])
        for col in range(1,5):
            cell = ws.cell(row=4, column=col); cell.fill = header_fill; cell.font = header_font; cell.alignment = Alignment(horizontal='center', vertical='center'); cell.border = thin_border
        for idx, (dia, qty) in enumerate([("63MM", report.qty_63mm), ("90MM", report.qty_90mm), ("110MM", report.qty_110mm)], start=1):
            ws.append([idx, dia, qty, f"{qty} MTR"]); r = ws.max_row
            for c in range(1,5): ws.cell(row=r, column=c).alignment = Alignment(horizontal='center', vertical='center'); ws.cell(row=r, column=c).border = thin_border
        ws.append([]); ws.append(["", "", "Grand Total", f"{report.total_qty} MTR"])
        r = ws.max_row
        for c in range(1,5): ws.cell(row=r, column=c).font = Font(bold=True); ws.cell(row=r, column=c).alignment = Alignment(horizontal='center', vertical='center'); ws.cell(row=r, column=c).border = thin_border
        ws.column_dimensions['A'].width = 12; ws.column_dimensions['B'].width = 15; ws.column_dimensions['C'].width = 12; ws.column_dimensions['D'].width = 15
        output = io.BytesIO(); wb.save(output); return output.getvalue()
    except Exception:
        return generate_single_csv(report)

def generate_single_pdf(report):
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
        from reportlab.lib import colors
        output = io.BytesIO(); c = canvas.Canvas(output, pagesize=A4); width, height = A4
        c.setFillColor(colors.HexColor("#10B981")); c.rect(0, height-80, width, 80, fill=1, stroke=0)
        c.setFillColor(colors.white); c.setFont("Helvetica-Bold", 18); c.drawCentredString(width/2, height-35, report.report_title)
        c.setFont("Helvetica", 11); c.drawCentredString(width/2, height-55, f"Area: {report.area_name or 'No Area'} | Date: {report.report_date.strftime('%d-%m-%Y')}")
        y = height - 120
        c.setFillColor(colors.HexColor("#059669")); c.rect(50, y-5, 500, 25, fill=1, stroke=0)
        c.setFillColor(colors.white); c.setFont("Helvetica-Bold", 12); c.drawString(70, y+2, "Sr.No"); c.drawString(150, y+2, "Pipe Dia"); c.drawString(270, y+2, "Quantity"); c.drawString(390, y+2, "UNIT")
        y -= 30; c.setFont("Helvetica", 12)
        for idx, (dia, qty) in enumerate([("63MM", report.qty_63mm), ("90MM", report.qty_90mm), ("110MM", report.qty_110mm)], start=1):
            if idx % 2 == 0: c.setFillColor(colors.HexColor("#ECFDF5")); c.rect(50, y-5, 500, 22, fill=1, stroke=0)
            c.setFillColor(colors.black); c.drawString(70, y, str(idx)); c.drawString(150, y, dia); c.drawString(270, y, str(qty)); c.drawString(390, y, f"{qty} MTR"); y -= 22
        y -= 10; c.setFillColor(colors.HexColor("#D1FAE5")); c.rect(50, y-5, 500, 25, fill=1, stroke=0)
        c.setFillColor(colors.HexColor("#059669")); c.setFont("Helvetica-Bold", 13); c.drawString(70, y+2, f"Grand Total: {report.total_qty} MTR")
        c.showPage(); c.save(); return output.getvalue()
    except Exception:
        return generate_single_csv(report)

def generate_month_csv(title, period_text, t63, t90, t110):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([title]); writer.writerow([period_text]); writer.writerow([f"Generated: {datetime.datetime.now(IST).strftime('%d-%m-%Y %H:%M:%S')}"]); writer.writerow([])
    writer.writerow(["Sr.No", "Pipe Dia", "Quantity", "UNIT"])
    writer.writerow([1, "63MM", t63, f"{t63} MTR"]); writer.writerow([2, "90MM", t90, f"{t90} MTR"]); writer.writerow([3, "110MM", t110, f"{t110} MTR"]); writer.writerow([])
    writer.writerow(["Grand Total", "", t63+t90+t110, f"{t63+t90+t110} MTR"])
    return output.getvalue().encode("utf-8")

def generate_month_excel(title, period_text, t63, t90, t110):
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
        wb = Workbook(); ws = wb.active; ws.title = "Monthly Report"
        thin = Border(left=Side(style='thin'), right=Side(style='thin'), top=Side(style='thin'), bottom=Side(style='thin'))
        hdr_fill = PatternFill(start_color="10B981", end_color="10B981", fill_type="solid")
        hdr_font = Font(bold=True, color="FFFFFF", size=11)
        ws.merge_cells('A1:D1'); ws['A1'] = title; ws['A1'].font = Font(bold=True, size=14); ws['A1'].alignment = Alignment(horizontal='center', vertical='center')
        ws.merge_cells('A2:D2'); ws['A2'] = period_text; ws['A2'].font = Font(bold=True, size=11); ws['A2'].alignment = Alignment(horizontal='center', vertical='center')
        ws.merge_cells('A3:D3'); ws['A3'] = f"Generated: {datetime.datetime.now(IST).strftime('%d-%m-%Y %H:%M:%S')}"; ws['A3'].alignment = Alignment(horizontal='center', vertical='center')
        ws.append([]); ws.append(["Sr.No", "Pipe Dia", "Quantity", "UNIT"])
        r = ws.max_row
        for col in range(1,5):
            cell = ws.cell(row=r, column=col); cell.fill = hdr_fill; cell.font = hdr_font; cell.alignment = Alignment(horizontal='center', vertical='center'); cell.border = thin
        for idx, (dia, qty) in enumerate([("63MM", t63), ("90MM", t90), ("110MM", t110)], start=1):
            ws.append([idx, dia, qty, f"{qty} MTR"]); rr = ws.max_row
            for col in range(1,5): ws.cell(row=rr, column=col).alignment = Alignment(horizontal='center', vertical='center'); ws.cell(row=rr, column=col).border = thin
        ws.append([]); ws.append(["", "", "Grand Total", f"{t63+t90+t110} MTR"])
        rr = ws.max_row
        for col in range(1,5): ws.cell(row=rr, column=col).font = Font(bold=True); ws.cell(row=rr, column=col).alignment = Alignment(horizontal='center', vertical='center'); ws.cell(row=rr, column=col).border = thin
        ws.column_dimensions['A'].width = 12; ws.column_dimensions['B'].width = 15; ws.column_dimensions['C'].width = 12; ws.column_dimensions['D'].width = 18
        out = io.BytesIO(); wb.save(out); return out.getvalue()
    except Exception:
        return generate_month_csv(title, period_text, t63, t90, t110)

def generate_month_pdf(title, period_text, t63, t90, t110):
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
        for idx, (dia, qty) in enumerate([("63MM", t63), ("90MM", t90), ("110MM", t110)], start=1):
            if idx % 2 == 0: c.setFillColor(colors.HexColor("#ECFDF5")); c.rect(50, y-5, 500, 22, fill=1, stroke=0)
            c.setFillColor(colors.black); c.drawString(70, y, str(idx)); c.drawString(150, y, dia); c.drawString(270, y, str(qty)); c.drawString(390, y, f"{qty} MTR"); y -= 22
        y -= 10; c.setFillColor(colors.HexColor("#D1FAE5")); c.rect(50, y-5, 500, 25, fill=1, stroke=0)
        c.setFillColor(colors.HexColor("#059669")); c.setFont("Helvetica-Bold", 12); c.drawString(70, y+2, f"Grand Total: {t63+t90+t110} MTR")
        c.showPage(); c.save(); return output.getvalue()
    except Exception:
        return generate_month_csv(title, period_text, t63, t90, t110)

ui.add_css("""
    .spa-hidden { display: none !important; }
    .report-patti { transition: all 0.15s; cursor: pointer; }
    .report-patti:hover { transform: translateY(-2px); box-shadow: 0 8px 20px rgba(16,185,129,0.2); border-color: #10B981 !important; }
    .editable-area .q-field__control { min-height: 48px !important; border-radius: 12px !important; }
    .editable-area input { font-weight: 700 !important; font-size: 14px !important; }
    .back-btn { background-color: #d4821e !important; color: black !important; border: 2px solid #b56a17 !important; border-radius: 20px !important; font-weight: bold !important; }
    .back-btn .q-btn__content { color: black !important; }
    .back-btn .q-icon { color: black !important; }
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
    .forgot-link:hover { text-decoration: underline !important; color: #1d4ed8 !important; }
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
                            ui.icon("timer_off", size="2rem", color="red")
                            ui.label("Link Expired! (15 min over)").classes("text-red-600 font-bold text-center w-full")
                            ui.button("Go to Login", icon="login", on_click=lambda: ui.navigate.to("/")).props("rounded no-caps").classes("w-full mt-2 bg-blue-600 text-white font-bold")
                            return
                        user = db_token_obj.user
                        email = user.email
                    else:
                        raise Exception("No DB model")
                except Exception as e:
                    ui.icon("error", size="2rem", color="red")
                    ui.label("Invalid or Expired Link!").classes("text-red-600 font-bold text-center w-full")
                    ui.label(f"Try new Forgot request").classes("text-[11px] text-center")
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
                        status_lbl.set_text("❌ Password must be exactly 6 digits! (e.g., 123456)")
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
                            ui.label("You can now log in with 6-digit password").classes("text-xs font-bold text-slate-600 text-center w-full mt-1")
                            ui.button("Go to Login", icon="login", on_click=lambda: ui.navigate.to("/")).props("rounded no-caps").classes("w-full mt-4 bg-gradient-to-r from-emerald-600 to-green-600 text-white font-bold py-2.5 shadow-lg")
                    except Exception as e:
                        status_lbl.set_text(f"❌ Failed: {e}")
                ui.button("Confirm (6-digit)", icon="check", on_click=do_confirm_reset).props("rounded no-caps").classes("w-full mt-2 bg-gradient-to-r from-emerald-600 to-green-600 text-white font-bold py-2.5 shadow-lg")

@ui.page("/")
def main_spa_page():
    print("🚀 FINAL FREE GMAIL - Login Fixed", flush=True)
    state = {"user": None, "selected_report": None}
    with ui.column().classes("w-full min-h-screen p-0 m-0 gap-0") as root:
        login_view = ui.column().classes("w-full min-h-screen items-center justify-center bg-gradient-to-br from-indigo-900 via-purple-900 to-slate-900 p-3")
        with login_view:
            with ui.card().classes("w-full max-w-sm rounded-3xl shadow-2xl overflow-hidden p-0 border-2 border-green-400/50"):
                with ui.column().classes("w-full bg-gradient-to-r from-emerald-500 via-green-600 to-teal-600 p-4 items-center text-white"):
                    ui.icon("bolt", size="2.5rem")
                    ui.label("6-DIGIT SECURE LOGIN").classes("text-xl font-extrabold")
                    ui.label("⚡ FREE Gmail - No Money").classes("text-xs")
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
            login_view.classes(remove="spa-hidden")
            home_view.classes(add="spa-hidden")
            filter_view.classes(add="spa-hidden")
            filter_detail_view.classes(add="spa-hidden")
            profile_view.classes(add="spa-hidden")
            register_view.classes(add="spa-hidden")
            forgot_view.classes(add="spa-hidden")

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
                        ui.label("Supabase jevu j - Tarat mail!").classes("text-xs")
                    with ui.column().classes("w-full p-5 bg-white gap-3"):
                        forgot_email = ui.input("Email ID", placeholder="Enter registered Email").props("outlined rounded dense").classes("w-full")
                        forgot_status = ui.label("").classes("text-xs font-bold text-center w-full")
                        def send_reset_link():
                            email = (forgot_email.value or "").strip()
                            if not email:
                                forgot_status.set_text("❌ Enter Email ID!")
                                return
                            try:
                                user = AppUser.objects.get(email=email)
                            except AppUser.DoesNotExist:
                                forgot_status.set_text("❌ Email not registered!")
                                return
                            token = secrets.token_urlsafe(32)
                            if HAS_TOKEN_MODEL:
                                PasswordResetToken.objects.filter(user=user).delete()
                                PasswordResetToken.objects.create(user=user, token=token)
                            base_url = os.getenv("RENDER_EXTERNAL_URL", os.getenv("BASE_URL", "https://site-collection.onrender.com"))
                            if "localhost" in base_url or not base_url:
                                base_url = "https://site-collection.onrender.com"
                            reset_link = f"{base_url}/reset/{token}"
                            forgot_status.set_text("⏳ Sending mail... (FREE Gmail)")
                            success, msg = send_reset_email_resend_http(email, user.username, reset_link)
                            if success:
                                forgot_status.set_text("✅ Mail sent! Check inbox & spam - 15 min valid (FREE)")
                            else:
                                forgot_status.set_text(f"❌ {msg}")
                            print(f"🔑 FREE RESET {email}: {reset_link} -> {msg}", flush=True)
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
                        today_str = datetime.date.today().isoformat()
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
                            title_input = ui.input(value=user.default_report_title).props("borderless dense input-class='text-center font-extrabold text-slate-900'").classes("w-full px-2 py-1 rounded-full bg-gradient-to-r from-cyan-200 via-purple-200 to-fuchsia-300 shadow-md border-2 border-purple-300")
                            def save_title_persist(e):
                                new_title = (e.value if hasattr(e, 'value') else title_input.value or "").strip()
                                if not new_title or new_title == user.default_report_title:
                                    return
                                try:
                                    user.default_report_title = new_title
                                    user.save(update_fields=['default_report_title'])
                                    CACHE["users"][user.email] = user
                                    state["user"] = user
                                except Exception:
                                    pass
                            title_input.on_value_change(save_title_persist)
                        def get_areas():
                            if user.id in CACHE["areas"]:
                                return CACHE["areas"][user.id]
                            areas = list(SavedArea.objects.filter(user=user).values_list("area_name", flat=True)[:100])
                            CACHE["areas"][user.id] = areas
                            return areas
                        saved_areas = get_areas()
                        with ui.column().classes("w-full mb-2.5 gap-1"):
                            ui.label("Enter Area *").classes("text-xs font-bold text-green-700 ml-1")
                            area_input = ui.input(placeholder="Type area name...", value="").props("outlined rounded dense color=green").classes("editable-area w-full bg-white font-bold text-sm shadow-sm")
                            with ui.row().classes("w-full gap-1 flex-wrap") as suggestions_row:
                                def refresh_suggestions():
                                    suggestions_row.clear()
                                    with suggestions_row:
                                        for area in saved_areas[:8]:
                                            def make_click(a=area):
                                                def click():
                                                    area_input.value = a
                                                    area_input.update()
                                                return click
                                            ui.button(area, on_click=make_click()).props("flat dense rounded").classes("text-[10px] bg-indigo-50 border border-indigo-200 text-indigo-700 font-bold px-2 py-0")
                                refresh_suggestions()
                            def on_area_save(e):
                                val = (e.value or "").strip() if hasattr(e, 'value') else (area_input.value or "").strip()
                                if val and val not in saved_areas:
                                    SavedArea.objects.get_or_create(user=user, area_name=val)
                                    CACHE["areas"].pop(user.id, None)
                                    refresh_suggestions()
                            area_input.on_value_change(on_area_save)
                        with ui.row().classes("w-full justify-center items-center gap-1.5 mb-1.5"):
                            ui.icon("bolt", color="green", size="1.3rem"); ui.label("Pipe Sizes").classes("text-base font-extrabold text-slate-800")
                        with ui.column().classes("w-full rounded-2xl overflow-hidden shadow-lg border-2 border-indigo-900 gap-0"):
                            with ui.grid(columns=3).classes("w-full bg-gradient-to-r from-emerald-500 via-green-500 to-teal-500 text-white font-extrabold text-center"):
                                ui.label("63MM").classes("py-2 text-xs"); ui.label("90MM").classes("py-2 text-xs border-x-2 border-indigo-900"); ui.label("110MM").classes("py-2 text-xs")
                            with ui.grid(columns=3).classes("w-full bg-white text-center items-center"):
                                with ui.column().classes("p-1.5 items-center w-full"): c63 = ui.input(placeholder="Count").props("type=number outlined dense color=green input-class='text-center font-bold text-xs'").classes("w-full")
                                with ui.column().classes("p-1.5 items-center border-x-2 border-indigo-900 w-full"): c90 = ui.input(placeholder="Count").props("type=number outlined dense color=green input-class='text-center font-bold text-xs'").classes("w-full")
                                with ui.column().classes("p-1.5 items-center w-full"): c110 = ui.input(placeholder="Count").props("type=number outlined dense color=green input-class='text-center font-bold text-xs'").classes("w-full")
                            with ui.grid(columns=3).classes("w-full bg-green-50 text-center border-b-2 border-indigo-900 items-center"):
                                u63_lbl = ui.label("UNIT").classes("py-2.5 font-extrabold text-indigo-900 text-xs")
                                u90_lbl = ui.label("UNIT").classes("py-2.5 font-extrabold text-indigo-900 text-xs border-x-2 border-indigo-900")
                                u110_lbl = ui.label("UNIT").classes("py-2.5 font-extrabold text-indigo-900 text-xs")
                            with ui.grid(columns=2).classes("w-full bg-gradient-to-r from-slate-900 via-indigo-950 to-slate-900 text-white text-center items-center"):
                                ui.label("SUMMARY").classes("py-2.5 font-bold text-green-300 text-xs")
                                total_lbl = ui.label("Total: 0 MTR").classes("py-2.5 font-extrabold text-cyan-300 text-xs")
                        def parse_qty(val):
                            try: return int(val) if val not in (None, "") else 0
                            except ValueError: return 0
                        def update_live_preview():
                            q63 = parse_qty(c63.value); q90 = parse_qty(c90.value); q110 = parse_qty(c110.value)
                            u63_lbl.set_text(f"{q63} MTR" if c63.value not in (None, "") else "UNIT")
                            u90_lbl.set_text(f"{q90} MTR" if c90.value not in (None, "") else "UNIT")
                            u110_lbl.set_text(f"{q110} MTR" if c110.value not in (None, "") else "UNIT")
                            total = q63 + q90 + q110; total_lbl.set_text(f"Total: {total} MTR")
                        c63.on_value_change(lambda: update_live_preview()); c90.on_value_change(lambda: update_live_preview()); c110.on_value_change(lambda: update_live_preview())
                        def save_daily_report():
                            q63 = parse_qty(c63.value); q90 = parse_qty(c90.value); q110 = parse_qty(c110.value)
                            try:
                                selected_date = datetime.datetime.strptime((home_date_input.value or "").strip(), "%Y-%m-%d").date()
                            except Exception:
                                try:
                                    selected_date = datetime.datetime.strptime((home_date_input.value or "").strip(), "%d-%m-%Y").date()
                                except Exception:
                                    selected_date = datetime.date.today()
                            area_val = (area_input.value or "").strip()
                            if not area_val: ui.notify("Please Enter Area!", type="warning", position="top"); return
                            if area_val not in (CACHE["areas"].get(user.id, [])):
                                SavedArea.objects.get_or_create(user=user, area_name=area_val)
                                CACHE["areas"].pop(user.id, None)
                            current_title = (title_input.value or "").strip() or user.default_report_title
                            if current_title != user.default_report_title:
                                user.default_report_title = current_title
                                user.save(update_fields=['default_report_title'])
                                CACHE["users"][user.email] = user
                            DailyReport.objects.create(user=user, report_title=current_title, report_date=selected_date, area_name=area_val, qty_63mm=q63, qty_90mm=q90, qty_110mm=q110, total_qty=q63+q90+q110, price_sum=float(q63+q90+q110))
                            c63.value = ""; c90.value = ""; c110.value = ""; area_input.value = ""; update_live_preview()
                            get_areas(); refresh_suggestions()
                            ui.notify("Saved!", type="positive", position="top")
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
            today = datetime.date.today(); months = {1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun", 7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec"}; years = {y: str(y) for y in range(today.year - 5, today.year + 2)}
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
                                        ui.badge(period_text, color="green").classes("text-xs font-bold px-2 py-1"); ui.badge(f"Reports: {qs.count()} | Total: {grand_total} MTR", color="green").classes("text-xs font-bold px-2 py-1")
                                    for report in qs[:50]:
                                        area_display = report.area_name or "No Area"
                                        with ui.card().classes("report-patti w-full rounded-2xl border-2 border-green-200 bg-gradient-to-r from-white to-green-50 p-0 overflow-hidden shadow-md"):
                                            with ui.column().classes("patti-click-area w-full p-3 pb-1").on("click", lambda r=report: show_filter_detail(r)):
                                                with ui.row().classes("w-full justify-between items-center"):
                                                    with ui.row().classes("items-center gap-2"): ui.icon("location_on", color="green", size="1.1rem"); ui.label(area_display).classes("font-extrabold text-sm text-indigo-900")
                                                    ui.badge(f"{report.report_date.strftime('%d-%m-%Y')}", color="grey").classes("text-[10px]")
                                                ui.label(report.report_title).classes("text-xs font-semibold text-slate-700 mt-1 w-full truncate")
                                                with ui.row().classes("w-full justify-between items-center mt-1"):
                                                    ui.label(f"63:{report.qty_63mm} | 90:{report.qty_90mm} | 110:{report.qty_110mm}").classes("text-[11px] font-bold text-slate-600")
                                                    ui.label(f"Total: {report.total_qty} MTR").classes("text-xs font-extrabold text-emerald-600")
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
                                                            ui.label("Report Title").classes("text-xs font-bold text-slate-700")
                                                            e_title = ui.input(value=report.report_title).props("outlined dense").classes("w-full")
                                                            with ui.grid(columns=3).classes("w-full gap-2"):
                                                                with ui.column().classes("gap-1"):
                                                                    ui.label("63MM").classes("text-xs font-bold text-center")
                                                                    e_63 = ui.input(value=str(report.qty_63mm)).props("type=number outlined dense").classes("w-full")
                                                                with ui.column().classes("gap-1"):
                                                                    ui.label("90MM").classes("text-xs font-bold text-center")
                                                                    e_90 = ui.input(value=str(report.qty_90mm)).props("type=number outlined dense").classes("w-full")
                                                                with ui.column().classes("gap-1"):
                                                                    ui.label("110MM").classes("text-xs font-bold text-center")
                                                                    e_110 = ui.input(value=str(report.qty_110mm)).props("type=number outlined dense").classes("w-full")
                                                            with ui.row().classes("w-full justify-between gap-3 mt-2"):
                                                                ui.button("Cancel", icon="close", on_click=edit_dialog.close).props("flat rounded").classes("flex-1 bg-slate-100")
                                                                save_edit_btn = ui.button("OK", icon="check").props("rounded").classes("flex-1 bg-blue-600 text-white font-bold")
                                                            def make_save_edit(rpt=report, ed=e_date, ea=e_area, et=e_title, e63=e_63, e90=e_90, e110=e_110, dlg=edit_dialog):
                                                                def do_save():
                                                                    try:
                                                                        try:
                                                                            new_date = datetime.datetime.strptime((ed.value or "").strip(), "%Y-%m-%d").date()
                                                                        except:
                                                                            new_date = rpt.report_date
                                                                        new_area = (ea.value or "").strip() or rpt.area_name
                                                                        new_title = (et.value or "").strip() or rpt.report_title
                                                                        def pq(v):
                                                                            try: return int(v) if v not in (None, "") else 0
                                                                            except: return 0
                                                                        q63 = pq(e63.value); q90 = pq(e90.value); q110 = pq(e110.value)
                                                                        rpt.report_date = new_date
                                                                        rpt.area_name = new_area
                                                                        rpt.report_title = new_title
                                                                        rpt.qty_63mm = q63
                                                                        rpt.qty_90mm = q90
                                                                        rpt.qty_110mm = q110
                                                                        rpt.total_qty = q63+q90+q110
                                                                        rpt.price_sum = float(q63+q90+q110)
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
                                                            ui.label(f"Area: {report.area_name} | Date: {report.report_date.strftime('%d-%m-%Y')} | Total: {report.total_qty} MTR").classes("text-xs text-slate-600")
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
                                agg = base_qs.aggregate(s63=Sum('qty_63mm'), s90=Sum('qty_90mm'), s110=Sum('qty_110mm')); t63 = agg['s63'] or 0; t90 = agg['s90'] or 0; t110 = agg['s110'] or 0; period_text = f"Full Month: {months[sel_month]} {sel_year}"
                                with table_container:
                                    with ui.row().classes("w-full justify-between items-center mb-2 px-1"):
                                        ui.badge(period_text, color="green").classes("text-xs font-bold px-2 py-1"); ui.badge(f"Total: {t63+t90+t110} MTR", color="green").classes("text-xs font-bold px-2 py-1")
                                    rows = [{"sr_no": 1, "pipe_dia": "63MM", "quantity": t63, "unit": f"{t63} MTR"}, {"sr_no": 2, "pipe_dia": "90MM", "quantity": t90, "unit": f"{t90} MTR"}, {"sr_no": 3, "pipe_dia": "110MM", "quantity": t110, "unit": f"{t110} MTR"}]
                                    columns = [{"name": "sr_no", "label": "Sr.No", "field": "sr_no", "align": "center"}, {"name": "pipe_dia", "label": "Pipe Dia", "field": "pipe_dia", "align": "center"}, {"name": "quantity", "label": "Quantity", "field": "quantity", "align": "center"}, {"name": "unit", "label": "UNIT", "field": "unit", "align": "center"}]
                                    ui.table(columns=columns, rows=rows).props("dense flat bordered").classes("w-full rounded-xl shadow-sm border border-green-200 text-xs font-semibold")
                                    with ui.dialog() as month_download_dialog, ui.card().classes("rounded-3xl p-0 w-full max-w-xs overflow-hidden shadow-2xl relative"):
                                        with ui.row().classes("w-full justify-between items-center p-3 bg-gradient-to-r from-green-600 to-emerald-600 text-white"):
                                            ui.label(f"📥 Download {period_text}").classes("font-extrabold text-xs text-white")
                                            ui.button(icon="close", on_click=month_download_dialog.close).props("flat round dense color=white").classes("text-white")
                                        with ui.column().classes("w-full p-4 gap-2 bg-white"):
                                            ui.label(f"{period_text} - {t63+t90+t110} MTR").classes("text-xs font-bold text-green-700 text-center w-full mb-1")
                                            def do_m_csv():
                                                data = generate_month_csv(user.default_report_title, period_text, t63, t90, t110)
                                                ui.download(data, f"{period_text.replace(' ', '_')}_report.csv")
                                                month_download_dialog.close()
                                            def do_m_excel():
                                                data = generate_month_excel(user.default_report_title, period_text, t63, t90, t110)
                                                ui.download(data, f"{period_text.replace(' ', '_')}_report.xlsx")
                                                month_download_dialog.close()
                                            def do_m_pdf():
                                                data = generate_month_pdf(user.default_report_title, period_text, t63, t90, t110)
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
                            with ui.row().classes("w-full items-center gap-2"):
                                ui.icon("location_on", color="green"); ui.label(report.area_name or "No Area").classes("font-extrabold text-base text-green-900")
                                ui.label("|").classes("text-slate-500"); ui.label(report.report_title).classes("font-bold text-sm text-slate-900 flex-1")
                        with ui.column().classes("w-full rounded-2xl overflow-hidden shadow-lg border-2 border-indigo-900 gap-0 mb-4"):
                            with ui.grid(columns=4).classes("w-full bg-gradient-to-r from-emerald-500 via-green-500 to-teal-500 text-white font-extrabold text-center"):
                                ui.label("Sr.No").classes("py-2 text-xs"); ui.label("63MM").classes("py-2 text-xs border-x border-white/30"); ui.label("90MM").classes("py-2 text-xs border-r border-white/30"); ui.label("110MM").classes("py-2 text-xs")
                            with ui.grid(columns=4).classes("w-full bg-white text-center items-center"):
                                ui.label("1").classes("py-3 font-bold text-xs"); ui.label(f"{report.qty_63mm} MTR").classes("py-3 font-extrabold text-xs border-x border-gray-200"); ui.label(f"{report.qty_90mm} MTR").classes("py-3 font-extrabold text-xs border-r border-gray-200"); ui.label(f"{report.qty_110mm} MTR").classes("py-3 font-extrabold text-xs")
                            with ui.grid(columns=2).classes("w-full bg-gradient-to-r from-slate-900 via-green-900 to-slate-900 text-white text-center"):
                                ui.label("Grand Total").classes("py-2.5 font-bold text-green-300 text-xs")
                                ui.label(f"{report.total_qty} MTR").classes("py-2.5 font-extrabold text-cyan-300 text-sm")
                        with ui.column().classes("w-full bg-gray-50 rounded-xl p-3 border border-gray-200 mb-3"):
                            ui.label(f"📅 Date: {report.report_date.strftime('%d-%m-%Y')}").classes("text-xs font-bold text-slate-700")
                            ui.label(f"📍 Area: {report.area_name}").classes("text-xs font-bold text-slate-700")
                            ui.label(f"📄 Title: {report.report_title}").classes("text-xs font-bold text-slate-700")
                        with ui.dialog() as detail_download_dialog, ui.card().classes("rounded-3xl p-0 w-full max-w-xs overflow-hidden shadow-2xl relative"):
                            with ui.row().classes("w-full justify-between items-center p-3 bg-gradient-to-r from-green-600 to-emerald-600 text-white"):
                                ui.label(f"📥 Download {report.area_name}").classes("font-extrabold text-xs text-white")
                                ui.button(icon="close", on_click=detail_download_dialog.close).props("flat round dense color=white").classes("text-white bg-white/20")
                            with ui.column().classes("w-full p-4 gap-2 bg-white"):
                                ui.label(f"Select format for {report.area_name} - {report.total_qty} MTR:").classes("text-xs font-bold text-gray-600 text-center w-full mb-1")
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
                            ui.element("div").classes("w-12 h-1 bg-emerald-100 rounded-full mt-2")
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
                                        ui.label(f"Email: {user.email} and all reports, areas linked to this account will be removed permanently. This action cannot be undone.").classes("text-xs text-slate-600 leading-relaxed")
                                        with ui.row().classes("w-full justify-between gap-3 mt-2"):
                                            cancel_btn = ui.button("Cancel", icon="close").props("flat rounded no-caps").classes("flex-1 font-bold text-slate-600 bg-slate-100 hover:bg-slate-200")
                                            ok_btn = ui.button("OK, Delete", icon="check").props("rounded no-caps").classes("flex-1 bg-red-600 hover:bg-red-700 text-white font-bold shadow-md")
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
                                                ui.notify(f"Account {email} deleted permanently!", type="positive", position="top")
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
                        ui.notify("Account created! Login now with 6-digit password!", type="positive", position="top")
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
                    ui.notify("❌ Invalid password! Must be 6 digits correct.", type="negative", position="top")
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
        print("🔒 FINAL FREE GMAIL Ready!", flush=True)
        show_login()

@app.get("/health")
def health_check():
    return {"status": "ok", "mode": "FREE Gmail - No Money - Like Supabase", "gmail_configured": bool(os.getenv("EMAIL_PASSWORD")), "token_model": HAS_TOKEN_MODEL}

@app.get("/test-email-debug")
def test_email_debug(to: str = ""):
    if not to:
        return {"error": "Add ?to=your_email@gmail.com - e.g., /test-email-debug?to=test@gmail.com"}
    link = "https://site-collection.onrender.com/reset/test123"
    success, msg = send_reset_email_resend_http(to, "TestUser", link)
    return {"to": to, "success": success, "message": msg, "gmail_user": os.getenv("EMAIL_USER"), "gmail_pass_set": bool(os.getenv("EMAIL_PASSWORD"))}

if __name__ in {"__main__", "__mp_main__"}:
    print(f"🚀 FREE GMAIL Starting on 0.0.0.0:{PORT}", flush=True)
    ui.run(host="0.0.0.0", port=PORT, title="FREE Gmail - No Money", storage_secret=STORAGE_SECRET, reload=False, show=False, dark=False)
