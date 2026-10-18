import os
import socket
import datetime
import csv
import io

os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"

from nicegui import ui, app
from django.contrib.auth.hashers import make_password, check_password
from db_setup import init_django

init_django()
from models_app.models import AppUser, SavedArea, DailyReport, PasswordResetToken

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

MOBILE_IP = get_local_ip()
PORT = 8080
APP_BASE_URL = os.getenv("APP_BASE_URL", f"http://{MOBILE_IP}:{PORT}")

# FIX: shared=True lagavu padse nahi to error avse
ui.add_css("""
    .count-box .q-field__control {
        padding-left: 4px !important;
        padding-right: 4px !important;
        border-radius: 10px !important;
        min-height: 44px !important;
    }
    .count-box input::placeholder {
        color: #475569 !important;
        opacity: 1 !important;
        font-weight: 700 !important;
    }
    .title-pill .q-field__control {
        padding-left: 8px !important;
        padding-right: 8px !important;
    }
    .report-patti {
        transition: all 0.1s;
        cursor: pointer;
    }
    .report-patti:hover {
        transform: translateY(-1px);
    }
""", shared=True)

# ==================== DOWNLOAD GENERATORS ====================
def generate_single_csv(report: DailyReport):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([report.report_title])
    writer.writerow([f"Date: {report.report_date.strftime('%d-%m-%Y')}", f"Area: {report.area_name}"])
    writer.writerow(["Sr.No", "Pipe Dia", "Quantity", "UNIT"])
    writer.writerow([1, "63MM", report.qty_63mm, f"{report.qty_63mm} MTR"])
    writer.writerow([2, "90MM", report.qty_90mm, f"{report.qty_90mm} MTR"])
    writer.writerow([3, "110MM", report.qty_110mm, f"{report.qty_110mm} MTR"])
    writer.writerow([])
    writer.writerow(["Total", "", report.total_qty, f"{report.total_qty} MTR"])
    return output.getvalue().encode("utf-8")

def generate_month_csv(qs, period_text, title):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([title])
    writer.writerow([period_text])
    writer.writerow(["Sr.No", "Pipe Dia", "Quantity", "UNIT"])
    t63 = sum(r.qty_63mm for r in qs); t90 = sum(r.qty_90mm for r in qs); t110 = sum(r.qty_110mm for r in qs)
    writer.writerow([1, "63MM", t63, f"{t63} MTR"])
    writer.writerow([2, "90MM", t90, f"{t90} MTR"])
    writer.writerow([3, "110MM", t110, f"{t110} MTR"])
    writer.writerow([]); writer.writerow(["Grand Total", "", t63+t90+t110, f"{t63+t90+t110} MTR"])
    return output.getvalue().encode("utf-8")

def generate_excel_fast_single(report: DailyReport):
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
        wb = Workbook(); ws = wb.active; ws.title = "Report"
        center = Alignment(horizontal='center', vertical='center')
        thin_border = Border(left=Side(style='thin'), right=Side(style='thin'), top=Side(style='thin'), bottom=Side(style='thin'))
        header_fill = PatternFill(start_color="9333EA", end_color="9333EA", fill_type="solid")
        header_font = Font(bold=True, color="FFFFFF", size=11)
        ws.merge_cells('A1:D1'); ws['A1'] = report.report_title; ws['A1'].font = Font(bold=True, size=14); ws['A1'].alignment = center
        ws.merge_cells('A2:D2'); ws['A2'] = f"Date: {report.report_date.strftime('%d-%m-%Y')} | Area: {report.area_name or 'No Area'}"; ws['A2'].font = Font(bold=True, size=10, color="6B7280"); ws['A2'].alignment = center
        ws.append([]); ws.append(["Sr.No", "Pipe Dia", "Quantity", "UNIT"])
        for col in range(1,5):
            cell = ws.cell(row=4, column=col); cell.fill = header_fill; cell.font = header_font; cell.alignment = center; cell.border = thin_border
        for idx, (dia, qty) in enumerate([("63MM", report.qty_63mm), ("90MM", report.qty_90mm), ("110MM", report.qty_110mm)], start=1):
            ws.append([idx, dia, qty, f"{qty} MTR"])
            r = ws.max_row
            for c in range(1,5): ws.cell(row=r, column=c).alignment = center; ws.cell(row=r, column=c).border = thin_border
        ws.append([]); ws.append(["", "", "Grand Total", f"{report.total_qty} MTR"])
        r = ws.max_row
        for c in range(1,5): ws.cell(row=r, column=c).font = Font(bold=True, color="059669"); ws.cell(row=r, column=c).alignment = center; ws.cell(row=r, column=c).border = thin_border
        ws.column_dimensions['A'].width = 12; ws.column_dimensions['B'].width = 15; ws.column_dimensions['C'].width = 12; ws.column_dimensions['D'].width = 15
        output = io.BytesIO(); wb.save(output); return output.getvalue()
    except Exception as e: return generate_single_csv(report)

def generate_excel_fast_month(qs, period_text, title):
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
        wb = Workbook(); ws = wb.active; ws.title = "Monthly"
        thin_border = Border(left=Side(style='thin'), right=Side(style='thin'), top=Side(style='thin'), bottom=Side(style='thin'))
        header_fill = PatternFill(start_color="7C3AED", end_color="7C3AED", fill_type="solid")
        header_font = Font(bold=True, color="FFFFFF", size=11)
        ws.merge_cells('A1:D1'); ws['A1'] = title; ws['A1'].font = Font(bold=True, size=14); ws['A1'].alignment = Alignment(horizontal='center', vertical='center')
        ws.merge_cells('A2:D2'); ws['A2'] = period_text; ws['A2'].font = Font(bold=True, size=11, color="6B7280"); ws['A2'].alignment = Alignment(horizontal='center', vertical='center')
        ws.append([]); ws.append(["Sr.No", "Pipe Dia", "Quantity", "UNIT"])
        for col in range(1,5):
            cell = ws.cell(row=4, column=col); cell.fill = header_fill; cell.font = header_font; cell.alignment = Alignment(horizontal='center', vertical='center'); cell.border = thin_border
        t63 = sum(r.qty_63mm for r in qs); t90 = sum(r.qty_90mm for r in qs); t110 = sum(r.qty_110mm for r in qs)
        for idx, (dia, qty) in enumerate([("63MM", t63), ("90MM", t90), ("110MM", t110)], start=1):
            ws.append([idx, dia, qty, f"{qty} MTR"])
            r = ws.max_row
            for c in range(1,5): ws.cell(row=r, column=c).alignment = Alignment(horizontal='center', vertical='center'); ws.cell(row=r, column=c).border = thin_border
        ws.append([]); ws.append(["", "", "Grand Total", f"{t63+t90+t110} MTR"])
        r = ws.max_row
        for c in range(1,5): ws.cell(row=r, column=c).font = Font(bold=True, color="059669"); ws.cell(row=r, column=c).alignment = Alignment(horizontal='center', vertical='center'); ws.cell(row=r, column=c).border = thin_border
        ws.column_dimensions['A'].width = 12; ws.column_dimensions['B'].width = 15; ws.column_dimensions['C'].width = 12; ws.column_dimensions['D'].width = 15
        output = io.BytesIO(); wb.save(output); return output.getvalue()
    except Exception: return generate_month_csv(qs, period_text, title)

def generate_pdf_fast_single(report: DailyReport):
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
        from reportlab.lib import colors
        output = io.BytesIO(); c = canvas.Canvas(output, pagesize=A4); width, height = A4
        c.setFillColor(colors.HexColor("#7C3AED")); c.rect(0, height-80, width, 80, fill=1, stroke=0)
        c.setFillColor(colors.white); c.setFont("Helvetica-Bold", 18); c.drawCentredString(width/2, height-35, report.report_title)
        c.setFont("Helvetica", 11); c.drawCentredString(width/2, height-55, f"Area: {report.area_name or 'No Area'} | Date: {report.report_date.strftime('%d-%m-%Y')}")
        y = height - 120
        c.setFillColor(colors.HexColor("#9333EA")); c.rect(50, y-5, 500, 25, fill=1, stroke=0)
        c.setFillColor(colors.white); c.setFont("Helvetica-Bold", 12); c.drawString(70, y+2, "Sr.No"); c.drawString(150, y+2, "Pipe Dia"); c.drawString(270, y+2, "Quantity"); c.drawString(390, y+2, "UNIT")
        y -= 30; c.setFont("Helvetica", 12)
        for idx, (dia, qty) in enumerate([("63MM", report.qty_63mm), ("90MM", report.qty_90mm), ("110MM", report.qty_110mm)], start=1):
            if idx % 2 == 0: c.setFillColor(colors.HexColor("#F5F3FF")); c.rect(50, y-5, 500, 22, fill=1, stroke=0)
            c.setFillColor(colors.black); c.drawString(70, y, str(idx)); c.drawString(150, y, dia); c.drawString(270, y, str(qty)); c.drawString(390, y, f"{qty} MTR"); y -= 22
        y -= 10; c.setFillColor(colors.HexColor("#D1FAE5")); c.rect(50, y-5, 500, 25, fill=1, stroke=0)
        c.setFillColor(colors.HexColor("#059669")); c.setFont("Helvetica-Bold", 13); c.drawString(70, y+2, f"Grand Total: {report.total_qty} MTR")
        c.showPage(); c.save(); return output.getvalue()
    except Exception: return generate_single_csv(report)

def generate_pdf_fast_month(qs, period_text, title):
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
        from reportlab.lib import colors
        output = io.BytesIO(); c = canvas.Canvas(output, pagesize=A4); width, height = A4
        c.setFillColor(colors.HexColor("#7C3AED")); c.rect(0, height-80, width, 80, fill=1, stroke=0)
        c.setFillColor(colors.white); c.setFont("Helvetica-Bold", 18); c.drawCentredString(width/2, height-35, title)
        c.setFont("Helvetica-Bold", 12); c.drawCentredString(width/2, height-55, period_text)
        y = height - 120
        c.setFillColor(colors.HexColor("#9333EA")); c.rect(50, y-5, 500, 25, fill=1, stroke=0)
        c.setFillColor(colors.white); c.setFont("Helvetica-Bold", 12); c.drawString(70, y+2, "Sr.No"); c.drawString(150, y+2, "Pipe Dia"); c.drawString(270, y+2, "Quantity"); c.drawString(390, y+2, "UNIT")
        y -= 30; t63 = sum(r.qty_63mm for r in qs); t90 = sum(r.qty_90mm for r in qs); t110 = sum(r.qty_110mm for r in qs)
        c.setFont("Helvetica", 12)
        for idx, (dia, qty) in enumerate([("63MM", t63), ("90MM", t90), ("110MM", t110)], start=1):
            if idx % 2 == 0: c.setFillColor(colors.HexColor("#F5F3FF")); c.rect(50, y-5, 500, 22, fill=1, stroke=0)
            c.setFillColor(colors.black); c.drawString(70, y, str(idx)); c.drawString(150, y, dia); c.drawString(270, y, str(qty)); c.drawString(390, y, f"{qty} MTR"); y -= 22
        y -= 10; c.setFillColor(colors.HexColor("#D1FAE5")); c.rect(50, y-5, 500, 25, fill=1, stroke=0)
        c.setFillColor(colors.HexColor("#059669")); c.setFont("Helvetica-Bold", 13); c.drawString(70, y+2, f"Grand Total: {t63+t90+t110} MTR")
        c.showPage(); c.save(); return output.getvalue()
    except Exception: return generate_month_csv(qs, period_text, title)

# ==========================================
# PAGES - FAST VERSION
# ==========================================
@ui.page("/")
@ui.page("/login")
def login_page():
    saved_email = app.storage.user.get("saved_email", "")
    saved_password = app.storage.user.get("saved_password", "")
    with ui.column().classes("w-full min-h-screen items-center justify-center bg-gradient-to-br from-indigo-900 via-purple-900 to-slate-900 p-3"):
        with ui.card().classes("w-full max-w-sm rounded-3xl shadow-2xl overflow-hidden p-0 border border-purple-400/30"):
            with ui.column().classes("w-full bg-gradient-to-r from-cyan-500 via-purple-600 to-fuchsia-600 p-5 items-center text-white"):
                ui.icon("engineering", size="2.6rem").classes("mb-1 drop-shadow")
                ui.label("Site Progress Portal").classes("text-xl font-extrabold tracking-wide")
            with ui.column().classes("w-full p-5 bg-white gap-3"):
                email_input = ui.input("Email ID", value=saved_email).props("outlined rounded dense").classes("w-full")
                with email_input.add_slot("prepend"): ui.icon("mail", color="purple")
                pass_input = ui.input("Password", value=saved_password, password=True, password_toggle_button=True).props("outlined rounded dense").classes("w-full")
                with pass_input.add_slot("prepend"): ui.icon("lock", color="purple")
                def handle_login():
                    email = (email_input.value or "").strip(); pwd = pass_input.value or ""
                    user = AppUser.objects.filter(email=email).first()
                    if user and check_password(pwd, user.password):
                        app.storage.user["logged_in_user_id"] = user.id; app.storage.user["saved_email"] = email; app.storage.user["saved_password"] = pwd
                        ui.navigate.to("/home")
                    else: ui.notify("Invalid Email ID or Password!", type="negative", position="top")
                def handle_reset_password():
                    email = (email_input.value or "").strip()
                    if not email: ui.notify("Please enter your Email ID first!", type="warning", position="top"); return
                    user = AppUser.objects.filter(email=email).first()
                    if not user: ui.notify("No account found with this Email ID.", type="negative", position="top"); return
                    reset_obj = PasswordResetToken.objects.create(user=user)
                    reset_link = f"{APP_BASE_URL}/reset-password?token={reset_obj.token}"
                    print(f"\n---> RESET LINK for {user.email}: {reset_link}\n")
                    ui.notify("Reset link generated! Check terminal.", type="info", position="top")
                ui.button("Log In", icon="login", on_click=handle_login).props("rounded no-caps").classes("w-full py-2.5 mt-1 bg-gradient-to-r from-indigo-600 to-purple-600 text-white font-bold text-base shadow-lg")
                ui.button("Reset Password", icon="key", on_click=handle_reset_password).props("flat no-caps").classes("w-full text-indigo-600 font-semibold text-sm")
                ui.separator()
                ui.button("Register! Create new account", icon="person_add", on_click=lambda: ui.navigate.to("/register")).props("outline rounded no-caps").classes("w-full text-emerald-600 font-bold text-sm border-emerald-500")

@ui.page("/register")
def register_page():
    with ui.column().classes("w-full min-h-screen items-center justify-center bg-gradient-to-br from-indigo-900 via-purple-900 to-slate-900 p-3"):
        with ui.card().classes("w-full max-w-sm rounded-3xl shadow-2xl overflow-hidden p-0"):
            with ui.column().classes("w-full bg-gradient-to-r from-emerald-500 via-teal-600 to-cyan-600 p-5 items-center text-white"):
                ui.icon("person_add", size="2.5rem"); ui.label("Create New Account").classes("text-xl font-extrabold")
            with ui.column().classes("w-full p-5 bg-white gap-3"):
                uname = ui.input("User name").props("outlined rounded dense").classes("w-full")
                email = ui.input("Email id").props("outlined rounded dense").classes("w-full")
                pwd = ui.input("Password (Min 6 characters)", password=True, password_toggle_button=True).props("outlined rounded dense").classes("w-full")
                re_pwd = ui.input("Retype password", password=True, password_toggle_button=True).props("outlined rounded dense").classes("w-full")
                def handle_register():
                    u_val = (uname.value or "").strip(); e_val = (email.value or "").strip(); p_val = pwd.value or ""; rp_val = re_pwd.value or ""
                    if not u_val or not e_val: ui.notify("Please enter User name and Email id!", type="warning", position="top"); return
                    if len(p_val) < 6: ui.notify("Password must be at least 6 characters long!", type="negative", position="top"); return
                    if p_val != rp_val: ui.notify("Password and Retype password must be the same!", type="negative", position="top"); return
                    if AppUser.objects.filter(email=e_val).exists(): ui.notify("This Email ID is already registered!", type="negative", position="top"); return
                    AppUser.objects.create(username=u_val, email=e_val, password=make_password(p_val), default_report_title="Veraval site daily progress report")
                    ui.notify("Account created successfully! Please log in.", type="positive", position="top"); ui.navigate.to("/login")
                ui.button("Register", icon="check_circle", on_click=handle_register).props("rounded no-caps").classes("w-full py-2.5 mt-1 bg-gradient-to-r from-emerald-500 to-teal-600 text-white font-bold text-base shadow-lg")
                ui.button("Back to Log In", icon="arrow_back", on_click=lambda: ui.navigate.to("/login")).props("flat no-caps").classes("w-full text-gray-600 font-semibold text-sm")

@ui.page("/reset-password")
def reset_password_page(token: str = ""):
    token_obj = PasswordResetToken.objects.filter(token=token).select_related("user").first()
    with ui.column().classes("w-full min-h-screen items-center justify-center bg-gradient-to-br from-indigo-900 via-purple-900 to-slate-900 p-3"):
        if not token_obj:
            with ui.card().classes("p-5 rounded-2xl bg-white shadow-xl"): ui.label("Invalid or expired password reset link.").classes("text-red-600 text-base font-bold")
            return
        user = token_obj.user
        container = ui.card().classes("w-full max-w-sm rounded-3xl shadow-2xl p-5 bg-white")
        with container:
            ui.label(f"Welcome, {user.username}").classes("text-xl font-extrabold text-indigo-900")
            ui.label(f"{user.email}").classes("text-xs text-purple-600 font-medium mb-3")
            new_pwd = ui.input("Password", password=True, password_toggle_button=True).props("outlined rounded dense").classes("w-full mb-2")
            re_new_pwd = ui.input("Retype password", password=True, password_toggle_button=True).props("outlined rounded dense").classes("w-full mb-3")
            def confirm_reset():
                p_val = new_pwd.value or ""; rp_val = re_new_pwd.value or ""
                if len(p_val) < 6: ui.notify("Password must be at least 6 characters!", type="negative", position="top"); return
                if p_val != rp_val: ui.notify("Password and Retype password must be the same!", type="negative", position="top"); return
                user.password = make_password(p_val); user.save()
                app.storage.user["saved_password"] = p_val; token_obj.delete()
                container.clear()
                with container:
                    with ui.column().classes("items-center text-center p-3"):
                        ui.icon("verified", size="3rem", color="green")
                        ui.label(f"Successfully changed password of {user.email}.").classes("text-emerald-700 font-bold text-base mt-2")
            ui.button("OK", on_click=confirm_reset).props("rounded no-caps").classes("w-full py-2 bg-gradient-to-r from-blue-600 to-indigo-600 text-white font-bold text-base shadow-md")

@ui.page("/home")
def home_page():
    user_id = app.storage.user.get("logged_in_user_id")
    user = AppUser.objects.filter(id=user_id).first() if user_id else None
    if not user: ui.navigate.to("/login"); return
    with ui.column().classes("w-full min-h-screen bg-gradient-to-br from-indigo-100 via-purple-50 to-pink-100 py-2 px-1.5 sm:px-4 items-center"):
        with ui.card().classes("w-full max-w-md rounded-3xl shadow-2xl bg-white/95 p-3 sm:p-5 border-2 border-purple-200"):
            with ui.row().classes("w-full justify-between items-center mb-2"):
                date_input = ui.input("Date", value=datetime.date.today().strftime("%Y-%m-%d")).props("type=date outlined rounded dense color=purple").classes("w-36 text-xs font-bold bg-purple-50 rounded-full shadow-sm")
                with ui.button(icon="account_circle").props("round unelevated").classes("bg-gradient-to-r from-indigo-600 to-purple-600 text-white shadow-md"):
                    with ui.menu().classes("rounded-xl shadow-xl border border-purple-200"):
                        with ui.menu_item(on_click=lambda: ui.navigate.to("/profile")).classes("hover:bg-purple-50 font-semibold"):
                            with ui.row().classes("items-center gap-2"): ui.icon("person", color="purple"); ui.label("Profile")
                        ui.separator()
                        with ui.menu_item(on_click=lambda: ui.navigate.to("/filter")).classes("hover:bg-purple-50 font-semibold"):
                            with ui.row().classes("items-center gap-2"): ui.icon("filter_alt", color="indigo"); ui.label("Filter")
            with ui.row().classes("w-full justify-center mb-2.5"):
                title_input = ui.input(value=user.default_report_title).props("borderless dense input-class='text-center font-extrabold text-[13px] sm:text-base text-slate-900'").classes("title-pill w-full px-2 py-1 rounded-full bg-gradient-to-r from-cyan-200 via-purple-200 to-fuchsia-300 shadow-md border-2 border-purple-300")

            saved_areas = list(SavedArea.objects.filter(user=user).values_list("area_name", flat=True))
            with ui.row().classes("w-full justify-end mb-2.5"):
                area_select = ui.select(options=saved_areas, label="Enter Area *", with_input=True, new_value_mode="add-unique").props("outlined rounded dense color=purple").classes("w-44 sm:w-56 bg-indigo-50/60 font-semibold text-xs shadow-sm")
                def on_area_change(e):
                    val = (e.value or "").strip()
                    if val:
                        SavedArea.objects.get_or_create(user=user, area_name=val)
                        area_select.options = list(SavedArea.objects.filter(user=user).values_list("area_name", flat=True)); area_select.update()
                area_select.on_value_change(on_area_change)
            with ui.row().classes("w-full justify-center items-center gap-1.5 mb-1.5"):
                ui.icon("plumbing", color="purple", size="1.3rem"); ui.label("Pipe Sizes").classes("text-base sm:text-xl font-extrabold text-slate-800")
            with ui.column().classes("w-full rounded-2xl overflow-hidden shadow-lg border-2 border-indigo-900 gap-0"):
                with ui.grid(columns=3).classes("w-full bg-gradient-to-r from-fuchsia-500 via-purple-500 to-fuchsia-500 text-white font-extrabold text-center"):
                    ui.label("63MM").classes("py-2 text-xs sm:text-base"); ui.label("90MM").classes("py-2 text-xs sm:text-base border-x-2 border-indigo-900"); ui.label("110MM").classes("py-2 text-xs sm:text-base")
                with ui.grid(columns=3).classes("w-full bg-white text-center items-center"):
                    with ui.column().classes("p-1.5 items-center w-full"): c63 = ui.input(placeholder="Count").props("type=number outlined dense color=purple input-class='text-center font-bold text-xs'").classes("count-box w-full")
                    with ui.column().classes("p-1.5 items-center border-x-2 border-indigo-900 w-full"): c90 = ui.input(placeholder="Count").props("type=number outlined dense color=purple input-class='text-center font-bold text-xs'").classes("count-box w-full")
                    with ui.column().classes("p-1.5 items-center w-full"): c110 = ui.input(placeholder="Count").props("type=number outlined dense color=purple input-class='text-center font-bold text-xs'").classes("count-box w-full")
                with ui.grid(columns=3).classes("w-full bg-purple-50/70 text-center border-b-2 border-indigo-900 items-center"):
                    u63_lbl = ui.label("UNIT").classes("py-2.5 font-extrabold text-indigo-900 text-xs")
                    u90_lbl = ui.label("UNIT").classes("py-2.5 font-extrabold text-indigo-900 text-xs border-x-2 border-indigo-900")
                    u110_lbl = ui.label("UNIT").classes("py-2.5 font-extrabold text-indigo-900 text-xs")
                with ui.grid(columns=2).classes("w-full bg-gradient-to-r from-slate-900 via-indigo-950 to-slate-900 text-white text-center items-center"):
                    ui.label("SUMMARY").classes("py-2.5 font-bold text-purple-300 text-xs")
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
                try: selected_date = datetime.date.fromisoformat(date_input.value)
                except Exception: selected_date = datetime.date.today()
                area_val = (area_select.value or "").strip()
                if not area_val:
                    ui.notify("Please Enter Area! Ex: Laskana, Kamrej", type="warning", position="top"); return
                SavedArea.objects.get_or_create(user=user, area_name=area_val)
                current_title = (title_input.value or "").strip() or user.default_report_title
                user.default_report_title = current_title; user.save()
                DailyReport.objects.create(user=user, report_title=current_title, report_date=selected_date, area_name=area_val, qty_63mm=q63, qty_90mm=q90, qty_110mm=q110, total_qty=q63+q90+q110, price_sum=float(q63+q90+q110))
                ui.notify(f"Saved! {area_val} - {selected_date.strftime('%d-%m-%Y')}", type="positive", position="top")
                c63.value = ""; c90.value = ""; c110.value = ""; update_live_preview()
            ui.button("Save Report", icon="save", on_click=save_daily_report).props("rounded no-caps").classes("w-full py-2.5 mt-3 bg-gradient-to-r from-indigo-600 via-purple-600 to-fuchsia-600 text-white font-extrabold text-sm shadow-xl")

@ui.page("/profile")
def profile_page():
    user_id = app.storage.user.get("logged_in_user_id")
    user = AppUser.objects.filter(id=user_id).first() if user_id else None
    if not user: ui.navigate.to("/login"); return
    with ui.column().classes("w-full min-h-screen items-center justify-center bg-gradient-to-br from-indigo-100 via-purple-50 to-pink-100 p-3"):
        with ui.card().classes("w-full max-w-sm rounded-3xl shadow-2xl p-5 bg-white border-2 border-purple-200"):
            ui.button("Back", icon="arrow_back", on_click=lambda: ui.navigate.to("/home")).props("flat rounded no-caps").classes("text-indigo-700 font-bold mb-1")
            with ui.column().classes("w-full items-center my-3"):
                ui.icon("account_circle", size="4.5rem", color="purple"); ui.label(user.username).classes("text-xl font-extrabold text-slate-800 mt-1"); ui.label(user.email).classes("text-sm text-purple-600 font-medium")
            ui.separator().classes("my-3")
            with ui.dialog() as delete_dialog, ui.card().classes("rounded-2xl p-5 max-w-xs"):
                with ui.row().classes("items-center gap-2 text-red-600 mb-2"): ui.icon("warning", size="1.8rem"); ui.label("Delete Account?").classes("text-lg font-extrabold")
                ui.label("If you delete your account, all your data will be permanently deleted.").classes("text-slate-700 text-sm font-medium mb-4")
                with ui.row().classes("w-full justify-end gap-2"):
                    ui.button("Cancel", on_click=delete_dialog.close).props("outline rounded no-caps").classes("font-bold text-xs")
                    def confirm_delete():
                        user.delete(); app.storage.user.clear(); delete_dialog.close(); ui.notify("Your account and data permanently deleted.", type="positive", position="top"); ui.timer(1.0, lambda: ui.navigate.to("/login"), once=True)
                    ui.button("Delete", icon="delete_forever", on_click=confirm_delete).props("rounded no-caps").classes("bg-red-600 text-white font-bold text-xs")
            ui.button("Delete Account", icon="delete", on_click=delete_dialog.open).props("rounded no-caps").classes("w-full py-2.5 bg-gradient-to-r from-red-500 to-rose-600 text-white font-bold shadow-lg")

@ui.page("/filter")
@ui.page("/download")
def filter_page():
    user_id = app.storage.user.get("logged_in_user_id")
    user = AppUser.objects.filter(id=user_id).first() if user_id else None
    if not user: ui.navigate.to("/login"); return
    today = datetime.date.today()
    months = {1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun", 7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec"}
    years = {y: str(y) for y in range(today.year - 5, today.year + 2)}
    with ui.column().classes("w-full min-h-screen bg-gradient-to-br from-indigo-100 via-purple-50 to-pink-100 py-2 px-1.5 sm:px-4 items-center"):
        with ui.card().classes("w-full max-w-md rounded-3xl shadow-2xl bg-white p-3 sm:p-5 border-2 border-purple-200"):
            ui.button("Back", icon="arrow_back", on_click=lambda: ui.navigate.to("/home")).props("flat rounded no-caps").classes("text-indigo-700 font-bold")
            with ui.row().classes("w-full justify-center my-1.5"):
                ui.label(user.default_report_title).classes("w-full px-2 py-1.5 rounded-full bg-gradient-to-r from-cyan-200 via-purple-200 to-fuchsia-300 text-slate-900 font-extrabold text-[13px] sm:text-base shadow-md border border-purple-300 text-center")
            with ui.grid(columns=3).classes("w-full gap-1.5 my-2.5 bg-purple-50 p-2 rounded-2xl border border-purple-200"):
                date_options = {"": "Select Date", **{str(d): f"{d:02d}" for d in range(1, 32)}}
                day_select = ui.select(options=date_options, value="", label="Select Date").props("outlined rounded dense color=purple").classes("w-full bg-white font-semibold text-xs")
                month_select = ui.select(options=months, value=today.month, label="Month").props("outlined rounded dense color=purple").classes("w-full bg-white font-semibold text-xs")
                year_select = ui.select(options=years, value=today.year, label="Year").props("outlined rounded dense color=purple").classes("w-full bg-white font-semibold text-xs")
            table_container = ui.column().classes("w-full mt-1 gap-2")

            def load_table_data():
                table_container.clear()
                sel_month = int(month_select.value); sel_year = int(year_select.value); sel_day = day_select.value
                base_qs = DailyReport.objects.filter(user=user, report_date__month=sel_month, report_date__year=sel_year).order_by('-id')
                if not base_qs.exists():
                    with table_container:
                        with ui.card().classes("w-full p-5 rounded-2xl bg-red-50 border-2 border-red-200 items-center text-center shadow-sm"):
                            ui.icon("info", size="2.2rem", color="red"); ui.label("No Data Available").classes("text-sm font-extrabold text-red-700 mt-1")
                    return
                if sel_day:
                    qs = base_qs.filter(report_date__day=int(sel_day))
                    period_text = f"Date: {int(sel_day):02d} {months[sel_month]} {sel_year}"
                    with table_container:
                        if not qs.exists():
                            with ui.card().classes("w-full p-5 rounded-2xl bg-red-50 border-2 border-red-200 items-center text-center shadow-sm"):
                                ui.icon("info", size="2.2rem", color="red"); ui.label("No Data").classes("text-sm font-extrabold text-red-700 mt-1")
                            return
                        grand_total = sum(r.total_qty for r in qs)
                        with ui.row().classes("w-full justify-between items-center mb-2 px-1"):
                            ui.badge(period_text, color="purple").classes("text-xs font-bold px-2 py-1")
                            ui.badge(f"Reports: {qs.count()} | Total: {grand_total} MTR", color="green").classes("text-[11px] font-bold px-2 py-1")
                        for report in qs:
                            area_display = report.area_name or "No Area"
                            with ui.card().classes("report-patti w-full rounded-2xl border-2 border-purple-200 bg-gradient-to-r from-white to-purple-50 p-3 shadow-md").on("click", lambda r=report: ui.navigate.to(f"/report/{r.id}")):
                                with ui.row().classes("w-full justify-between items-center"):
                                    with ui.row().classes("items-center gap-2"):
                                        ui.icon("location_on", color="purple", size="1.2rem"); ui.label(area_display).classes("font-extrabold text-sm text-indigo-900")
                                    ui.badge(f"{report.report_date.strftime('%d-%m-%Y')}", color="grey").classes("text-[10px]")
                                ui.label(report.report_title).classes("text-xs font-semibold text-slate-700 mt-1 w-full truncate")
                                with ui.row().classes("w-full justify-between items-center mt-1"):
                                    ui.label(f"63:{report.qty_63mm} | 90:{report.qty_90mm} | 110:{report.qty_110mm}").classes("text-[11px] font-bold text-slate-600")
                                    ui.label(f"Total: {report.total_qty} MTR").classes("text-xs font-extrabold text-emerald-600")
                else:
                    qs = base_qs
                    period_text = f"Full Month: {months[sel_month]} {sel_year}"
                    t63 = sum(r.qty_63mm for r in qs); t90 = sum(r.qty_90mm for r in qs); t110 = sum(r.qty_110mm for r in qs)
                    with table_container:
                        with ui.row().classes("w-full justify-between items-center mb-2 px-1"):
                            ui.badge(period_text, color="purple").classes("text-xs font-bold px-2 py-1")
                            ui.badge(f"Total: {t63+t90+t110} MTR", color="green").classes("text-xs font-bold px-2 py-1")
                        rows = [{"sr_no": 1, "pipe_dia": "63MM", "quantity": t63, "unit": f"{t63} MTR"}, {"sr_no": 2, "pipe_dia": "90MM", "quantity": t90, "unit": f"{t90} MTR"}, {"sr_no": 3, "pipe_dia": "110MM", "quantity": t110, "unit": f"{t110} MTR"}]
                        columns = [{"name": "sr_no", "label": "Sr.No", "field": "sr_no", "align": "center"}, {"name": "pipe_dia", "label": "Pipe Dia", "field": "pipe_dia", "align": "center"}, {"name": "quantity", "label": "Quantity", "field": "quantity", "align": "center"}, {"name": "unit", "label": "UNIT", "field": "unit", "align": "center"}]
                        ui.table(columns=columns, rows=rows).props("dense flat bordered").classes("w-full rounded-xl shadow-sm border border-purple-200 text-xs font-semibold")
                        with ui.dialog() as month_download_dialog, ui.card().classes("rounded-3xl p-0 w-full max-w-xs overflow-hidden shadow-2xl"):
                            with ui.column().classes("w-full bg-gradient-to-r from-indigo-600 to-purple-600 p-4 items-center text-white"):
                                ui.icon("download", size="2rem"); ui.label("Download Monthly Report").classes("font-extrabold text-base"); ui.label(period_text).classes("text-xs text-purple-100 text-center")
                            with ui.column().classes("w-full p-4 gap-2 bg-white"):
                                def do_m_csv():
                                    ui.download(generate_month_csv(qs, period_text, user.default_report_title), f"{period_text}_report.csv")
                                    month_download_dialog.close()
                                def do_m_excel():
                                    ui.download(generate_excel_fast_month(qs, period_text, user.default_report_title), f"{period_text}_report.xlsx")
                                    month_download_dialog.close()
                                def do_m_pdf():
                                    ui.download(generate_pdf_fast_month(qs, period_text, user.default_report_title), f"{period_text}_report.pdf")
                                    month_download_dialog.close()
                                ui.button("As CSV", icon="table_view", on_click=do_m_csv).props("outline rounded no-caps").classes("w-full font-bold text-sm border-indigo-500 text-indigo-600")
                                ui.button("As Excel", icon="description", on_click=do_m_excel).props("outline rounded no-caps").classes("w-full font-bold text-sm border-emerald-500 text-emerald-600")
                                ui.button("As PDF", icon="picture_as_pdf", on_click=do_m_pdf).props("outline rounded no-caps").classes("w-full font-bold text-sm border-red-500 text-red-600")
                                ui.separator().classes("my-1")
                                ui.button("Close", icon="close", on_click=month_download_dialog.close).props("rounded no-caps").classes("w-full bg-slate-200 text-slate-700 font-bold text-sm")
                        ui.button("Download Report", icon="download", on_click=month_download_dialog.open).props("rounded no-caps").classes("w-full mt-3 bg-gradient-to-r from-emerald-500 to-teal-600 text-white font-bold py-2 shadow-md")

            day_select.on_value_change(lambda: load_table_data()); month_select.on_value_change(lambda: load_table_data()); year_select.on_value_change(lambda: load_table_data())
            load_table_data()

@ui.page("/report/{report_id}")
def report_detail_page(report_id: int):
    user_id = app.storage.user.get("logged_in_user_id")
    user = AppUser.objects.filter(id=user_id).first() if user_id else None
    if not user: ui.navigate.to("/login"); return
    report = DailyReport.objects.filter(id=report_id, user=user).select_related("user").first()
    if not report:
        with ui.column().classes("w-full min-h-screen items-center justify-center"):
            ui.label("Report not found!").classes("text-red-600 font-bold"); ui.button("Back", on_click=lambda: ui.navigate.to("/filter"))
        return
    with ui.column().classes("w-full min-h-screen bg-gradient-to-br from-indigo-100 via-purple-50 to-pink-100 py-2 px-1.5 sm:px-4 items-center"):
        with ui.card().classes("w-full max-w-md rounded-3xl shadow-2xl bg-white p-3 sm:p-5 border-2 border-purple-200"):
            with ui.row().classes("w-full justify-between items-center mb-3"):
                ui.button("Back", icon="arrow_back", on_click=lambda: ui.navigate.to("/filter")).props("flat rounded no-caps").classes("text-indigo-700 font-bold")
                ui.badge(f"{report.report_date.strftime('%d-%m-%Y')}", color="purple").classes("font-bold")
            with ui.column().classes("w-full rounded-2xl bg-gradient-to-r from-cyan-200 via-purple-200 to-fuchsia-300 p-3 border-2 border-purple-300 shadow-md mb-3"):
                with ui.row().classes("w-full items-center gap-2"):
                    ui.icon("location_on", color="purple"); ui.label(report.area_name or "No Area").classes("font-extrabold text-base text-indigo-900")
                    ui.label("|").classes("text-slate-500"); ui.label(report.report_title).classes("font-bold text-sm text-slate-900 flex-1")
            with ui.column().classes("w-full rounded-2xl overflow-hidden shadow-lg border-2 border-indigo-900 gap-0 mb-4"):
                with ui.grid(columns=3).classes("w-full bg-gradient-to-r from-fuchsia-500 via-purple-500 to-fuchsia-500 text-white font-extrabold text-center"):
                    ui.label("63MM").classes("py-2 text-xs sm:text-base"); ui.label("90MM").classes("py-2 text-xs sm:text-base border-x-2 border-indigo-900"); ui.label("110MM").classes("py-2 text-xs sm:text-base")
                with ui.grid(columns=3).classes("w-full bg-white text-center items-center"):
                    ui.label(f"{report.qty_63mm} MTR").classes("py-3 font-extrabold text-xs"); ui.label(f"{report.qty_90mm} MTR").classes("py-3 font-extrabold text-xs border-x-2 border-indigo-900"); ui.label(f"{report.qty_110mm} MTR").classes("py-3 font-extrabold text-xs")
                with ui.grid(columns=1).classes("w-full bg-gradient-to-r from-slate-900 to-indigo-950 text-white text-center"):
                    ui.label(f"Total: {report.total_qty} MTR").classes("py-2.5 font-extrabold text-cyan-300 text-sm")
            with ui.dialog() as download_dialog, ui.card().classes("rounded-3xl p-0 w-full max-w-xs overflow-hidden shadow-2xl"):
                with ui.column().classes("w-full bg-gradient-to-r from-indigo-600 to-purple-600 p-4 items-center text-white"):
                    ui.icon("download", size="2rem"); ui.label("Download Report").classes("font-extrabold text-base")
                    ui.label(f"{report.area_name} - {report.report_date.strftime('%d-%m-%Y')}").classes("text-xs text-purple-100 text-center")
                with ui.column().classes("w-full p-4 gap-2 bg-white"):
                    def do_download_csv():
                        ui.download(generate_single_csv(report), f"{report.area_name}_{report.report_date}_report.csv")
                        download_dialog.close()
                    def do_download_excel():
                        ui.download(generate_excel_fast_single(report), f"{report.area_name}_{report.report_date}_report.xlsx")
                        download_dialog.close()
                    def do_download_pdf():
                        ui.download(generate_pdf_fast_single(report), f"{report.area_name}_{report.report_date}_report.pdf")
                        download_dialog.close()
                    ui.button("As CSV", icon="table_view", on_click=do_download_csv).props("outline rounded no-caps").classes("w-full font-bold text-sm border-indigo-500 text-indigo-600")
                    ui.button("As Excel", icon="description", on_click=do_download_excel).props("outline rounded no-caps").classes("w-full font-bold text-sm border-emerald-500 text-emerald-600")
                    ui.button("As PDF", icon="picture_as_pdf", on_click=do_download_pdf).props("outline rounded no-caps").classes("w-full font-bold text-sm border-red-500 text-red-600")
                    ui.separator().classes("my-1")
                    ui.button("Close", icon="close", on_click=download_dialog.close).props("rounded no-caps").classes("w-full bg-slate-200 text-slate-700 font-bold text-sm")
            ui.button("Download Report", icon="download", on_click=download_dialog.open).props("rounded no-caps").classes("w-full py-3 bg-gradient-to-r from-emerald-500 to-teal-600 text-white font-extrabold text-base shadow-xl")

print("\n========================================================")
print(f"✅ FIXED | IP: {MOBILE_IP}:{PORT}")
print("========================================================\n")

ui.run(host="0.0.0.0", port=PORT, title="Site Daily Progress Report", storage_secret="my_persistent_secret_key_123", reload=False, show=False)
