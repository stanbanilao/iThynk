import re
from datetime import datetime
from pathlib import Path
from playwright.sync_api import sync_playwright
from ithynk.extractor import extract_to_workbook
class IDocsRobot:
    def __init__(self,settings,email,password,log):
        self.s,self.email,self.password,self.log=settings,email,password,log
        self.root=Path.home()/"AppData"/"Local"/"iThynk"
        self.diag,self.reports=self.root/"diagnostics",self.root/"calibration-reports"
        self.diag.mkdir(parents=True,exist_ok=True); self.reports.mkdir(parents=True,exist_ok=True)
        self.pw=self.context=self.page=None
    def start(self):
        self.pw=sync_playwright().start()
        self.context=self.pw.chromium.launch_persistent_context(str(self.root/"browser-profile"),headless=bool(self.s.get("headless",False)),accept_downloads=True,viewport={"width":1440,"height":900})
        self.page=self.context.pages[0] if self.context.pages else self.context.new_page()
        self.login()
    def stop(self):
        if self.context: self.context.close()
        if self.pw: self.pw.stop()
    def login(self):
        self.log("Opening iDocs")
        self.page.goto(self.s["idocs_url"],wait_until="domcontentloaded",timeout=60000)
        if "dashboard" in self.page.url: self.log("Existing iDocs session restored"); return
        self.page.get_by_label("Email").fill(self.email)
        self.page.get_by_label("Password").fill(self.password)
        checkbox=self.page.locator('input[type="checkbox"]').first
        if checkbox.count() and not checkbox.is_checked(): checkbox.check()
        self.page.get_by_role("button",name="Sign In").click()
        self.page.wait_for_url("**/dashboard.xhtml",timeout=60000)
        self.log("Logged in to iDocs")
    def process(self,rsa_id,ref):
        try:
            self.log(f"{ref}: searching iDocs")
            self.page.get_by_role("button",name="Consumers").click()
            search=self.page.get_by_placeholder("Search")
            search.fill(rsa_id)
            self.page.get_by_role("button",name="Search").click()
            self.page.wait_for_timeout(1200)
            row=self.page.locator("table tbody tr").filter(has_text=rsa_id[-4:]).first
            if not row.count(): return {"ProcessStatus":"Consumer Not Found","RobotStatus":"Needs Review","FailureReason":"RSA ID not found"}
            applicant=self._status(row.inner_text())
            if applicant and applicant not in self.s.get("accepted_statuses",[]):
                return {"ProcessStatus":"Status Not Accepted","IDocsApplicantStatus":applicant,"RobotStatus":"Needs Review"}
            link=row.get_by_title("View this record")
            (link if link.count() else row.locator("a").last).click()
            self.page.get_by_text("Credit Checks",exact=True).scroll_into_view_if_needed()
            credit=self.page.locator("table tbody tr").filter(has_text="Completed").first
            if not credit.count(): return {"ProcessStatus":"Needs Review","CreditCheckStatus":"Not Found","RobotStatus":"Needs Review","FailureReason":"Completed credit check not found"}
            credit.locator("a").last.click()
            self.page.get_by_text("Attachments",exact=True).scroll_into_view_if_needed()
            xml=self.page.locator("a").filter(has_text=".xml").first
            pdf=self.page.locator("a").filter(has_text=".pdf").first
            target=xml if xml.count() else pdf
            if not target.count(): return {"ProcessStatus":"Needs Review","CreditCheckStatus":"Completed","AttachmentFound":False,"RobotStatus":"Needs Review","FailureReason":"No XML or PDF found"}
            href=target.get_attribute("href")
            if not href:
                return {"ProcessStatus":"Needs Review","CreditCheckStatus":"Completed","AttachmentFound":True,"RobotStatus":"Needs Review","FailureReason":"Attachment link has no readable URL"}
            response=self.context.request.get(href)
            if not response.ok:
                raise RuntimeError(f"Credit report request failed ({response.status})")
            report_path=self.reports/f"iThynk-calibration-{ref}-{datetime.now():%Y%m%d-%H%M%S}.xlsx"
            _,verification=extract_to_workbook(response.body(),report_path,rsa_id,Path(href).name or "iDocs preview")
            status="Completed" if verification=="Verified" else "Needs Review"
            self.log(f"{ref}: Excel calibration report created: {report_path}")
            return {"ProcessStatus":"Calibration Complete" if status=="Completed" else "Manual Review","IDocsApplicantStatus":applicant or "Unknown","CreditCheckStatus":"Completed","AttachmentFound":True,"RobotStatus":status,"FailureReason":"" if status=="Completed" else f"Document ID check: {verification}","CalibrationReport":str(report_path)}
        except Exception as exc:
            self.capture(ref)
            return {"ProcessStatus":"Failed","RobotStatus":"Failed","FailureReason":str(exc)[:250]}
    def capture(self,ref):
        stamp=datetime.now().strftime("%Y%m%d-%H%M%S")
        self.page.screenshot(path=str(self.diag/f"{ref}-{stamp}.png"),full_page=True)
        (self.diag/f"{ref}-{stamp}.html").write_text(self.page.content(),"utf-8")

    def calibration(self,rsa_id):
        digits=re.sub(r"\D","",rsa_id)
        if len(digits)!=13:
            raise ValueError("Enter a valid 13-digit South African ID number")
        return self.process(digits,f"TEST-{digits[-4:]}")
    @staticmethod
    def _status(text):
        for status in ("Created Applicant","Budgets Generated","Signed","Form16 Sent"):
            if status in text: return status
        return ""
