from pathlib import Path
import msal, requests
GRAPH="https://graph.microsoft.com/v1.0"
SCOPES=["Sites.ReadWrite.All","offline_access"]
class SharePointQueue:
    def __init__(self,settings,log):
        self.s,self.log=settings,log
        self.session=requests.Session()
    def connect(self):
        cache=msal.SerializableTokenCache()
        cache_path=Path.home()/"AppData"/"Local"/"iThynk"/"msal-cache.json"
        if cache_path.exists(): cache.deserialize(cache_path.read_text("utf-8"))
        app=msal.PublicClientApplication(self.s["client_id"],authority=f"https://login.microsoftonline.com/{self.s['tenant_id']}",token_cache=cache)
        accounts=app.get_accounts()
        result=app.acquire_token_silent(SCOPES,account=accounts[0]) if accounts else None
        if not result:
            flow=app.initiate_device_flow(scopes=SCOPES)
            if "user_code" not in flow: raise RuntimeError(f"Microsoft sign-in could not start: {flow}")
            self.log(f"Open {flow['verification_uri']} and enter Microsoft code {flow['user_code']}")
            result=app.acquire_token_by_device_flow(flow)
        if "access_token" not in result: raise RuntimeError(result.get("error_description","Microsoft sign-in failed"))
        if cache.has_state_changed:
            cache_path.parent.mkdir(parents=True,exist_ok=True)
            cache_path.write_text(cache.serialize(),"utf-8")
        self.session.headers["Authorization"]=f"Bearer {result['access_token']}"
        host,path=self.s["sharepoint_hostname"],self.s["sharepoint_site_path"]
        self.site_id=self._get(f"{GRAPH}/sites/{host}:{path}")["id"]
        lists=self._get(f"{GRAPH}/sites/{self.site_id}/lists?$select=id,displayName")["value"]
        match=next((x for x in lists if x["displayName"].casefold()==self.s["sharepoint_list_name"].casefold()),None)
        if not match: raise RuntimeError("SharePoint list not found")
        self.list_id=match["id"]
        self.log("Connected to SharePoint queue")
    def waiting(self):
        rows=self._get(f"{GRAPH}/sites/{self.site_id}/lists/{self.list_id}/items?expand=fields&$top=25")["value"]
        return [r for r in rows if str(r["fields"].get("RobotStatus","")).casefold()=="waiting" or str(r["fields"].get("ProcessStatus","")).casefold()=="submitted"]
    def update(self,item_id,fields):
        url=f"{GRAPH}/sites/{self.site_id}/lists/{self.list_id}/items/{item_id}/fields"
        response=self.session.patch(url,json=fields,timeout=30)
        if not response.ok: raise RuntimeError(f"SharePoint update failed ({response.status_code}): {response.text[:250]}")
    def _get(self,url):
        response=self.session.get(url,timeout=30)
        if not response.ok: raise RuntimeError(f"Graph request failed ({response.status_code}): {response.text[:250]}")
        return response.json()
