import os
import queue
import re
import threading
from datetime import datetime, timezone

import customtkinter as ctk

from ithynk.idocs import IDocsRobot
from ithynk.sharepoint import SharePointQueue
from ithynk.store import get_idocs_credentials, load_settings, save_idocs_credentials, save_settings

ctk.set_appearance_mode("dark")


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("iThynk v1.2 PDF Reader Calibration")
        self.geometry("1180x820")
        self.minsize(1040, 720)
        self.configure(fg_color="#100f0e")
        self.events = queue.Queue()
        self.stop_event = threading.Event()
        self.settings = load_settings()
        self.last_preview_text = ""
        self._ui()
        self.after(150, self._drain)

    def _ui(self):
        header = ctk.CTkFrame(self, fg_color="#191715", corner_radius=0)
        header.pack(fill="x")
        ctk.CTkLabel(header, text="iThynk", font=("Segoe UI", 28, "bold"), text_color="#f47920").pack(side="left", padx=24, pady=18)
        ctk.CTkLabel(header, text="iDocs PDF Reader Calibration", text_color="#aaa29a").pack(side="left")

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=20, pady=20)

        left = ctk.CTkScrollableFrame(body, fg_color="#191715", width=330)
        left.pack(side="left", fill="y", padx=(0, 12))
        right = ctk.CTkFrame(body, fg_color="#191715")
        right.pack(side="left", fill="both", expand=True)

        ctk.CTkLabel(left, text="iDocs Test Settings", font=("Segoe UI", 16, "bold")).pack(anchor="w", padx=16, pady=(16, 8))
        self.inputs = {}
        email, password = get_idocs_credentials()
        fields = [
            ("iDocs URL", "idocs_url"),
            ("iDocs Email", "idocs_email"),
            ("iDocs Password", "idocs_password"),
        ]
        for label, key in fields:
            ctk.CTkLabel(left, text=label, text_color="#aaa29a").pack(anchor="w", padx=16)
            entry = ctk.CTkEntry(left, width=295, show="*" if key == "idocs_password" else "")
            entry.pack(padx=16, pady=(3, 9))
            value = password if key == "idocs_password" and password else email if key == "idocs_email" and email else self.settings.get(key, "")
            entry.insert(0, value or "")
            self.inputs[key] = entry

        ctk.CTkLabel(left, text="Test RSA ID", text_color="#aaa29a").pack(anchor="w", padx=16)
        self.calibration_id = ctk.CTkEntry(left, width=295, placeholder_text="13-digit authorised test ID")
        self.calibration_id.pack(padx=16, pady=(3, 9))

        self.calibrate_btn = ctk.CTkButton(left, text="Read iDocs PDF", fg_color="#2f6f59", command=self.start_calibration)
        self.calibrate_btn.pack(fill="x", padx=16, pady=(3, 7))
        self.copy_btn = ctk.CTkButton(left, text="Copy All Fields", fg_color="#4a4642", state="disabled", command=self.copy_preview)
        self.copy_btn.pack(fill="x", padx=16, pady=(0, 7))
        self.open_reports_btn = ctk.CTkButton(left, text="Open Excel Reports", fg_color="#4a4642", command=self.open_reports)
        self.open_reports_btn.pack(fill="x", padx=16, pady=(0, 7))

        ctk.CTkLabel(left, text="Live SharePoint Robot", font=("Segoe UI", 14, "bold")).pack(anchor="w", padx=16, pady=(16, 6))
        ctk.CTkLabel(left, text="Disabled for calibration until field mapping is approved.", wraplength=285, justify="left", text_color="#aaa29a").pack(anchor="w", padx=16, pady=(0, 16))

        tabs = ctk.CTkTabview(right, fg_color="#191715", segmented_button_selected_color="#f47920")
        tabs.pack(fill="both", expand=True, padx=12, pady=12)
        tabs.add("PDF Data Preview")
        tabs.add("Raw PDF Text")
        tabs.add("Activity Log")

        preview_tab = tabs.tab("PDF Data Preview")
        self.summary_label = ctk.CTkLabel(preview_tab, text="No PDF read yet.", anchor="w", justify="left", text_color="#aaa29a")
        self.summary_label.pack(fill="x", padx=12, pady=(12, 6))
        self.preview_box = ctk.CTkTextbox(preview_tab, fg_color="#100f0e", text_color="#eee7df", font=("Consolas", 12))
        self.preview_box.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        raw_tab = tabs.tab("Raw PDF Text")
        self.raw_box = ctk.CTkTextbox(raw_tab, fg_color="#100f0e", text_color="#ddd5cd", font=("Consolas", 11))
        self.raw_box.pack(fill="both", expand=True, padx=12, pady=12)

        log_tab = tabs.tab("Activity Log")
        self.logbox = ctk.CTkTextbox(log_tab, fg_color="#100f0e", text_color="#ddd5cd")
        self.logbox.pack(fill="both", expand=True, padx=12, pady=12)
        self.log("iThynk ready. Enter authorised iDocs details and one test ID, then select Read iDocs PDF.")

    def log(self, msg):
        self.events.put(("log", f"[{datetime.now():%H:%M:%S}] {msg}"))

    def _drain(self):
        while not self.events.empty():
            kind, payload = self.events.get()
            if kind == "log":
                self.logbox.insert("end", payload + "\n")
                self.logbox.see("end")
            elif kind == "preview":
                self._show_preview(payload)
        self.after(150, self._drain)

    def start_calibration(self):
        rsa_id = re.sub(r"\D", "", self.calibration_id.get())
        if len(rsa_id) != 13:
            self.log("Calibration requires one authorised 13-digit RSA ID.")
            return

        idocs_url = self.inputs["idocs_url"].get().strip()
        email = self.inputs["idocs_email"].get().strip()
        password = self.inputs["idocs_password"].get().strip()
        if not idocs_url or not email or not password:
            self.log("Enter the authorised iDocs URL, email and password first.")
            return

        save_idocs_credentials(email, password)
        settings = dict(self.settings)
        settings.update({
            "idocs_url": idocs_url,
            "headless": False,
            "accepted_statuses": ["Created Applicant", "Budgets Generated", "Signed", "Form16 Sent"],
        })
        self.settings.update({"idocs_url": idocs_url})
        save_settings(self.settings)
        self.calibrate_btn.configure(state="disabled")
        self.copy_btn.configure(state="disabled")
        self.preview_box.delete("1.0", "end")
        self.raw_box.delete("1.0", "end")
        self.summary_label.configure(text="Reading iDocs PDF...")
        threading.Thread(target=self._run_calibration, args=(settings, email, password, rsa_id), daemon=True).start()

    def _run_calibration(self, settings, email, password, rsa_id):
        robot = None
        try:
            self.log(f"Starting PDF calibration for *********{rsa_id[-4:]}")
            robot = IDocsRobot(settings, email, password, self.log)
            robot.start()
            result = robot.calibration(rsa_id)
            self.log(f"Calibration result: {result.get('ProcessStatus')}")
            if result.get("FailureReason"):
                self.log(f"Reason: {result.get('FailureReason')}")
            self.events.put(("preview", result))
        except Exception as exc:
            self.log(f"Calibration failed: {str(exc)[:300]}")
            self.events.put(("preview", {"ProcessStatus": "Failed", "FailureReason": str(exc)[:300]}))
        finally:
            if robot:
                robot.stop()
            self.after(0, lambda: self.calibrate_btn.configure(state="normal"))

    def _show_preview(self, result):
        fields = result.get("ExtractedFields") or []
        source_text = result.get("SourceText") or ""
        status = result.get("ProcessStatus", "Unknown")
        verification = result.get("DocumentIDCheck", "Not available")
        reason = result.get("FailureReason", "")
        self.summary_label.configure(text=f"Status: {status}   |   Document ID Check: {verification}" + (f"   |   {reason}" if reason else ""))

        lines = []
        for item in fields:
            field = str(item.get("field", ""))
            value = str(item.get("value", ""))
            page = item.get("page") or "-"
            review = item.get("review_required", "")
            lines.append(f"{field:<20} : {value}\n  Page: {page} | Review Required: {review}")
        if not lines:
            lines = ["No structured fields were extracted. Check Raw PDF Text and Activity Log for details."]
        preview_text = "\n\n".join(lines)
        self.preview_box.delete("1.0", "end")
        self.preview_box.insert("1.0", preview_text)
        self.raw_box.delete("1.0", "end")
        self.raw_box.insert("1.0", source_text or "No raw selectable PDF text was returned.")
        self.last_preview_text = preview_text
        self.copy_btn.configure(state="normal" if fields else "disabled")

    def copy_preview(self):
        if not self.last_preview_text:
            return
        self.clipboard_clear()
        self.clipboard_append(self.last_preview_text)
        self.update()
        self.log("Extracted PDF fields copied to clipboard.")

    def open_reports(self):
        path = os.path.join(os.path.expanduser("~"), "AppData", "Local", "iThynk", "calibration-reports")
        os.makedirs(path, exist_ok=True)
        os.startfile(path)

    # Kept for the next release. It is intentionally not exposed in the calibration UI.
    def _run_sharepoint_robot(self):
        robot = None
        try:
            email, password = get_idocs_credentials()
            sp = SharePointQueue(self.settings, self.log)
            sp.connect()
            robot = IDocsRobot(self.settings, email, password, self.log)
            robot.start()
            while not self.stop_event.is_set():
                for item in sp.waiting():
                    if self.stop_event.is_set():
                        break
                    fields = item["fields"]
                    ref = str(fields.get("SubmissionRef") or item["id"])
                    rsa = str(fields.get("RSAIDNumber") or fields.get("RSA_x0020_ID_x0020_Number") or "")
                    if not rsa:
                        sp.update(item["id"], {"ProcessStatus": "Failed", "RobotStatus": "Failed", "FailureReason": "RSA ID missing"})
                        continue
                    sp.update(item["id"], {"ProcessStatus": "Checking iDocs", "RobotStatus": "Running", "RobotStartedAt": datetime.now(timezone.utc).isoformat()})
                    result = robot.process(rsa, ref)
                    result.pop("ExtractedFields", None)
                    result.pop("SourceText", None)
                    result["RobotCompletedAt"] = datetime.now(timezone.utc).isoformat()
                    sp.update(item["id"], result)
                self.stop_event.wait(int(self.settings.get("poll_seconds", 15)))
        finally:
            if robot:
                robot.stop()


if __name__ == "__main__":
    App().mainloop()
