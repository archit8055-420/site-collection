"""
FORGOT PASSWORD - REAL EMAIL + 6 DIGIT PASSWORD ONLY
- Site password: exactly 6 digits (e.g., 123456)
- Gmail 16-digit App Password is only for sending email (backend), not for user
"""
import os, datetime, csv, io, secrets, hashlib, time, smtplib, ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

print("🚀 6-DIGIT PASSWORD + REAL EMAIL Loading...", flush=True)
os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"
from nicegui import ui, app, run

CACHE = {"users": {}, "areas": {}, "pwd_verified": {}, "reset_tokens": {}}

from db_setup import init_django
init_django()
from models_app.models import AppUser, SavedArea, DailyReport
from django.contrib.auth.hashers import make_password, check_password
from django.db.models import Sum

PORT = int(os.getenv("PORT", "8080"))
STORAGE_SECRET = os.getenv("STORAGE_SECRET", "my_persistent_secret_key_123")

def send_reset_email(to_email, username, reset_link):
    host = os.getenv("EMAIL_HOST", "")
    port = int(os.getenv("EMAIL_PORT", "587"))
    user = os.getenv("EMAIL_USER", "")
    pwd = os.getenv("EMAIL_PASSWORD", "")
    from_email = os.getenv("EMAIL_FROM", user)
    if not host or not user or not pwd:
        print(f"⚠️ EMAIL NOT CONFIGURED - Would send to {to_email}: {reset_link}", flush=True)
        return False, "Email not configured. Set EMAIL_HOST, EMAIL_USER, EMAIL_PASSWORD in Render."
    try:
        msg = MIMEMultipart()
        msg['From'] = from_email
        msg['To'] = to_email
        msg['Subject'] = "Reset Your Password - Site Collection"
        body = f"Hello {username}, Reset link (6-digit password): {reset_link} Valid 15 min."
        html_body = f"""
<html><body style="font-family: Arial; padding:20px; background:#f5f5f5;">
<div style="max-width:500px; margin:0 auto; background:white; padding:30px; border-radius:16px;">
<h2 style="color:#059669;">Welcome {username}!</h2>
<p>Reset your site password (6-digit only) for: <b>{to_email}</b></p>
<a href="{reset_link}" style="display:inline-block; background:#059669; color:white; padding:12px 24px; text-decoration:none; border-radius:9999px; font-weight:bold;">Reset Password (6-digit)</a>
<p style="font-size:11px; color:#999; word-break:break-all; margin-top:15px;">{reset_link}</p>
<p style="font-size:11px; color:#666;">New password must be exactly 6 digits (e.g., 123456). Valid 15 min.</p>
</div></body></html>
"""
        msg.attach(MIMEText(body, 'plain'))
        msg.attach(MIMEText(html_body, 'html'))
        context = ssl.create_default_context()
        with smtplib.SMTP(host, port) as server:
            server.starttls(context=context)
            server.login(user, pwd)
            server.sendmail(from_email, to_email, msg.as_string())
        print(f"✅ RESET EMAIL SENT to {to_email}", flush=True)
        return True, "Email sent!"
    except Exception as e:
        print(f"❌ EMAIL FAILED to {to_email}: {e}", flush=True)
        return False, str(e)

def is_valid_6digit(pwd):
    """Check if password is exactly 6 digits"""
    return pwd and len(pwd) == 6 and pwd.isdigit()

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
                if not token or token not in CACHE["reset_tokens"]:
                    ui.icon("error", size="2rem", color="red")
                    ui.label("Invalid or Expired Link!").classes("text-red-600 font-bold text-center w-full")
                    ui.button("Go to Login", icon="login", on_click=lambda: ui.navigate.to("/")).props("rounded no-caps").classes("w-full mt-3 bg-blue-600 text-white font-bold")
                    return
                data = CACHE["reset_tokens"][token]
                if time.time() - data["created_at"] > 900:
                    CACHE["reset_tokens"].pop(token, None)
                    ui.icon("timer_off", size="2rem", color="red")
                    ui.label("Link Expired! (15 min over)").classes("text-red-600 font-bold text-center w-full")
                    ui.button("Go to Login", icon="login", on_click=lambda: ui.navigate.to("/")).props("rounded no-caps").classes("w-full mt-2 bg-blue-600 text-white font-bold")
                    return
                email = data["email"]
                try:
                    user = AppUser.objects.get(email=email)
                except:
                    ui.label("User not found!").classes("text-red-600 font-bold text-center w-full")
                    ui.button("Go to Login", icon="login", on_click=lambda: ui.navigate.to("/")).props("rounded no-caps").classes("w-full mt-2 bg-blue-600 text-white font-bold")
                    return
                ui.label(f"Welcome {user.username}").classes("text-lg font-extrabold text-slate-900 text-center w-full")
                ui.label(f"For this email: {email}").classes("text-xs font-bold text-slate-600 text-center w-full break-all")
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
                        CACHE["reset_tokens"].pop(token, None)
                        content_col.clear()
                        with content_col:
                            ui.icon("check_circle", size="3rem", color="green")
                            ui.label("Successfully changed password!").classes("text-base font-extrabold text-green-700 text-center w-full mt-2")
                            ui.label("You can now go to app or site and log in with 6-digit password").classes("text-xs font-bold text-slate-600 text-center w-full mt-1")
                            ui.button("Go to Login", icon="login", on_click=lambda: ui.navigate.to("/")).props("rounded no-caps").classes("w-full mt-4 bg-gradient-to-r from-emerald-600 to-green-600 text-white font-bold py-2.5 shadow-lg")
                    except Exception as e:
                        status_lbl.set_text(f"❌ Failed: {e}")
                ui.button("Confirm (6-digit)", icon="check", on_click=do_confirm_reset).props("rounded no-caps").classes("w-full mt-2 bg-gradient-to-r from-emerald-600 to-green-600 text-white font-bold py-2.5 shadow-lg")

@ui.page("/")
def main_spa_page():
    print("🚀 6-DIGIT PASSWORD Flow Loading", flush=True)
    state = {"user": None, "selected_report": None}
    with ui.column().classes("w-full min-h-screen p-0 m-0 gap-0") as root:
        login_view = ui.column().classes("w-full min-h-screen items-center justify-center bg-gradient-to-br from-indigo-900 via-purple-900 to-slate-900 p-3")
        with login_view:
            with ui.card().classes("w-full max-w-sm rounded-3xl shadow-2xl overflow-hidden p-0 border-2 border-green-400/50"):
                with ui.column().classes("w-full bg-gradient-to-r from-emerald-500 via-green-600 to-teal-600 p-4 items-center text-white"):
                    ui.icon("bolt", size="2.5rem")
                    ui.label("FINAL DIALOG + EDITABLE").classes("text-xl font-extrabold")
                    ui.label("⚡ 6-Digit Secure Login").classes("text-xs")
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
                        ui.label("Forgot Password").classes("text-xl font-extrabold")
                        ui.label("Enter your Email ID (6-digit reset)").classes("text-xs")
                    with ui.column().classes("w-full p-5 bg-white gap-3"):
                        forgot_email = ui.input("Email ID", placeholder="Enter registered Email").props("outlined rounded dense").classes("w-full")
                        forgot_status = ui.label("").classes("text-xs font-bold text-center w-full")
                        link_display = ui.column().classes("w-full gap-2")
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
                            CACHE["reset_tokens"][token] = {"email": email, "created_at": time.time()}
                            base_url = os.getenv("RENDER_EXTERNAL_URL", os.getenv("BASE_URL", "https://site-collection.onrender.com"))
                            if "localhost" in base_url or not base_url:
                                base_url = "https://site-collection.onrender.com"
                            reset_link = f"{base_url}/reset/{token}"
                            success, msg = send_reset_email(email, user.username, reset_link)
                            if success:
                                forgot_status.set_text("✅ Reset link sent to your Email! (6-digit new password, 15 min valid)")
                                link_display.clear()
                                with link_display:
                                    ui.label("Check inbox & spam folder.").classes("text-xs font-bold text-green-600 text-center w-full mt-2")
                            else:
                                forgot_status.set_text(f"⚠️ {msg} - Showing link below")
                                link_display.clear()
                                with link_display:
                                    ui.label("Email not configured - Your reset link (6-digit):").classes("text-[10px] font-bold text-slate-500 text-center w-full mt-2")
                                    with ui.card().classes("w-full p-2 bg-blue-50 border border-blue-200 rounded-xl"):
                                        ui.label(reset_link).classes("text-[10px] font-bold text-blue-700 break-all w-full")
                                    ui.button("Open Reset Page", icon="open_in_new", on_click=lambda: ui.navigate.to(reset_link)).props("rounded no-caps dense").classes("w-full bg-blue-600 text-white font-bold text-xs mt-2")
                            print(f"🔑 RESET LINK for {email}: {reset_link}", flush=True)
                        ui.button("Send Reset Link (6-digit)", icon="send", on_click=send_reset_link).props("rounded no-caps").classes("w-full py-2.5 bg-gradient-to-r from-blue-600 to-indigo-600 text-white font-bold shadow-lg")
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
                                                            ui.label(f"✏️ Edit - {area_display}").classes("font-extrabold text-sm text-white")
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
                                        ui.label(f"Email: {user.email} and all reports, areas linked to this account will be removed permanently.").classes("text-xs text-slate-600 leading-relaxed")
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
            # Validate 6-digit for login too
            if not is_valid_6digit(pwd):
                ui.notify("Password must be exactly 6 digits!", type="warning", position="top")
                return
            pwd_key = hashlib.sha256(f"{email}:{pwd}".encode()).hexdigest()
            if pwd_key in CACHE["pwd_verified"]:
                user_id = CACHE["pwd_verified"][pwd_key]
                user = CACHE["users"].get(email)
                if not user:
                    def fetch_cached_user():
                        try:
                            return AppUser.objects.get(id=user_id)
                        except:
                            return None
                    user = await run.io_bound(fetch_cached_user)
                    if user:
                        CACHE["users"][email] = user
                if user:
                    state["user"] = user
                    app.storage.user["logged_in_user_id"] = user.id
                    app.storage.user["saved_email"] = email
                    app.storage.user["saved_password"] = pwd
                    status_label.set_text("✅ Logged in")
                    show_home()
                    return
            status_label.set_text("⏳ Verifying...")
            login_btn.props("loading")
            def get_user_and_check():
                try:
                    u = AppUser.objects.get(email=email)
                except AppUser.DoesNotExist:
                    return None, False
                is_ok = check_password(pwd, u.password)
                return u, is_ok
            quick_user, is_valid = await run.io_bound(get_user_and_check)
            login_btn.props(remove="loading")
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

        login_btn.on_click(handle_login)
        reg_btn.on_click(show_register)
        forgot_link.on("click", show_forgot)
        print("🔒 6-DIGIT PASSWORD + REAL EMAIL Ready", flush=True)
        show_login()

@app.get("/health")
def health_check():
    return {"status": "ok", "mode": "6-Digit Real Email", "reset_tokens": len(CACHE["reset_tokens"])}

if __name__ in {"__main__", "__mp_main__"}:
    print(f"🚀 6-Digit Password Starting on 0.0.0.0:{PORT}", flush=True)
    ui.run(host="0.0.0.0", port=PORT, title="6-Digit Password", storage_secret=STORAGE_SECRET, reload=False, show=False, dark=False)
