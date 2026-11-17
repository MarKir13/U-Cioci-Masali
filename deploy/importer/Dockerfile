# Product importer (issue #70): loads scraper-results/ into the shop through the Webservice API.
# Run through Compose: docker compose -f deploy/compose.yaml --profile init run --rm importer
FROM python:3.12.15-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY importer/ importer/
# Products with variants (issue #73). In the image, so that `run --build` picks up an edited file.
COPY variants.json .

# Runs as root on purpose: it writes its log to a bind-mounted folder (deploy/logs), which Docker on Linux
# creates as root, so another user could not write there. The container only lives for one import run,
# reads the data read-only and talks to the shop over HTTP.
ENTRYPOINT ["python", "-m", "importer"]
