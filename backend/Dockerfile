# Build from the repository root so the MCP server package (used by the agent) is available:
#   docker build -f backend/Dockerfile -t unicompass-backend .
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

# requirements.txt installs ../mcp-server in editable mode, so keep the same layout.
COPY mcp-server /app/mcp-server
COPY backend/requirements.txt /app/backend/requirements.txt
WORKDIR /app/backend
RUN pip install -r requirements.txt

COPY backend /app/backend
RUN useradd --create-home app && mkdir -p /app/backend/.cache && chown -R app /app/backend
USER app

EXPOSE 8000
# The API serves requests only; workers run in the separate `worker` service.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
