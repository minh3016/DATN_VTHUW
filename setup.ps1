# ============================================================
# setup.ps1 – Cài đặt môi trường cho Vehicle Classification AI
# Chạy 1 lần duy nhất sau khi clone repo từ GitHub
# Usage: .\setup.ps1
# ============================================================

param(
    [switch]$SkipMongoDB,
    [switch]$SkipModel,
    [switch]$Help
)

if ($Help) {
    Write-Host ""
    Write-Host "Usage: .\setup.ps1 [options]"
    Write-Host ""
    Write-Host "Options:"
    Write-Host "  -SkipMongoDB    Bo qua kiem tra MongoDB"
    Write-Host "  -SkipModel      Bo qua kiem tra file model AI"
    Write-Host "  -Help           Hien thi huong dan"
    Write-Host ""
    exit 0
}

# ── Biến cấu hình ─────────────────────────────────────────────
$ProjectRoot = $PSScriptRoot
$BackendDir  = Join-Path $ProjectRoot "backend"
$FrontendDir = Join-Path $ProjectRoot "frontend"
$ModelsDir   = Join-Path $ProjectRoot "models"

$StepTotal   = 6
$StepCurrent = 0
$Errors      = @()
$Warnings    = @()

# ── Hàm tiện ích ──────────────────────────────────────────────

function Write-Step {
    param([string]$Message)
    $script:StepCurrent++
    Write-Host ""
    Write-Host "[$script:StepCurrent/$StepTotal] $Message" -ForegroundColor Cyan
    Write-Host ("-" * 50) -ForegroundColor DarkGray
}

function Write-OK {
    param([string]$Message)
    Write-Host "  [OK] $Message" -ForegroundColor Green
}

function Write-Warn {
    param([string]$Message)
    Write-Host "  [!] $Message" -ForegroundColor Yellow
    $script:Warnings += $Message
}

function Write-Err {
    param([string]$Message)
    Write-Host "  [X] $Message" -ForegroundColor Red
    $script:Errors += $Message
}

function Write-Info {
    param([string]$Message)
    Write-Host "  $Message" -ForegroundColor White
}

function Test-Command {
    param([string]$Command)
    return [bool](Get-Command $Command -ErrorAction SilentlyContinue)
}

# ── Banner ────────────────────────────────────────────────────

Clear-Host
Write-Host ""
Write-Host "  ╔══════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "  ║   Vehicle Classification AI - Setup Script   ║" -ForegroundColor Cyan
Write-Host "  ║   Cai dat moi truong lan dau sau khi clone   ║" -ForegroundColor Cyan
Write-Host "  ╚══════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Thu muc du an: $ProjectRoot" -ForegroundColor DarkGray
Write-Host ""

# ============================================================
# BƯỚC 1: Kiểm tra phần mềm cần thiết
# ============================================================

Write-Step "Kiem tra phan mem can thiet"

# Python
if (Test-Command "python") {
    $pyVersion = python --version 2>&1
    Write-OK "Python: $pyVersion"

    # Kiểm tra phiên bản >= 3.10
    $pyVer = python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>&1
    if ([double]$pyVer -lt 3.10) {
        Write-Warn "Python $pyVer < 3.10. Khuyen nghi dung Python 3.10 hoac 3.11"
    }
} else {
    Write-Err "Python chua duoc cai dat!"
    Write-Info "Tai tai: https://www.python.org/downloads/"
    Write-Info "Luu y: Tick chon 'Add Python to PATH' khi cai dat"
}

# Node.js
if (Test-Command "node") {
    $nodeVersion = node --version 2>&1
    Write-OK "Node.js: $nodeVersion"

    $nodeMajor = ($nodeVersion -replace 'v','').Split('.')[0]
    if ([int]$nodeMajor -lt 18) {
        Write-Warn "Node.js $nodeVersion < 18. Khuyen nghi dung Node.js 18 LTS tro len"
    }
} else {
    Write-Err "Node.js chua duoc cai dat!"
    Write-Info "Tai tai: https://nodejs.org/"
}

# npm
if (Test-Command "npm") {
    $npmVersion = npm --version 2>&1
    Write-OK "npm: v$npmVersion"
} else {
    Write-Err "npm chua duoc cai dat (thuong di kem Node.js)"
}

# Git
if (Test-Command "git") {
    $gitVersion = git --version 2>&1
    Write-OK "Git: $gitVersion"
} else {
    Write-Warn "Git chua duoc cai dat (khong bat buoc neu da clone xong)"
}

# Dừng nếu thiếu Python hoặc Node.js
if (-not (Test-Command "python") -or -not (Test-Command "node")) {
    Write-Host ""
    Write-Host "  Thieu phan mem bat buoc. Vui long cai dat truoc khi chay lai." -ForegroundColor Red
    Write-Host ""
    exit 1
}

# ============================================================
# BƯỚC 2: Kiểm tra MongoDB
# ============================================================

Write-Step "Kiem tra MongoDB"

if ($SkipMongoDB) {
    Write-Info "Bo qua (flag -SkipMongoDB)"
} else {
    $mongoFound = $false

    # Kiểm tra MongoDB service (cài local)
    $svc = Get-Service -Name "MongoDB" -ErrorAction SilentlyContinue
    if ($svc) {
        $mongoFound = $true
        if ($svc.Status -eq "Running") {
            Write-OK "MongoDB service dang chay"
        } else {
            Write-Info "MongoDB service da cai nhung chua chay."
            Write-Info "Dang khoi dong..."
            try {
                net start MongoDB 2>&1 | Out-Null
                Start-Sleep -Seconds 3
                $svc = Get-Service -Name "MongoDB" -ErrorAction SilentlyContinue
                if ($svc.Status -eq "Running") {
                    Write-OK "MongoDB service da khoi dong thanh cong"
                } else {
                    Write-Warn "Khong the khoi dong MongoDB service. Thu chay voi quyen Admin."
                }
            } catch {
                Write-Warn "Khong the khoi dong MongoDB. Thu chay PowerShell voi quyen Admin."
            }
        }
    }

    # Kiểm tra Docker
    if (-not $mongoFound -and (Test-Command "docker")) {
        $dockerMongo = docker ps --filter "name=traffic_mongo" --format "{{.Names}}" 2>&1
        if ($dockerMongo -match "traffic_mongo") {
            $mongoFound = $true
            Write-OK "MongoDB dang chay trong Docker (traffic_mongo)"
        } else {
            # Thử khởi động bằng docker-compose
            $composeFile = Join-Path $ProjectRoot "docker-compose.yml"
            if (Test-Path $composeFile) {
                Write-Info "Tim thay docker-compose.yml. Dang khoi dong MongoDB container..."
                Push-Location $ProjectRoot
                docker-compose up -d mongo 2>&1 | Out-Null
                Start-Sleep -Seconds 5
                Pop-Location

                $dockerMongo = docker ps --filter "name=traffic_mongo" --format "{{.Names}}" 2>&1
                if ($dockerMongo -match "traffic_mongo") {
                    $mongoFound = $true
                    Write-OK "MongoDB Docker container da khoi dong"
                } else {
                    Write-Warn "Khong the khoi dong MongoDB container"
                }
            }
        }
    }

    if (-not $mongoFound) {
        Write-Warn "MongoDB chua duoc cai dat hoac chua chay!"
        Write-Info ""
        Write-Info "Cach 1 (Docker - khuyen nghi):"
        Write-Info "  docker-compose up -d mongo"
        Write-Info ""
        Write-Info "Cach 2 (Cai truc tiep):"
        Write-Info "  Tai tai: https://www.mongodb.com/try/download/community"
        Write-Info "  Hoac:    winget install MongoDB.Server"
    }
}

# ============================================================
# BƯỚC 3: Cài đặt Backend Python
# ============================================================

Write-Step "Cai dat Backend (Python)"

$venvPath    = Join-Path $BackendDir ".venv"
$venvPython  = Join-Path $venvPath "Scripts\python.exe"
$venvPip     = Join-Path $venvPath "Scripts\pip.exe"
$reqFile     = Join-Path $BackendDir "requirements.txt"

# Tạo virtual environment
if (Test-Path $venvPython) {
    Write-OK "Virtual environment da ton tai (.venv)"
} else {
    Write-Info "Dang tao virtual environment..."
    Push-Location $BackendDir
    python -m venv .venv 2>&1
    Pop-Location

    if (Test-Path $venvPython) {
        Write-OK "Tao .venv thanh cong"
    } else {
        Write-Err "Khong the tao virtual environment!"
        Write-Info "Thu chay thu cong: cd backend && python -m venv .venv"
    }
}

# Cài đặt dependencies
if (Test-Path $venvPip) {
    Write-Info "Dang cai dat thu vien Python (co the mat 5-15 phut)..."
    Write-Host ""

    # Upgrade pip trước
    & $venvPython -m pip install --upgrade pip 2>&1 | Out-Null

    # Cài requirements
    & $venvPip install -r $reqFile 2>&1 | ForEach-Object {
        if ($_ -match "^Successfully installed") {
            Write-OK $_
        } elseif ($_ -match "^(ERROR|Could not)") {
            Write-Err $_
        } elseif ($_ -match "already satisfied") {
            # Bỏ qua, giảm noise
        }
    }

    # Kiểm tra các package chính đã cài thành công
    $checkPackages = @("fastapi", "uvicorn", "torch", "cv2", "ultralytics", "motor")
    $allOK = $true
    foreach ($pkg in $checkPackages) {
        $result = & $venvPython -c "import $pkg" 2>&1
        if ($LASTEXITCODE -ne 0) {
            Write-Err "Package '$pkg' chua cai duoc!"
            $allOK = $false
        }
    }

    if ($allOK) {
        Write-OK "Tat ca thu vien Python da cai dat thanh cong"
    } else {
        Write-Warn "Mot so package chua cai duoc. Thu:"
        Write-Info "  cd backend"
        Write-Info "  .venv\Scripts\activate"
        Write-Info "  pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu"
        Write-Info "  pip install -r requirements.txt"
    }
} else {
    Write-Err "Khong tim thay pip trong .venv!"
}

# ============================================================
# BƯỚC 4: Cài đặt Frontend (Node.js)
# ============================================================

Write-Step "Cai dat Frontend (Vue.js + Vite)"

$nodeModules = Join-Path $FrontendDir "node_modules"

if (Test-Path $nodeModules) {
    $pkgCount = (Get-ChildItem $nodeModules -Directory).Count
    Write-OK "node_modules da ton tai ($pkgCount packages)"
    Write-Info "Dang kiem tra cap nhat..."
}

Write-Info "Dang chay npm install..."
Push-Location $FrontendDir
$npmOutput = npm install 2>&1
Pop-Location

if ($LASTEXITCODE -eq 0) {
    Write-OK "npm install thanh cong"
} else {
    Write-Err "npm install that bai!"
    Write-Info "Thu chay thu cong: cd frontend && npm install"
}

# ============================================================
# BƯỚC 5: Tạo file .env
# ============================================================

Write-Step "Tao file cau hinh .env"

# Backend .env
$backendEnv        = Join-Path $BackendDir ".env"
$backendEnvExample = Join-Path $BackendDir ".env.example"

if (Test-Path $backendEnv) {
    Write-OK "backend\.env da ton tai (giu nguyen)"
} elseif (Test-Path $backendEnvExample) {
    Copy-Item $backendEnvExample $backendEnv
    Write-OK "Tao backend\.env tu .env.example"
} else {
    # Tạo .env mặc định
    @"
# ── MongoDB ────────────────────────────────────────────────────
MONGO_URI=mongodb://localhost:27017
MONGO_DB=vehicle_classification

# ── Model Path ─────────────────────────────────────────────────
VEHICLE_MODEL_PATH=../models/vehicle_detection.pt

# ── Confidence Threshold ──────────────────────────────────────
VEHICLE_CONF=0.45

# ── Frame Processing ───────────────────────────────────────────
FRAME_WIDTH=1280
FRAME_HEIGHT=720
PROCESS_FPS=3

# ── CORS ───────────────────────────────────────────────────────
CORS_ORIGINS=http://localhost:5173,http://localhost:3000

# ── WebSocket ──────────────────────────────────────────────────
WS_HEARTBEAT_INTERVAL=30
"@ | Out-File -FilePath $backendEnv -Encoding UTF8
    Write-OK "Tao backend\.env voi cau hinh mac dinh"
}

# Frontend .env
$frontendEnv        = Join-Path $FrontendDir ".env"
$frontendEnvExample = Join-Path $FrontendDir ".env.example"

if (Test-Path $frontendEnv) {
    Write-OK "frontend\.env da ton tai (giu nguyen)"
} elseif (Test-Path $frontendEnvExample) {
    Copy-Item $frontendEnvExample $frontendEnv
    Write-OK "Tao frontend\.env tu .env.example"
} else {
    @"
VITE_API_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000
VITE_APP_TITLE=Traffic Monitoring AI
"@ | Out-File -FilePath $frontendEnv -Encoding UTF8
    Write-OK "Tao frontend\.env voi cau hinh mac dinh"
}

# ============================================================
# BƯỚC 6: Kiểm tra file Model AI
# ============================================================

Write-Step "Kiem tra file Model AI"

if ($SkipModel) {
    Write-Info "Bo qua (flag -SkipModel)"
} else {
    # Tạo thư mục models nếu chưa có
    if (-not (Test-Path $ModelsDir)) {
        New-Item -ItemType Directory -Path $ModelsDir -Force | Out-Null
        Write-Info "Tao thu muc models/"
    }

    $modelFile = Join-Path $ModelsDir "vehicle_detection.pt"
    if (Test-Path $modelFile) {
        $modelSize = [math]::Round((Get-Item $modelFile).Length / 1MB, 1)
        Write-OK "vehicle_detection.pt da co ($modelSize MB)"
    } else {
        Write-Warn "Chua co file models/vehicle_detection.pt"
        Write-Info ""
        Write-Info "File model AI (~285MB) khong duoc luu tren GitHub."
        Write-Info "Ban can lay file nay bang 1 trong cac cach sau:"
        Write-Info ""
        Write-Info "  1. Copy tu may cu:   Copy file vao thu muc models/"
        Write-Info "  2. Google Drive:     Tai tu link cua nhom"
        Write-Info "  3. Pretrained:       He thong se tu tai YOLOv8n khi khoi dong"
        Write-Info "                       (do chinh xac thap hon model custom)"
    }

    # Tạo thư mục evidence và uploads
    $evidenceDir = Join-Path $BackendDir "evidence"
    $uploadsDir  = Join-Path $BackendDir "uploads"

    if (-not (Test-Path $evidenceDir)) {
        New-Item -ItemType Directory -Path $evidenceDir -Force | Out-Null
    }
    if (-not (Test-Path $uploadsDir)) {
        New-Item -ItemType Directory -Path $uploadsDir -Force | Out-Null
    }
    Write-OK "Thu muc evidence/ va uploads/ da san sang"
}

# ============================================================
# KẾT QUẢ
# ============================================================

Write-Host ""
Write-Host "  ╔══════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "  ║            KET QUA CAI DAT                   ║" -ForegroundColor Cyan
Write-Host "  ╚══════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# Tổng kết
$successItems = @(
    @{ Name = "Python venv";  OK = (Test-Path $venvPython) },
    @{ Name = "Pip packages"; OK = (Test-Path $venvPip) },
    @{ Name = "node_modules"; OK = (Test-Path $nodeModules) },
    @{ Name = "backend .env"; OK = (Test-Path $backendEnv) },
    @{ Name = "frontend .env"; OK = (Test-Path $frontendEnv) }
)

foreach ($item in $successItems) {
    if ($item.OK) {
        Write-Host "  [✓] $($item.Name)" -ForegroundColor Green
    } else {
        Write-Host "  [✗] $($item.Name)" -ForegroundColor Red
    }
}

# Warnings
if ($Warnings.Count -gt 0) {
    Write-Host ""
    Write-Host "  Canh bao ($($Warnings.Count)):" -ForegroundColor Yellow
    foreach ($w in $Warnings) {
        Write-Host "    ! $w" -ForegroundColor Yellow
    }
}

# Errors
if ($Errors.Count -gt 0) {
    Write-Host ""
    Write-Host "  Loi ($($Errors.Count)):" -ForegroundColor Red
    foreach ($e in $Errors) {
        Write-Host "    X $e" -ForegroundColor Red
    }
}

# Hướng dẫn tiếp theo
Write-Host ""
Write-Host ("-" * 50) -ForegroundColor DarkGray

if ($Errors.Count -eq 0) {
    Write-Host ""
    Write-Host "  Cai dat hoan tat! Buoc tiep theo:" -ForegroundColor Green
    Write-Host ""
    Write-Host "  1. Dam bao MongoDB dang chay" -ForegroundColor White
    Write-Host "  2. Chay he thong:" -ForegroundColor White
    Write-Host "       .\start_all.ps1" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  Hoac chay thu cong:" -ForegroundColor White
    Write-Host "    Terminal 1:  cd backend && .venv\Scripts\activate && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload" -ForegroundColor DarkGray
    Write-Host "    Terminal 2:  cd frontend && npm run dev" -ForegroundColor DarkGray
    Write-Host ""
    Write-Host "  Truy cap:" -ForegroundColor White
    Write-Host "    Dashboard : http://localhost:5173" -ForegroundColor Yellow
    Write-Host "    API Docs  : http://localhost:8000/docs" -ForegroundColor Yellow
} else {
    Write-Host ""
    Write-Host "  Co loi xay ra. Vui long xu ly cac loi phia tren roi chay lai:" -ForegroundColor Red
    Write-Host "       .\setup.ps1" -ForegroundColor Yellow
}

Write-Host ""
