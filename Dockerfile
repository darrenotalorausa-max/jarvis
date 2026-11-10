# Jarvis OS como servidor siempre encendido (opcional). El uso normal es local, con START_JARVIS.
FROM node:22-slim AS ui
WORKDIR /src/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY backend/requirements.lock backend/requirements.txt backend/
RUN pip install --no-cache-dir -r backend/requirements.lock
COPY backend/ backend/
COPY content/ content/
COPY --from=ui /src/frontend/dist frontend/dist
ENV JARVIS_HOME=/data JARVIS_SECRETS_BACKEND=file JARVIS_SECRETS_FILE=/secrets/secrets.json JARVIS_HOST=0.0.0.0 JARVIS_NO_BROWSER=1
VOLUME ["/data", "/secrets"]
EXPOSE 8765
WORKDIR /app/backend
CMD ["python", "-m", "jarvis.launch"]
