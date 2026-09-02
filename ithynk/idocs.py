import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin

from playwright.sync_api import sync_playwright

from ithynk.extractor import extract_to_workbook


class IDocsRobot:
    def __init__(self, settings, email, password, log):
        self.s = settings
        self.email = email
        self.password = password
        self.log = log
        self.root = Path.home() / "AppData" / "Local" / "iThynk"
        self.diag = self.root / "diagnostics"
        self.reports = self.root / "calibration-reports"
        self.diag.mkdir(parents=True, exist_ok=True)
        self.reports.mkdir(parents=True, exist_ok=True)
        self.pw = self.context = self.page = None

    def start(self):
        self.pw = sync_playwright().start()
        self.context = self.pw.chromium.launch_persistent_context(
            str(self.root / "browser-profile"),
            headless=bool(self.s.get("headless", False)),
            accept_downloads=False,
            viewport={"width": 1440, "height": 900},
        )
        self.page = self.context.pages[0] if self.context.pages else self.context.new_page()
        self.login()

    def stop(self):
        if self.context:
            self.context.close()
        if self.pw:
            self.pw.stop()

    def login(self):
        self.log("Opening iDocs")
        self.page.goto(self.s["idocs_url"], wait_until="domcontentloaded", timeout=60000)
        if "dashboard" in self.page.url.lower():
            self.log("Existing iDocs session restored")
            return

        email_box = self.page.get_by_label("Email")
        password_box = self.page.get_by_label("Password")
        if not email_box.count():
            email_box = self.page.locator('input[type="email"], input[name*="email" i]').first
        if not password_box.count():
            password_box = self.page.locator('input[type="password"]').first
        if not email_box.count() or not password_box.count():
            raise RuntimeError("Could not locate the iDocs login fields")

        email_box.fill(self.email)
        password_box.fill(self.password)
        checkbox = self.page.locator('input[type="checkbox"]').first
        if checkbox.count() and not checkbox.is_checked():
            checkbox.check()

        sign_in = self.page.get_by_role("button", name=re.compile(r"sign\s*in|login", re.I)).first
        if not sign_in.count():
            sign_in = self.page.locator('button[type="submit"], input[type="submit"]').first
        if not sign_in.count():
            raise RuntimeError("Could not locate the iDocs Sign In button")
        sign_in.click()
        self.page.wait_for_load_state("domcontentloaded")
        self.page.wait_for_timeout(1500)
        if "dashboard" not in self.page.url.lower():
            raise RuntimeError("iDocs login did not reach the dashboard")
        self.log("Logged in to iDocs")

    def process(self, rsa_id, ref):
        try:
            self.log(f"{ref}: searching iDocs")
            consumers = self.page.get_by_role("button", name=re.compile(r"consumers?", re.I)).first
            if not consumers.count():
                consumers = self.page.get_by_text("Consumers", exact=True).first
            if not consumers.count():
                raise RuntimeError("Could not locate Consumers in iDocs")
            consumers.click()

            search = self.page.get_by_placeholder(re.compile("search", re.I)).first
            if not search.count():
                search = self.page.locator('input[type="search"], input[name*="search" i]').first
            if not search.count():
                raise RuntimeError("Could not locate the consumer search field")
            search.fill(rsa_id)

            search_button = self.page.get_by_role("button", name=re.compile(r"^search$", re.I)).first
            if search_button.count():
                search_button.click()
            else:
                search.press("Enter")
            self.page.wait_for_timeout(1200)

            row = self.page.locator("table tbody tr").filter(has_text=rsa_id[-4:]).first
            if not row.count():
                return {
                    "ProcessStatus": "Consumer Not Found",
                    "RobotStatus": "Needs Review",
                    "FailureReason": "RSA ID not found",
                }

            applicant = self._status(row.inner_text())
            if applicant and applicant not in self.s.get("accepted_statuses", []):
                return {
                    "ProcessStatus": "Status Not Accepted",
                    "IDocsApplicantStatus": applicant,
                    "RobotStatus": "Needs Review",
                    "FailureReason": "",
                }

            link = row.get_by_title(re.compile(r"view.*record", re.I)).first
            if not link.count():
                link = row.locator("a").last
            if not link.count():
                raise RuntimeError("Could not open the matching consumer record")
            link.click()
            self.page.wait_for_timeout(700)

            credit_heading = self.page.get_by_text("Credit Checks", exact=True).first
            if not credit_heading.count():
                credit_heading = self.page.get_by_text(re.compile(r"credit\s*checks?", re.I)).first
            if not credit_heading.count():
                raise RuntimeError("Could not locate Credit Checks")
            credit_heading.scroll_into_view_if_needed()

            credit = self.page.locator("table tbody tr").filter(has_text=re.compile(r"completed", re.I)).first
            if not credit.count():
                return {
                    "ProcessStatus": "Needs Review",
                    "CreditCheckStatus": "Not Found",
                    "RobotStatus": "Needs Review",
                    "FailureReason": "Completed credit check not found",
                }
            credit_link = credit.locator("a").last
            if not credit_link.count():
                raise RuntimeError("Completed credit check has no view link")
            credit_link.click()
            self.page.wait_for_timeout(700)

            attachments = self.page.get_by_text("Attachments", exact=True).first
            if not attachments.count():
                attachments = self.page.get_by_text(re.compile(r"attachments?", re.I)).first
            if attachments.count():
                attachments.scroll_into_view_if_needed()

            # Calibration intentionally targets the PDF only. XML is ignored because
            # the purpose of this build is to prove what can be read from the PDF preview.
            pdf = self.page.locator("a").filter(has_text=re.compile(r"\.pdf(?:\s|$)", re.I)).first
            if not pdf.count():
                pdf = self.page.locator('a[href*=".pdf" i]').first
            if not pdf.count():
                return {
                    "ProcessStatus": "Needs Review",
                    "CreditCheckStatus": "Completed",
                    "AttachmentFound": False,
                    "RobotStatus": "Needs Review",
                    "FailureReason": "No PDF credit report found",
                }

            pdf.scroll_into_view_if_needed()
            href = pdf.get_attribute("href")
            if not href or href.strip().lower().startswith(("javascript:", "blob:", "#")):
                return {
                    "ProcessStatus": "Needs Review",
                    "CreditCheckStatus": "Completed",
                    "AttachmentFound": True,
                    "RobotStatus": "Needs Review",
                    "FailureReason": "PDF was found but its preview URL is not directly readable yet",
                }

            pdf_url = urljoin(self.page.url, href)
            self.log(f"{ref}: reading PDF preview in memory")
            response = self.context.request.get(pdf_url, timeout=60000)
            if not response.ok:
                raise RuntimeError(f"Credit report request failed ({response.status})")
            pdf_bytes = response.body()
            if not pdf_bytes.startswith(b"%PDF"):
                raise RuntimeError("The iDocs attachment did not return PDF data")

            report_path = self.reports / f"iThynk-pdf-preview-{ref}-{datetime.now():%Y%m%d-%H%M%S}.xlsx"
            report_path, verification, extracted, pages = extract_to_workbook(
                pdf_bytes,
                report_path,
                rsa_id,
                Path(href.split("?", 1)[0]).name or "iDocs PDF preview",
            )
            preview = [item.as_preview() for item in extracted]
            source_text = "\n\n".join(f"--- Page {page_number} ---\n{text}" for page_number, text in pages)
            completed = verification == "Verified"
            self.log(f"{ref}: PDF read successfully; {len(pages)} page(s) inspected")
            self.log(f"{ref}: calibration workbook created: {report_path}")
            return {
                "ProcessStatus": "Calibration Complete" if completed else "Manual Review",
                "IDocsApplicantStatus": applicant or "Unknown",
                "CreditCheckStatus": "Completed",
                "AttachmentFound": True,
                "RobotStatus": "Completed" if completed else "Needs Review",
                "FailureReason": "" if completed else f"Document ID check: {verification}",
                "CalibrationReport": str(report_path),
                "DocumentIDCheck": verification,
                "ExtractedFields": preview,
                "SourceText": source_text,
            }
        except Exception as exc:
            self.capture(ref)
            return {
                "ProcessStatus": "Failed",
                "RobotStatus": "Failed",
                "FailureReason": str(exc)[:250],
            }

    def capture(self, ref):
        if not self.page:
            return
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        try:
            self.page.screenshot(path=str(self.diag / f"{ref}-{stamp}.png"), full_page=True)
            (self.diag / f"{ref}-{stamp}.html").write_text(self.page.content(), "utf-8")
        except Exception:
            pass

    def calibration(self, rsa_id):
        digits = re.sub(r"\D", "", rsa_id)
        if len(digits) != 13:
            raise ValueError("Enter a valid 13-digit South African ID number")
        return self.process(digits, f"TEST-{digits[-4:]}")

    @staticmethod
    def _status(text):
        for status in ("Created Applicant", "Budgets Generated", "Signed", "Form16 Sent"):
            if status.lower() in str(text).lower():
                return status
        return ""
