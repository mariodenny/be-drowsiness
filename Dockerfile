FROM python:3.10-slim

# Install system dependencies needed for OpenCV, MediaPipe, and other AI tools
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements file first to leverage Docker cache
COPY requirements.txt .

# Upgrade pip and install requirements
# We also pin mediapipe and numpy to specific stable versions to avoid known conflicts
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir mediapipe==0.10.14 numpy==1.24.3 scipy==1.10.1

# Remove conflicting jax/jaxlib if they were pulled, as they break deepface on some environments
RUN pip uninstall -y jax jaxlib || true

# Copy the rest of the application code
COPY . .

# Ensure uploads directory exists
RUN mkdir -p uploads

# Expose port
EXPOSE 7001

# Set encoding to avoid unicode errors when printing emojis
ENV PYTHONIOENCODING=utf-8

# Run the app
CMD ["python", "app.py"]
