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
                                                            ui.label(f"Area: {report.area_name} | Date: {report.report_date.strftime('%d-%m-%Y')} | Total: {report.total_qty} Qty").classes("text-xs text-slate-600")
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
                                    rows = [{"sr_no": 1, "pipe_dia": "63MM PVC", "quantity": t63, "unit": "6 MTR"}, {"sr_no": 2, "pipe_dia": "90MM PVC", "quantity": t90, "unit": "12 MTR"}, {"sr_no": 3, "pipe_dia": "110MM PVC", "quantity": t110, "unit": "18 MTR"}, {"sr_no": 4, "pipe_dia": "150MM DI", "quantity": t150, "unit": "5.5 MTR"}]
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
                            with ui.row().classes("w-full items-center gap-2"):
                                ui.icon("location_on", color="green"); ui.label(report.area_name or "No Area").classes("font-extrabold text-base text-green-900")
                        with ui.column().classes("w-full rounded-2xl overflow-hidden shadow-lg border-2 border-indigo-900 gap-0 mb-4"):
                            with ui.grid(columns=4).classes("w-full bg-gradient-to-r from-emerald-500 via-green-500 to-teal-500 text-white font-extrabold text-center"):
                                ui.label("63MM PVC").classes("py-2 text-[10px]"); ui.label("90MM PVC").classes("py-2 text-[10px] border-x border-white/30"); ui.label("110MM PVC").classes("py-2 text-[10px] border-r border-white/30"); ui.label("150MM DI").classes("py-2 text-[10px]")
                            with ui.grid(columns=4).classes("w-full bg-white text-center items-center"):
                                ui.label(f"{get_q(report,'qty_63mm')}").classes("py-2 font-extrabold text-xs"); ui.label(f"{get_q(report,'qty_90mm')}").classes("py-2 font-extrabold text-xs border-x border-gray-200"); ui.label(f"{get_q(report,'qty_110mm')}").classes("py-2 font-extrabold text-xs border-r border-gray-200"); ui.label(f"{get_q(report,'qty_150mm')}").classes("py-2 font-extrabold text-xs bg-green-50 text-green-700")
                            with ui.grid(columns=4).classes("w-full bg-green-50 text-center border-y border-indigo-900 items-center"):
                                ui.label(f"{int(get_q(report,'qty_63mm')*6)} MTR").classes("py-1.5 font-bold text-[10px]"); ui.label(f"{int(get_q(report,'qty_90mm')*12)} MTR").classes("py-1.5 font-bold text-[10px] border-x border-gray-200"); ui.label(f"{int(get_q(report,'qty_110mm')*18)} MTR").classes("py-1.5 font-bold text-[10px] border-r border-gray-200"); ui.label(f"{get_q(report,'qty_150mm')*5.5} MTR").classes("py-1.5 font-bold text-[10px] bg-green-50")
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
                                            delete_dialo
