import json
from pathlib import Path
import keyring
APP="iThynk"
def app_dir():
    path=Path.home()/"AppData"/"Local"/APP
    path.mkdir(parents=True,exist_ok=True)
    return path
def load_settings():
    path=app_dir()/"settings.json"
    return json.loads(path.read_text("utf-8")) if path.exists() else {}
def save_settings(data):
    (app_dir()/"settings.json").write_text(json.dumps(data,indent=2),"utf-8")
def save_idocs_credentials(email,password):
    keyring.set_password(APP,"idocs_email",email)
    keyring.set_password(APP,"idocs_password",password)
def get_idocs_credentials():
    return keyring.get_password(APP,"idocs_email"),keyring.get_password(APP,"idocs_password")
