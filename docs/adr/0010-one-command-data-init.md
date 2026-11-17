# 0010. One-command data init

- Status: Proposed
- Date: 2026-11-17
- Authors: Marcel Kiraga

## Context

W3 [K] requires that a clean clone becomes a working shop with data after the README's steps: one start command and
one data init command. The lecturer measures the whole path from a clean clone to a shop with data, with a limit of
15 minutes. The pieces existed before this decision: `up -d --build` installs the shop, and the importer
([ADR 0008](0008-product-import-through-the-webservice-api.md)) loads `scraper-results/` through the API. Missing was
everything between them:

- The product images are not in git (rule 5). They are one archive of 585 MB (4822 files) in the GitHub Release
  `images-v1` ([ADR 0007](0007-rejected-products-and-image-publishing.md)); without them every product is rejected.
- The importer needs a shop that has finished installing. The first install takes 1-5 minutes, depending on the
  machine.
- The issue asks for a fallback to the source shop when the Release is missing, and for a small subset mode for CI
  and E2E tests.

Measured on own machine (Windows, Docker Desktop, shop limited to 4 CPUs) and on a throwaway stack:

| Step | Time |
|---|---|
| Install from `up -d --build` until the shop answers | about 70 s |
| Download of the full archive from the Release | 846 s (0.7 MB/s) |
| Unpacking 4822 files into a Windows folder bind-mounted into a container | 158-186 s |
| The same into a named Docker volume, or into the container's own filesystem | 9-10 s |
| Full import of 2159 products and 4822 images | 1305 s |
| Subset init (53 products, 121 images) right after `up -d`, from start to end | 132 s |
| A second init with nothing to do | 6-9 s |

## Options considered

### What the init command is

- **A Python module in the importer's image, run as a Compose service `init` (chosen):**
  `docker compose -f deploy/compose.yaml --profile init run --rm --build init`. It needs only Docker, works the same
  on Windows, macOS and Linux, reuses the importer's data loading, and is tested with pytest like the rest.
- A `Makefile` (`make init`), as the brief suggests: `make` is not installed on Windows by default.
- A shell script in `deploy/`: runs differently in Git Bash, PowerShell and Linux shells, and would still need
  Python or `curl` and `tar` on the host for the images.

### When the images are downloaded

- After the shop is ready (`depends_on: service_healthy`, as the `importer` service does): simple, but the download
  waits for the install although it does not need the shop.
- **At once, while the shop installs (chosen):** `init` has no `depends_on`; it downloads and unpacks the images,
  then waits for the shop itself with the same test as the Compose healthcheck (`http://shop/` answers below 400).
  If the shop container is not running at all, its name does not resolve and init stops after 30 s with the start
  command, instead of waiting 15 minutes.

### Where the images are stored

- **`scraper-results/images/`, the bind mount the importer already reads (chosen).** It survives `down -v`, so a
  developer who resets the shop never downloads again, the files are visible on disk, and the scraper writes to the
  same place. Costs about 3 minutes of unpacking once per machine on Docker Desktop (Windows and macOS), where every
  file written into a host folder crosses into the VM; on Linux it is as fast as a volume.
- A named Docker volume: unpacks in 10 s everywhere, but `down -v` deletes it with the shop's data, so every reset
  would download 585 MB again, which at the measured speed costs far more than the unpacking saves.
- Unpacking while downloading (streaming): keeps the bind mount and overlaps the two, but the files are written
  before the archive's hash can be checked, and the code is harder to explain.

### How the download is trusted

The archive's sha256 is written in `deploy/importer/importer/init.py` (`FULL`, `SUBSET`). A file with another hash is
refused, and so is an archive that holds anything but files directly under `images/`; tarfile's `data` filter also
refuses links and `../` paths. Each file is written under a temporary name and renamed when complete, so an
interrupted unpack never leaves a half-written image that the next run would take as present. The cost: a rebuilt
archive gets a new hash (file dates are stored inside), so publishing one means changing the code too.

### Fallback when the Release is unavailable

- Ask the user whether to download from the source shop: init would block in CI and in a non-interactive run.
- Download from the source shop automatically: an unasked 1 h 40 min run against the source shop (rule 7).
- **Stop with exit code 2 and print the command (chosen):**
  `docker compose -f deploy/compose.yaml --profile init run --rm --build scraper images`, with the expected time.
  The new image `scraper/Dockerfile` runs the existing scraper (2 requests per second at most, robots.txt, resumable)
  without Python on the host. When `CI` is set, init prints only "fix the Release": CI never touches the source shop.

### Subset mode

`init --subset` imports only categories 85 (Przyprawy, under Żywność) and 99 (Pielęgnacja okolic oczu, under
Kosmetyki) with their subcategories: two branches of the top menu with enough products in stock for the E2E
scenario, 53 products and 121 images. Its images are a separate Release asset, `subset-images.tar.gz` (9.8 MB, made
with `python -m scraper archive --categories 85,99`), so CI does not download 585 MB for them. A subset run deletes
nothing, so the installer's 19 demo products stay next to the subset.

### Import through the API or a database snapshot

Loading a prepared database dump and the shop's image folder would skip the import, but the shop's resized images are
1.1 GB (29 202 files, 5 sizes of every image), more than the source archive, and D2 asks for the API import anyway. It
stays the plan if the final measurement shows the API import cannot meet the limit.

## Decision

A Compose service `init` runs `python -m importer.init` from the importer's image, right after `up -d`. It checks
that the shop container runs, makes sure the image files of this run are in `scraper-results/images/` (downloading,
checking and unpacking the Release archive if any is missing), waits for the shop, then runs the importer with the
same options. `--subset` uses the small archive and categories 85 and 99. Without the archive, init stops and prints
the command for the `scraper` service. CI runs the subset init twice in the `smoke` job (the second run must change
nothing), and the manual workflow `init-timing.yml` times a full clean start on a GitHub runner.

## Consequences

- A clean clone needs three commands: `cp deploy/.env.example deploy/.env`, `up -d --build` and `init`. A second
  init downloads nothing and changes nothing.
- **The 15 minute limit is dependant on the device:** for machine it was tested on it took about 14 minutes of download, overlapping the install,
  plus about 22 minutes of import, so 35-40 minutes in total. The image uploads are most of the import (PrestaShop
  makes 5 sizes of each). What to change is decided after the final timing at the end of Stage 1, on a team machine
  and on a GitHub runner: images resized to 800 px for the upload (about 4.8 times faster per image in a test), or
  the snapshot above.
- Every PR that changes `shop/`, `deploy/` or `scraper-results/` now depends on the Release: the `smoke` job
  downloads the subset archive.
- A new archive needs its hash changed in `init.py`; the scraper README says so where it explains how to build one.
- On Linux, files written by the root containers in `scraper-results/` belong to root. Init gives them back to the
  owner of `scraper-results/` after each run, so the scraper's files are fixed by the next init.
- If the source shop has removed an image since the scrape, the fallback cannot fetch it and init keeps reporting
  it as missing. Not handled yet; the importer alone would only reject that product.
