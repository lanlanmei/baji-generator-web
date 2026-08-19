$ErrorActionPreference = 'Stop'
$python = Get-Command python -ErrorAction Stop
& $python.Source -m pip install -r requirements.txt
& $python.Source -m uvicorn app.main:app --host 127.0.0.1 --port 8000
