# stop_all.ps1
# Dừng tất cả services của Vehicle Classification AI

Write-Host ""
Write-Host "============================================" -ForegroundColor Red
Write-Host "   Vehicle Classification AI - Dung he thong" -ForegroundColor Red
Write-Host "============================================" -ForegroundColor Red
Write-Host ""

# Dừng Backend (tắt uvicorn)
Write-Host "Dang dung Backend..." -ForegroundColor Yellow
Get-Process -Name "python" -ErrorAction SilentlyContinue | Where-Object {
    $_.MainWindowTitle -match "uvicorn" -or $_.CommandLine -match "uvicorn"
} | Stop-Process -Force
# Fallback: kill tất cả python trên port 8000
$proc = netstat -ano | Select-String ":8000" | ForEach-Object {
    ($_ -split '\s+')[-1]
} | Select-Object -First 1
if ($proc -and $proc -match '^\d+$') {
    Stop-Process -Id $proc -Force -ErrorAction SilentlyContinue
    Write-Host "  Backend (PID $proc) da dung" -ForegroundColor Green
}

# Dừng Frontend (node/vite)
Write-Host "Dang dung Frontend..." -ForegroundColor Yellow
$proc5173 = netstat -ano | Select-String ":5173" | ForEach-Object {
    ($_ -split '\s+')[-1]
} | Select-Object -First 1
if ($proc5173 -and $proc5173 -match '^\d+$') {
    Stop-Process -Id $proc5173 -Force -ErrorAction SilentlyContinue
    Write-Host "  Frontend (PID $proc5173) da dung" -ForegroundColor Green
}

# Dừng MongoDB service
Write-Host "Dang dung MongoDB..." -ForegroundColor Yellow
$svc = Get-Service -Name "MongoDB" -ErrorAction SilentlyContinue
if ($svc -and $svc.Status -eq "Running") {
    net stop MongoDB 2>&1 | Out-Null
    Write-Host "  MongoDB service da dung" -ForegroundColor Green
} else {
    # Kill mongod process nếu chạy trực tiếp
    Get-Process -Name "mongod" -ErrorAction SilentlyContinue | Stop-Process -Force
    Write-Host "  mongod process da dung" -ForegroundColor Green
}

Write-Host ""
Write-Host "Tat ca service da dung." -ForegroundColor Cyan
Write-Host ""
