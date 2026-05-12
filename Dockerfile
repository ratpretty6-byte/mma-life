FROM python:3.12-slim

WORKDIR /app

# Copy all game files
COPY . .

# Install Python and clean up
RUN apt-get update && apt-get install -y python3 python3-pip && rm -rf /var/lib/apt/lists/*

# Expose port
ENV PORT=8000
EXPOSE 8000

# Run the server
CMD ["python3", "web_server.py"]