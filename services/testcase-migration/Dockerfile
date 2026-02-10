# Build stage
FROM python:3.12-alpine AS builder

WORKDIR /app

RUN apk add --no-cache gcc musl-dev libffi-dev

COPY services/testcase-migration/requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Runtime stage
FROM python:3.12-alpine

WORKDIR /app

COPY --from=builder /root/.local /root/.local

COPY shared /app/shared
COPY services/testcase-migration/main.py /app/main.py

ENV PATH=/root/.local/bin:$PATH

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
