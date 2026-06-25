# Use Python 3.11 slim base image
FROM python:3.11-slim

# Install system dependencies (build-essential for GCC/G++, and OpenJDK for Java compilation)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    default-jdk \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory
WORKDIR /app

# Copy application files
COPY server.py minilang.py index.html index.css index.js ./

# Expose port (Render will configure PORT dynamically, but default is 8000)
EXPOSE 8000

# Start server
CMD ["python", "server.py"]
