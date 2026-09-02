@echo off
setlocal
set PLAYWRIGHT_BROWSERS_PATH=0
py -3.12 -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
playwright install chromium
python -m compileall -q main.py ithynk tests
python -m unittest discover -s tests -v
if errorlevel 1 exit /b 1
pyinstaller --noconfirm --clean --windowed --name iThynk-v1.2-pdf-reader --collect-all customtkinter --collect-all keyring --collect-all playwright main.py
echo Build complete in dist\iThynk-v1.2-pdf-reader
pause
