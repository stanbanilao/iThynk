# iThynk v1.1 — iDocs Excel Calibration

This is the safe first development build for validating what iThynk can read from an authorised iDocs credit-report preview. It does **not** write extracted credit data to SharePoint yet.

## What this build does

1. Opens iDocs in a dedicated Playwright Chromium profile.
2. Reuses the authorised iDocs session after the first successful login.
3. Searches one authorised 13-digit RSA ID.
4. Opens the exact matching consumer and first completed credit report.
5. Reads the report in memory through the authorised browser session.
6. Creates an Excel workbook in `%LOCALAPPDATA%\iThynk\calibration-reports`.
7. Does not retain a PDF copy.

The workbook contains:

- **Extracted Data** — field, value, matched label, source page, confidence and review flag.
- **Source Text** — text available from each PDF page for controlled comparison.
- **Field Mapping** — labels searched and an empty SharePoint destination column for approval.

Initial candidate fields are Consumer Name, Consumer Surname, ID Number, Contact Number, Employer, Status, Status Date and iDocs Reference. Missing fields are clearly marked; the bot does not guess.

## Build on Windows

1. Install Python 3.12.
2. Download or clone this repository.
3. Double-click `build_windows.bat`.
4. Open `dist\iThynk-v1.1-calibration\iThynk-v1.1-calibration.exe`.
5. Enter the authorised iDocs login inside the app. It is stored with Windows Credential Manager.
6. Enter one approved test ID under **Calibration ID**.
7. Select **Test iDocs → Excel**.
8. Select **Open Excel Reports** and review the result.

## Important first-test limitation

iDocs element names and the credit-report attachment behaviour must be confirmed against the live authorised site. If the first run cannot locate a control, iThynk saves a diagnostic screenshot and HTML under `%LOCALAPPDATA%\iThynk\diagnostics`. Do not publish those diagnostics because they may contain client information.

After the Excel fields are approved, the next release will map them into the existing `Sales Bot Capture` SharePoint item and enable the five-second queue monitor.
