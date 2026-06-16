# Dockerfile cho Backend FastAPI
FROM python:3.11-slim

# Thiết lập thư mục làm việc
WORKDIR /app

# Cài dependencies hệ thống
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    tesseract-ocr \
    tesseract-ocr-vie \
    && rm -rf /var/lib/apt/lists/*

# Copy và cài Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir ultralytics

# Copy source code
COPY . .

# Tạo thư mục models nếu chưa có
RUN mkdir -p /models /samples

# Expose port
EXPOSE 8000

# Biến môi trường mặc định
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    MONGO_URI=mongodb://mongo:27017 \
    MONGO_DB=traffic_monitoring

# Khởi động server
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
