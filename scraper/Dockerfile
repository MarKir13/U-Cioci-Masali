# The scraper in a container, so the images can be downloaded from the source shop without installing Python.
# Used by the init command's fallback when the GitHub Release is unavailable (issue #71):
#   docker compose -f deploy/compose.yaml --profile init run --rm --build scraper images
# Any other command works too, for example `... run --rm --build scraper verify`.
FROM python:3.12.15-slim

# The same layout as the repository: config.py finds scraper-results/ next to the scraper folder, so Compose
# mounts it at /app/scraper-results
WORKDIR /app/scraper
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY scraper/ scraper/

# Runs as root, like the importer: it writes into bind-mounted folders, which Docker on Linux creates as root.
# On Linux the files it writes are root's; the next init gives them back to the owner of scraper-results/.
ENTRYPOINT ["python", "-m", "scraper"]
