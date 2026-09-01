@echo off
py -3.12 -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
playwright install chromium
pyinstaller --noconfirm --clean --windowed --name iThynk-v1.1-calibration --collect-all customtkinter --collect-all keyring main.py
echo Build complete in dist\iThynk-v1.1-calibration
pause
