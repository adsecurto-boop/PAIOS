# PAIOS relay — a tiny, dependency-free reverse-tunnel broker.
# Stdlib only, so the base image needs nothing but Python.
FROM python:3.12-slim

WORKDIR /app
COPY paios_relay ./paios_relay

# Config is entirely environment variables (see docker-compose.yml).
EXPOSE 8770

# Unbuffered so `docker logs` shows the startup line immediately.
ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "paios_relay"]
