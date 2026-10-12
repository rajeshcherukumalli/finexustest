FROM mcr.microsoft.com/playwright/python:v1.60.0-jammy

WORKDIR /app

# Node.js for running generated @playwright/test TypeScript specs
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates default-jre-headless \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/* \
    && npm install -g @anthropic-ai/claude-code

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV QA_DATA_ROOT=/data
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
