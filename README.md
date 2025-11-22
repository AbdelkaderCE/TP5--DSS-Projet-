# Veterinary Clinic Intake Form

A simple Flask web app to capture animal and owner details and append each submission as a new row to an Excel file (`animals.xlsx`) in the sheet named `Animals`.

## Features
- Modern, responsive form UI
- Required field checks (client + server)
- Appends to `animals.xlsx` (sheet `Animals`) with a timestamp

## Quickstart (Windows, PowerShell)

```powershell
# 1) (Optional) Create and activate a virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2) Install dependencies
pip install -r requirements.txt

# 3) Run the app
python app.py
# The server listens at http://127.0.0.1:5000/
```

Submissions will create/update `animals.xlsx` in this folder. Each new entry is appended as a new row in the `Animals` sheet.

## Environment
- Python 3.9+ recommended
- Packages: Flask, pandas, openpyxl

## Notes
- If `animals.xlsx` exists but is unreadable, the app will recreate it on next submission.
- To change the Excel path or sheet name, edit `EXCEL_FILENAME` and `SHEET_NAME` in `app.py`.