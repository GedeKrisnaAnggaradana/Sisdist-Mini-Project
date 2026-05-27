# Dockerfile untuk Ticket Service
# Menggunakan Python 3.11 slim sebagai base image
FROM python:3.11-slim

# Set working directory di dalam container
WORKDIR /app

# Copy file requirements terlebih dahulu untuk memanfaatkan
# Docker layer caching (requirements jarang berubah)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy semua source code ke dalam container
COPY . .

# Jalankan ticket_service.py saat container dimulai
CMD ["python", "ticket_service.py"]
