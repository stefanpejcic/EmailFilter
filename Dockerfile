FROM python:3.11-slim

LABEL maintainer="Stefan Pejcic <stefan@pejcice.rs>"
LABEL org.opencontainers.image.title="emailfilter API"
LABEL org.opencontainers.image.description="Self-hosted and privacy-focused email verification API."
LABEL org.opencontainers.image.version="1.0.0"
LABEL org.opencontainers.image.authors="Stefan Pejcic <stefan@pejcice.rs>"

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
