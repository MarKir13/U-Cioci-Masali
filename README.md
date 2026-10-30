# U Cioci Masali

Reconstruction of the online shop [magiczne-indie.pl](https://www.magiczne-indie.pl/) on PrestaShop,
built as a team project for the *Biznes Elektroniczny* course at Gdansk University of Technology.

> Product data is scraped from the source shop for educational purposes only.
> This shop must not be publicly available on the internet.

## Tech stack

| Component | Version |
|---|---|
| PrestaShop | 8.2.8 (official image `prestashop/prestashop:8.2.8-8.1-apache`) |
| PHP | 8.1 (Apache) |
| Database | MariaDB 10.11.18 |
| Containers | Docker Engine + Docker Compose v2 |

Our own code (child theme `ciocia`, modules, PHP config) lives in `shop/` and is built on top of
the official image. PrestaShop itself is not stored in this repository.

## Running the shop

Requirements: [Docker Desktop](https://www.docker.com/products/docker-desktop/) (or Docker Engine with Compose v2) and Git.

1. Clone the repository and enter it:
   ```sh
   git clone <repo-url>
   cd U-Cioci-Masali
   ```
2. Create the local configuration from the template (works as-is for local use):
   ```sh
   cp deploy/.env.example deploy/.env
   ```
3. Build and start the containers:
   ```sh
   docker compose -f deploy/compose.yaml up -d --build
   ```
4. Wait for the first-time installation to finish (about 3–5 minutes). It is done when the log shows
   `Starting web server`:
   ```sh
   docker compose -f deploy/compose.yaml logs -f shop
   ```
5. Open the shop:
   - Storefront: http://localhost:8080
   - Admin panel: http://localhost:8080/admin-ciocia
     (login: `ADMIN_MAIL` / `ADMIN_PASSWORD` from `deploy/.env`)

### Everyday commands

| Task | Command |
|---|---|
| Stop the shop (data is kept) | `docker compose -f deploy/compose.yaml down` |
| Apply changes from `shop/` (theme, modules, config) | `docker compose -f deploy/compose.yaml up -d --build` |
| Reset everything and reinstall from scratch | `docker compose -f deploy/compose.yaml down -v` |

## Repository structure

| Path | Contents | Status |
|---|---|---|
| `shop/` | Dockerfile, PHP config, child theme, own modules | in progress |
| `deploy/` | `compose.yaml`, `.env.example`; later: init, backup and restore scripts | in progress |
| `docs/` | AI log, architecture decisions (ADR) | in progress |
| `scraper/` | Scraper source code and tests, see [scraper/README.md](scraper/README.md) | in progress |
| `scraper-results/` | Scraped data (JSON/CSV) and sample images | planned |
| `tests/` | Playwright E2E tests | planned |

## Team

* Marcel Kiraga 203224
* Jakub Bugnacki 203392
* Jakub Rachubka 203296
* Mateusz Radziul 203772
* Piotr Bortnowski 203438
