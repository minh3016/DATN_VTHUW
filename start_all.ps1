# start_all.ps1 - Vehicle Classification AI v3.0 (YOLOv7 + ESP32 MJPEG)
# Khởi động: MongoDB + Backend FastAPI + Frontend Vue 3
# Chạy: .\start_all.ps1

$ProjectRoot = $PSScriptRoot
$BackendDir  = Join-Path $ProjectRoot "backend"
$FrontendDir = Join-Path $ProjectRoot "frontend"

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  Vehicle Classification AI v3.0 - YOLOv7  " -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# ── 1. MongoDB ─────────────────────────────────────────────────
Write-Host "[1/3] Kiem tra MongoDB..." -ForegroundColor Yellow

try {
    $svc = Get-Service -Name "MongoDB" -ErrorAction Stop
    if ($svc.Status -eq "Running") {
        Write-Host "  MongoDB service dang chay" -ForegroundColor Green
    } else {
        Write-Host "  Dang khoi dong MongoDB service..." -ForegroundColor Yellow
        net start MongoDB 2>&1 | Out-Null
        Start-Sleep -Seconds 2
        Write-Host "  MongoDB da khoi dong" -ForegroundColor Green
    }
} catch {
    Write-Host "  [CANH BAO] Khong tim thay MongoDB service." -ForegroundColor Red
    Write-Host "  Cai dat: winget install MongoDB.Server" -ForegroundColor Yellow
}

# ── 2. Backend ─────────────────────────────────────────────────
Write-Host ""
Write-Host "[2/3] Khoi dong Backend FastAPI (port 8000)..." -ForegroundColor Yellow

$venvPython = Join-Path $BackendDir ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Host "  [LOI] Chua co .venv! Chay:" -ForegroundColor Red
    Write-Host "    cd backend" -ForegroundColor White
    Write-Host "    python -m venv .venv" -ForegroundColor White
    Write-Host "    .venv\Scripts\pip install -r requirements.txt" -ForegroundColor White
    exit 1
}

Start-Process -FilePath "powershell" -ArgumentList @(
    "-NoExit", "-Command",
    "Set-Location '$BackendDir'; Write-Host '[Backend]' -ForegroundColor Cyan; & '$venvPython' -m uvicorn app.main:app --host 0.0.0.0 --port 8000"
) -WindowStyle Normal

Write-Host "  Backend terminal da mo" -ForegroundColor Green

# ── 3. Frontend ────────────────────────────────────────────────
Write-Host ""
Write-Host "[3/3] Khoi dong Frontend Vue 3 (port 5173)..." -ForegroundColor Yellow

if (-not (Test-Path (Join-Path $FrontendDir "node_modules"))) {
    Write-Host "  Cai node_modules..." -ForegroundColor Yellow
    Push-Location $FrontendDir
    npm install
    Pop-Location
}

Start-Process -FilePath "powershell" -ArgumentList @(
    "-NoExit", "-Command",
    "Set-Location '$FrontendDir'; Write-Host '[Frontend]' -ForegroundColor Magenta; npm run dev"
) -WindowStyle Normal

Write-Host "  Frontend terminal da mo" -ForegroundColor Green

# ── Summary ───────────────────────────────────────────────────
Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  Doi ~30 giay (YOLOv7 load) roi truy cap:" -ForegroundColor Green
Write-Host ""
Write-Host "  Dashboard  : http://localhost:5173" -ForegroundColor White
Write-Host "  API Docs   : http://localhost:8000/docs" -ForegroundColor White
Write-Host "  Health     : http://localhost:8000/" -ForegroundColor White
Write-Host ""
Write-Host "  Model: vehicle_detection.pt (YOLOv7)" -ForegroundColor Yellow
Write-Host "  Classes: car, motorcycle, truck, bus" -ForegroundColor Yellow
Write-Host "  ESP32 stream: http://<ESP32_IP>/stream" -ForegroundColor Yellow
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

Start-Sleep -Seconds 15
Start-Process "http://localhost:5173"
