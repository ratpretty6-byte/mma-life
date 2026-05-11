FROM python:3.12-slim

WORKDIR /app

# Copy virtual environment and game files
COPY venv/ venv/
COPY *.py ./
COPY templates/ templates/

# Install dependencies from virtual environment
RUN venv/bin/pip install --no-cache-dir -r venv/lib/python3.12/site-packages/pytest*.txt 2>/dev/null || true

# Expose port 8080
EXPOSE 8000

# Run the server
CMD ["venv/bin/python", "web_server.py"]