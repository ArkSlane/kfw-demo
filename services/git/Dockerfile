# Build stage
FROM python:3.11-alpine AS builder

WORKDIR /app

# Install build dependencies
RUN apk add --no-cache gcc musl-dev libffi-dev

# Copy and install Python dependencies
COPY services/git/requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Runtime stage
FROM python:3.11-alpine

# Install git and openssh (for SSH key management) and curl for healthcheck
RUN apk add --no-cache git openssh-client curl

WORKDIR /app

# Create non-root user
RUN adduser -D appuser

# Copy Python dependencies from builder
COPY --from=builder /root/.local /home/appuser/.local

# Copy shared modules
COPY shared /app/shared

# Copy service code
COPY services/git/ .

# Create workspace and SSH dirs writable by appuser
RUN mkdir -p /workspace /ssh-keys && chown -R appuser:appuser /app /workspace /ssh-keys

# Make sure scripts in .local are usable
ENV PATH=/home/appuser/.local/bin:$PATH

USER appuser

# Expose port
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD curl -f http://localhost:8000/health || exit 1

# Run the service
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
