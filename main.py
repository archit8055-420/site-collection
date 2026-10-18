"""
FINAL - DATE DESIGN REPAIR ONLY + Render Fix
Same design, only host=0.0.0.0 changed
"""
import os, datetime, csv, io
print("🚀 FINAL - Date Design Repair Loading...", flush=True)
os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"
from nicegui import ui, app, run

CACHE = {"users": {}, "areas": {}, "pwd_verified": {}}

from db_setup import init_django
init_django()
from models_app.models import AppUser, SavedArea, DailyReport
from django.contrib.auth.hashers import make_password, check_password
from django.db.models import Sum
import hashlib, time

PORT = int(os.getenv("PORT", "8080"))
STORAGE_SECRET = os.getenv("STORAGE_SECRET", "my_persistent_secret_key_123")

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
        center = Alignment(horizontal='center', vertical='center')
        thin_border = Border(left=Side(style='thin'), right=Side(style='thin'), top=Side(style='thin'), bottom=Side(style='thin'))
        header_fill = PatternFill(start_color="10B981", end_color="10B981", fill_type="solid")
        header_font = Font(bold=True, color="FFFFFF", size=11)
        ws.merge_cells('A1:D1'); ws['A1'] = report.report_title; ws['A1'].font = Font(bold=True, size=14); ws['A1'].alignment = center
        ws.merge_cells('A2:D2'); ws['A2'] = f"Date: {report.report_date.strftime('%d-%m-%Y')} | Area: {report.area_name or 'No Area'}"; ws['A2'].font = Font(bold=True, size=10); ws['A2'].alignment = center
        ws.append([]); ws.append(["Sr.No", "Pipe Dia", "Quantity", "UNIT"])
        for col in range(1,5):
            cell = ws.cell(row=4, column=col); cell.fill = header_fill; cell.font = header_font; cell.alignment = center; cell.border = thin_border
        for idx, (dia, qty) in enumerate([("63MM", report.qty_63mm), ("90MM", report.qty_90mm), ("110MM", report.qty_110mm)], start=1):
            ws.append([idx, dia, qty, f"{qty} MTR"]); r = ws.max_row
            for c in range(1,5): ws.cell(row=r, column=c).alignment = center; ws.cell(row=r, column=c).border = thin_border
        ws.append([]); ws.append(["", "", "Grand Total", f"{report.total_qty} MTR"])
        r = ws.max_row
        for c in range(1,5): ws.cell(row=r, column=c).font = Font(bold=True); ws.cell(row=r, column=c).alignment = center; ws.cell(row=r, column=c).border = thin_border
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
    writer.writerow([title])
    writer.writerow([period_text])
    writer.writerow([f"Generated: {datetime.datetime.now().strftime('%d-%m-%Y %H:%M:%S')}"])
    writer.writerow([])
    writer.writerow(["Sr.No", "Pipe Dia", "Quantity", "UNIT"])
    writer.writerow([1, "63MM", t63, f"{t63} MTR"])
    writer.writerow([2, "90MM", t90, f"{t90} MTR"])
    writer.writerow([3, "110MM", t110, f"{t110} MTR"])
    writer.writerow([])
    writer.writerow(["Grand Total", "", t63+t90+t110, f"{t63+t90+t110} MTR"])
    return output.getvalue().encode("utf-8")

def generate_month_excel(title, period_text, t63, t90, t110):
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
        wb = Workbook(); ws = wb.active; ws.title = "Monthly Report"
        center = Alignment(horizontal='center', vertical='center')
        thin = Border(left=Side(style='thin'), right=Side(style='thin'), top=Side(style='thin'), bottom=Side(style='thin'))
        hdr_fill = PatternFill(start_color="10B981", end_color="10B981", fill_type="solid")
        hdr_font = Font(bold=True, color="FFFFFF", size=11)
        ws.merge_cells('A1:D1'); ws['A1'] = title; ws['A1'].font = Font(bold=True, size=14); ws['A1'].alignment = center
        ws.merge_cells('A2:D2'); ws['A2'] = period_text; ws['A2'].font = Font(bold=True, size=11); ws['A2'].alignment = center
        ws.merge_cells('A3:D3'); ws['A3'] = f"Generated: {datetime.datetime.now().strftime('%d-%m-%Y %H:%M:%S')}"; ws['A3'].alignment = center
        ws.append([])
        ws.append(["Sr.No", "Pipe Dia", "Quantity", "UNIT"])
        r = ws.max_row
        for col in range(1,5):
            cell = ws.cell(row=r, column=col); cell.fill = hdr_fill; cell.font = hdr_font; cell.alignment = center; cell.border = thin
        for idx, (dia, qty) in enumerate([("63MM", t63), ("90MM", t90), ("110MM", t110)], start=1):
            ws.append([idx, dia, qty, f"{qty} MTR"])
            rr = ws.max_row
            for col in range(1,5): ws.cell(row=rr, column=col).alignment = center; ws.cell(row=rr, column=col).border = thin
        ws.append([])
        ws.append(["", "", "Grand Total", f"{t63+t90+t110} MTR"])
        rr = ws.max_row
        for col in range(1,5): ws.cell(row=rr, column=col).font = Font(bold=True); ws.cell(row=rr, column=col).alignment = center; ws.cell(row=rr, column=col).border = thin
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
    .back-btn {
        background-color: #d4821e !important;
        color: black !important;
        border: 2px solid #b56a17 !important;
        border-radius: 20px !important;
        font-weight: bold !important;
    }
    .back-btn .q-btn__content { color: black !important; }
    .back-btn .q-icon { color: black !important; }
    .back-btn:hover { background-color: #b56a17 !important; color: black !important; }
    .date-pill {
        background: white !important;
        border: 1.5px solid #e5e7eb !important;
        border-radius: 9999px !important;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1) !important;
        padding: 6px 16px !important;
        display: flex !important;
        align-items: center !important;
        gap: 8px !important;
        min-width: 145px !important;
    }
    .date-pill input {
        border: none !important;
        outline: none !important;
        font-weight: 700 !important;
        font-size: 13px !important;
        color: #1f2937 !important;
        background: transparent !important;
        width: 100px !important;
        text-align: center !important;
        cursor: pointer !important;
    }
    .date-pill .q-field__control {
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
        min-height: auto !important;
        height: auto !important;
        padding: 0 !important;
    }
    .date-pill .q-field__control:before,
    .date-pill .q-field__control:after {
        display: none !important;
    }
    .date-pill input::-webkit-calendar-picker-indicator {
        cursor: pointer !important;
        opacity: 0.7 !important;
        margin-left: 4px !important;
    }
""", shared=True)

@ui.page("/")
def main_spa_page():
    print("🚀 FINAL - Date Design Repair Loading", flush=True)
    state = {"user": None, "selected_report": None}
    with ui.column().classes("w-full min-h-screen p-0 m-0 gap-0") as root:
        login_view = ui.column().classes("w-full min-h-screen items-center justify-center bg-gradient-to-br from-indigo-900 via-purple-900 to-slate-900 p-3")
        with login_view:
            with ui.card().classes("w-full max-w-sm rounded-3xl shadow-2xl overflow-hidden p-0 border-2 border-green-400/50"):
                with ui.column().classes("w-full bg-gradient-to-r from-emerald-500 via-green-600 to-teal-600 p-4 items-center text-white"):
                    ui.icon("bolt", size="2.5rem")
                    ui.label("FINAL DIALOG + EDITABLE").classes("text-xl font-extrabold")
                    ui.label("⚡ Single Download -> Dialog").classes("text-xs")
                with ui.column().classes("w-full p-5 bg-white gap-3"):
                    saved_email = app.storage.user.get("saved_email", "")
                    saved_pwd = app.storage.user.get("saved_password", "")
                    email_input = ui.input("Email ID", value=saved_email).props("outlined rounded dense").classes("w-full")
                    pass_input = ui.input("Password", value=saved_pwd, password=True, password_toggle_button=True).props("outlined rounded dense").classes("w-full")
                    login_btn = ui.button("⚡ Log In", icon="bolt").props("rounded no-caps").classes("w-full py-2.5 bg-gradient-to-r from-emerald-600 to-green-600 text-white font-bold shadow-lg")
                    status_label = ui.label("").classes("text-xs text-center font-bold text-green-600")
                    reg_btn = ui.button("Register New Account", icon="person_add").props("outline rounded no-caps").classes("w-full text-emerald-600 font-bold text-sm border-emerald-500")

        home_view = ui.column().classes("w-full min-h-screen bg-gradient-to-br from-indigo-100 via-purple-50 to-pink-100 py-2 px-1.5 sm:px-4 items-center spa-hidden")
        filter_view = ui.column().classes("w-full min-h-screen bg-gradient-to-br from-indigo-100 via-purple-50 to-pink-100 py-2 px-1.5 sm:px-4 items-center spa-hidden")
        filter_detail_view = ui.column().classes("w-full min-h-screen bg-gradient-to-br from-indigo-100 via-purple-50 to-pink-100 py-2 px-1.5 sm:px-4 items-center spa-hidden")
        profile_view = ui.column().classes("w-full min-h-screen bg-gradient-to-br from-indigo-100 via-purple-50 to-pink-100 p-3 items-center justify-center spa-hidden")
        register_view = ui.column().classes("w-full min-h-screen items-center justify-center bg-gradient-to-br from-indigo-900 via-purple-900 to-slate-900 p-3 spa-hidden")

        def show_login():
            state["user"] = None
            login_view.classes(remove="spa-hidden")
            home_view.classes(add="spa-hidden")
            filter_view.classes(add="spa-hidden")
            filter_detail_view.classes(add="spa-hidden")
            profile_view.classes(add="spa-hidden")
            register_view.classes(add="spa-hidden")

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

        def show_home():
            login_view.classes(add="spa-hidden")
            home_view.classes(remove="spa-hidden")
            filter_view.classes(add="spa-hidden")
            filter_detail_view.classes(add="spa-hidden")
            profile_view.classes(add="spa-hidden")
            register_view.classes(add="spa-hidden")
            build_home()

        def show_filter():
            login_view.classes(add="spa-hidden")
            home_view.classes(add="spa-hidden")
            filter_view.classes(remove="spa-hidden")
            filter_detail_view.classes(add="spa-hidden")
            profile_view.classes(add="spa-hidden")
            register_view.classes(add="spa-hidden")
            build_filter()

        def show_filter_detail(report):
            state["selected_report"] = report
            login_view.classes(add="spa-hidden")
            home_view.classes(add="spa-hidden")
            filter_view.classes(add="spa-hidden")
            filter_detail_view.classes(remove="spa-hidden")
            profile_view.classes(add="spa-hidden")
            register_view.classes(add="spa-hidden")
            build_filter_detail(report)

        def show_profile():
            login_view.classes(add="spa-hidden")
            home_view.classes(add="spa-hidden")
            filter_view.classes(add="spa-hidden")
            filter_detail_view.classes(add="spa-hidden")
            profile_view.classes(remove="spa-hidden")
            register_view.classes(add="spa-hidden")
            build_profile()

        def show_register():
            login_view.classes(add="spa-hidden")
            home_view.classes(add="spa-hidden")
            filter_view.classes(add="spa-hidden")
            filter_detail_view.classes(add="spa-hidden")
            profile_view.classes(add="spa-hidden")
            register_view.classes(remove="spa-hidden")

        def build_home():
            home_view.clear()
            user = state["user"]
            if not user:
                show_login()
                return
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
                                user.default_report_title = current_title; user.save(update_fields=['default_report_title']); CACHE["users"][user.email] = user
                            DailyReport.objects.create(user=user, report_title=current_title, report_date=selected_date, area_name=area_val, qty_63mm=q63, qty_90mm=q90, qty_110mm=q110, total_qty=q63+q90+q110, price_sum=float(q63+q90+q110))
                            ui.notify(f"Saved {area_val} on {selected_date.strftime('%d-%m-%Y')}!", type="positive", position="top")
                            c63.value = ""; c90.value = ""; c110.value = ""; area_input.value = ""; update_live_preview()
                            get_areas(); refresh_suggestions()

                        ui.button("⚡ Save", icon="bolt", on_click=save_daily_report).props("rounded no-caps").classes("w-full py-2.5 mt-3 bg-gradient-to-r from-emerald-600 via-green-600 to-teal-600 text-white font-extrabold text-sm shadow-xl")

        def build_filter():
            filter_view.clear()
            user = state["user"]
            if not user:
                show_login()
                return
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
                                        ui.badge(period_text, color="green").classes("text-xs font-bold px-2 py-1"); ui.badge(f"Reports: {qs.count()} | Total: {grand_total} MTR", color="green").classes("text- font-bold px-2 py-1")
                                    for report in qs[:50]:
                                        area_display = report.area_name or "No Area"
                                        with ui.card().classes("report-patti w-full rounded-2xl border-2 border-green-200 bg-gradient-to-r from-white to-green-50 p-3 shadow-md").on("click", lambda r=report: show_filter_detail(r)):
                                            with ui.row().classes("w-full justify-between items-center"):
                                                with ui.row().classes("items-center gap-2"): ui.icon("location_on", color="green", size="1.2rem"); ui.label(area_display).classes("font-extrabold text-sm text-indigo-900")
                                                ui.badge(f"{report.report_date.strftime('%d-%m-%Y')}", color="grey").classes("text-")
                                            ui.label(report.report_title).classes("text-xs font-semibold text-slate-700 mt-1 w-full truncate")
                                            with ui.row().classes("w-full justify-between items-center mt-1"):
                                                ui.label(f"63:{report.qty_63mm} | 90:{report.qty_90mm} | 110:{report.qty_110mm}").classes("text- font-bold text-slate-600")
                                                ui.label(f"Total: {report.total_qty} MTR").classes("text-xs font-extrabold text-emerald-600")
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
                                            ui.label("Select format:").classes("text-xs font-bold text-gray-600 text-center w-full")
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
                                            ui.button("As CSV", icon="table_view", on_click=do_m_csv).props("outline rounded no-caps").classes("w-full font-bold text-sm border-blue-500 text-blue-600")
                                            ui.button("As Excel", icon="description", on_click=do_m_excel).props("outline rounded no-caps").classes("w-full font-bold text-sm border-green-500 text-green-600")
                                            ui.button("As PDF", icon="picture_as_pdf", on_click=do_m_pdf).props("outline rounded no-caps").classes("w-full font-bold text-sm border-red-500 text-red-600")
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
                with ui.column().classes("w-full max-w-sm items-center gap-2"):
                    with ui.card().classes("w-full rounded-3xl shadow-2xl p-5 bg-white border-2 border-green-200"):
                        ui.button("Back to Home", icon="arrow_back", on_click=show_home).props("flat rounded no-caps").classes("back-btn text-xs mb-2")
                        with ui.column().classes("w-full items-center my-3"):
                            ui.icon("account_circle", size="4.5rem", color="green"); ui.label(user.username).classes("text-xl font-extrabold text-slate-800 mt-1"); ui.label(user.email).classes("text-sm text-green-600 font-medium")
                        with ui.row().classes("w-full justify-center gap-2 mb-2"):
                            def logout():
                                state["user"] = None
                                show_login()
                            ui.button("Logout", icon="logout", on_click=logout).props("outline rounded").classes("font-bold text-xs border-red-500 text-red-600")

        with register_view:
            with ui.card().classes("w-full max-w-sm rounded-3xl shadow-2xl overflow-hidden p-0"):
                with ui.column().classes("w-full bg-gradient-to-r from-emerald-500 via-teal-600 to-cyan-600 p-5 items-center text-white"):
                    ui.icon("person_add", size="2.5rem"); ui.label("Create Account").classes("text-xl font-extrabold")
                with ui.column().classes("w-full p-5 bg-white gap-3"):
                    uname = ui.input("User name").props("outlined rounded dense").classes("w-full")
                    email = ui.input("Email id").props("outlined rounded dense").classes("w-full")
                    pwd = ui.input("Password", password=True, password_toggle_button=True).props("outlined rounded dense").classes("w-full")
                    re_pwd = ui.input("Retype password", password=True, password_toggle_button=True).props("outlined rounded dense").classes("w-full")
                    def handle_register():
                        u_val = (uname.value or "").strip(); e_val = (email.value or "").strip(); p_val = pwd.value or ""; rp_val = re_pwd.value or ""
                        if not u_val or not e_val: ui.notify("Enter User name and Email!", type="warning", position="top"); return
                        if len(p_val) < 6: ui.notify("Min 6 chars!", type="negative", position="top"); return
                        if p_val != rp_val: ui.notify("Not same!", type="negative", position="top"); return
                        if AppUser.objects.filter(email=e_val).exists(): ui.notify("Already registered!", type="negative", position="top"); return
                        user = AppUser.objects.create(username=u_val, email=e_val, password=make_password(p_val), default_report_title="Veraval site daily progress report")
                        CACHE["users"][e_val] = user
                        pwd_key = hashlib.sha256(f"{e_val}:{p_val}".encode()).hexdigest()
                        CACHE["pwd_verified"][pwd_key] = user.id
                        app.storage.user["saved_email"] = e_val
                        app.storage.user["saved_password"] = p_val
                        ui.notify("Account created! Login now!", type="positive", position="top")
                        show_login()
                    ui.button("Register", icon="check_circle", on_click=handle_register).props("rounded no-caps").classes("w-full py-2.5 mt-1 bg-gradient-to-r from-emerald-500 to-teal-600 text-white font-bold text-base shadow-lg")
                    ui.button("Back", icon="arrow_back", on_click=show_login).props("flat no-caps").classes("back-btn w-full font-semibold text-sm mt-1")

        async def handle_login():
            email = (email_input.value or "").strip()
            pwd = pass_input.value or ""
            if not email or not pwd:
                ui.notify("Enter Email & Password!", type="warning", position="top")
                return
            pwd_key = hashlib.sha256(f"{email}:{pwd}".encode()).hexdigest()
            if pwd_key in CACHE["pwd_verified"]:
                user_id = CACHE["pwd_verified"][pwd_key]
                user = CACHE["users"].get(email)
                if not user:
                    user = AppUser.objects.filter(id=user_id).first()
                    if user:
                        CACHE["users"][email] = user
                if user:
                    state["user"] = user
                    app.storage.user["logged_in_user_id"] = user.id
                    app.storage.user["saved_email"] = email
                    app.storage.user["saved_password"] = pwd
                    show_home()
                    return
            status_label.set_text("⏳ Checking...")
            login_btn.props("loading")
            def get_user_quick():
                if email in CACHE["users"]:
                    return CACHE["users"][email]
                try:
                    return AppUser.objects.get(email=email)
                except AppUser.DoesNotExist:
                    return None
            quick_user = await run.io_bound(get_user_quick)
            if not quick_user:
                status_label.set_text("❌ User not found")
                ui.notify("User not found! Register first.", type="negative", position="top")
                login_btn.props(remove="loading")
                return
            state["user"] = quick_user
            app.storage.user["saved_email"] = email
            app.storage.user["saved_password"] = pwd
            show_home()
            login_btn.props(remove="loading")
            async def background_verify():
                def verify():
                    return check_password(pwd, quick_user.password)
                is_valid = await run.io_bound(verify)
                if is_valid:
                    CACHE["users"][email] = quick_user
                    CACHE["pwd_verified"][pwd_key] = quick_user.id
                    app.storage.user["logged_in_user_id"] = quick_user.id
                else:
                    ui.notify("❌ Invalid password!", type="negative", position="top")
                    await run.io_bound(lambda: time.sleep(0.8))
                    show_login_as_logout()
                    status_label.set_text("❌ Invalid password")
            ui.timer(0.1, lambda: background_verify(), once=True)

        login_btn.on_click(handle_login)
        reg_btn.on_click(show_register)
        print("🔒 Always Login First - Date Repair", flush=True)
        show_login()

@app.get("/health")
def health_check():
    return {"status": "ok", "mode": "Date Design Repair", "cache": {"users": len(CACHE["users"]), "pwd": len(CACHE["pwd_verified"])}}

if __name__ in {"__main__", "__mp_main__"}:
    print(f"🚀 Date Design Repaired! Starting on 0.0.0.0:{PORT}", flush=True)
    # CRITICAL FIX for Render: Must bind to 0.0.0.0, not 127.0.0.1
    # This allows Render to detect open port and avoids "Port scan timeout"
    # Works on any PC/Mobile because Render forwards public traffic to 0.0.0.0
    ui.run(host="0.0.0.0", port=PORT, title="Date Repair", storage_secret=STORAGE_SECRET, reload=False, show=False, dark=False)
