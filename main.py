import os, queue, re, threading
from datetime import datetime, timezone
import customtkinter as ctk
from ithynk.store import load_settings,save_settings,save_idocs_credentials,get_idocs_credentials
from ithynk.sharepoint import SharePointQueue
from ithynk.idocs import IDocsRobot
ctk.set_appearance_mode("dark")
class App(ctk.CTk):
    def __init__(self):
        super().__init__(); self.title("iThynk v1.1 Calibration"); self.geometry("940x790"); self.minsize(900,720); self.configure(fg_color="#100f0e")
        self.events=queue.Queue(); self.stop_event=threading.Event(); self.settings=load_settings(); self._ui(); self.after(150,self._drain)
    def _ui(self):
        header=ctk.CTkFrame(self,fg_color="#191715",corner_radius=0); header.pack(fill="x")
        ctk.CTkLabel(header,text="iThynk",font=("Segoe UI",28,"bold"),text_color="#f47920").pack(side="left",padx=24,pady=18)
        ctk.CTkLabel(header,text="SharePoint to iDocs Automation",text_color="#aaa29a").pack(side="left")
        body=ctk.CTkFrame(self,fg_color="transparent"); body.pack(fill="both",expand=True,padx=20,pady=20)
        left=ctk.CTkFrame(body,fg_color="#191715"); left.pack(side="left",fill="y",padx=(0,12))
        right=ctk.CTkFrame(body,fg_color="#191715"); right.pack(side="left",fill="both",expand=True)
        ctk.CTkLabel(left,text="Connection Settings",font=("Segoe UI",16,"bold")).pack(anchor="w",padx=16,pady=(16,8))
        self.inputs={}; email,password=get_idocs_credentials()
        fields=[("Tenant ID","tenant_id"),("Entra Client ID","client_id"),("SharePoint Host","sharepoint_hostname"),("Site Path","sharepoint_site_path"),("List Name","sharepoint_list_name"),("iDocs URL","idocs_url"),("iDocs Email","idocs_email"),("iDocs Password","idocs_password")]
        for label,key in fields:
            ctk.CTkLabel(left,text=label,text_color="#aaa29a").pack(anchor="w",padx=16)
            entry=ctk.CTkEntry(left,width=315,show="*" if key=="idocs_password" else ""); entry.pack(padx=16,pady=(3,9))
            value=password if key=="idocs_password" and password else email if key=="idocs_email" and email else self.settings.get(key,"")
            entry.insert(0,value); self.inputs[key]=entry
        ctk.CTkLabel(left,text="Calibration ID",text_color="#aaa29a").pack(anchor="w",padx=16)
        self.calibration_id=ctk.CTkEntry(left,width=315,placeholder_text="13-digit authorised test ID"); self.calibration_id.pack(padx=16,pady=(3,9))
        self.calibrate_btn=ctk.CTkButton(left,text="Test iDocs → Excel",fg_color="#2f6f59",command=self.start_calibration); self.calibrate_btn.pack(fill="x",padx=16,pady=(3,7))
        self.open_reports_btn=ctk.CTkButton(left,text="Open Excel Reports",fg_color="#4a4642",command=self.open_reports); self.open_reports_btn.pack(fill="x",padx=16,pady=(0,7))
        self.start_btn=ctk.CTkButton(left,text="Start SharePoint Robot",fg_color="#f47920",command=self.start); self.start_btn.pack(fill="x",padx=16,pady=(0,7))
        self.stop_btn=ctk.CTkButton(left,text="Stop",fg_color="#7e302d",state="disabled",command=self.stop); self.stop_btn.pack(fill="x",padx=16,pady=(0,16))
        ctk.CTkLabel(right,text="Activity Log",font=("Segoe UI",16,"bold")).pack(anchor="w",padx=16,pady=(16,8))
        self.logbox=ctk.CTkTextbox(right,fg_color="#100f0e",text_color="#ddd5cd"); self.logbox.pack(fill="both",expand=True,padx=16,pady=(0,16))
        self.log("iThynk ready. Configure connections, then select Start Robot.")
    def log(self,msg): self.events.put(f"[{datetime.now():%H:%M:%S}] {msg}")
    def _drain(self):
        while not self.events.empty(): self.logbox.insert("end",self.events.get()+"\n"); self.logbox.see("end")
        self.after(150,self._drain)
    def start(self):
        data={k:v.get().strip() for k,v in self.inputs.items()}
        if not all(data.values()): self.log("Complete every connection setting first."); return
        save_idocs_credentials(data.pop("idocs_email"),data.pop("idocs_password"))
        data.update({"poll_seconds":5,"headless":False,"accepted_statuses":["Created Applicant","Budgets Generated","Signed","Form16 Sent"]})
        save_settings(data); self.settings=data; self.stop_event.clear(); self.start_btn.configure(state="disabled"); self.stop_btn.configure(state="normal")
        threading.Thread(target=self._run,daemon=True).start()
    def start_calibration(self):
        rsa_id=re.sub(r"\D","",self.calibration_id.get())
        if len(rsa_id)!=13:
            self.log("Calibration requires one authorised 13-digit RSA ID."); return
        email=self.inputs["idocs_email"].get().strip(); password=self.inputs["idocs_password"].get().strip()
        if not email or not password:
            self.log("Enter the authorised iDocs email and password first."); return
        save_idocs_credentials(email,password)
        settings=dict(self.settings)
        idocs_url=self.inputs["idocs_url"].get().strip()
        if not idocs_url:
            self.log("Enter the authorised iDocs login URL first."); self.calibrate_btn.configure(state="normal"); return
        settings.update({"idocs_url":idocs_url,"headless":False,"accepted_statuses":["Created Applicant","Budgets Generated","Signed","Form16 Sent"]})
        self.calibrate_btn.configure(state="disabled")
        threading.Thread(target=self._run_calibration,args=(settings,email,password,rsa_id),daemon=True).start()
    def _run_calibration(self,settings,email,password,rsa_id):
        robot=None
        try:
            self.log(f"Starting calibration for *********{rsa_id[-4:]}")
            robot=IDocsRobot(settings,email,password,self.log); robot.start()
            result=robot.calibration(rsa_id)
            self.log(f"Calibration result: {result.get('ProcessStatus')}")
            if result.get("CalibrationReport"):
                self.log("Open Excel Reports to review the extracted fields.")
        except Exception as exc:
            self.log(f"Calibration failed: {str(exc)[:300]}")
        finally:
            if robot: robot.stop()
            self.after(0,lambda:self.calibrate_btn.configure(state="normal"))
    def open_reports(self):
        path=os.path.join(os.path.expanduser("~"),"AppData","Local","iThynk","calibration-reports")
        os.makedirs(path,exist_ok=True)
        os.startfile(path)
    def stop(self): self.stop_event.set(); self.log("Stop requested; finishing the active record.")
    def _run(self):
        robot=None
        try:
            email,password=get_idocs_credentials(); sp=SharePointQueue(self.settings,self.log); sp.connect()
            robot=IDocsRobot(self.settings,email,password,self.log); robot.start(); self.log("Robot online; watching submitted records.")
            while not self.stop_event.is_set():
                for item in sp.waiting():
                    if self.stop_event.is_set(): break
                    fields=item["fields"]; ref=str(fields.get("SubmissionRef") or item["id"])
                    rsa=str(fields.get("RSAIDNumber") or fields.get("RSA_x0020_ID_x0020_Number") or "")
                    if not rsa: sp.update(item["id"],{"ProcessStatus":"Failed","RobotStatus":"Failed","FailureReason":"RSA ID missing"}); continue
                    sp.update(item["id"],{"ProcessStatus":"Checking iDocs","RobotStatus":"Running","RobotStartedAt":datetime.now(timezone.utc).isoformat()})
                    result=robot.process(rsa,ref); result["RobotCompletedAt"]=datetime.now(timezone.utc).isoformat(); sp.update(item["id"],result)
                    self.log(f"{ref}: {result.get('ProcessStatus')}")
                self.stop_event.wait(int(self.settings.get("poll_seconds",15)))
        except Exception as exc: self.log(f"Robot stopped with error: {str(exc)[:300]}")
        finally:
            if robot: robot.stop()
            self.after(0,lambda:(self.start_btn.configure(state="normal"),self.stop_btn.configure(state="disabled")))
if __name__=="__main__": App().mainloop()

