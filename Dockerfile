FROM python:3.12-slim

WORKDIR /app

# Copy all game files
COPY . .

# No external dependencies - standard library only
RUN pip install --no-cache-dir -r requirements.txt || true

# Expose port (Railway will override with PORT env)
EXPOSE 8000

# Run the server - Railway sets PORT env var
CMD ["python", "web_server.py"]