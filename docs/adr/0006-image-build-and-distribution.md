# 0006. How the shop images are built and distributed

- Status: Accepted
- Date: 2026-11-11
- Authors: Marcel Kiraga

## Context

Stage 2 runs the Stage 1 shop on a Docker Swarm cluster of `linux/amd64` nodes. `docker stack deploy` ignores
`build:` in the compose file, so every node has to download ready-made images from a registry. The stack needs two
images we build ourselves: `shop` (PrestaShop with our theme, config and scripts) and `proxy` (nginx with the
self-signed certificate setup from ADR 0002). MariaDB and Mailpit are official images and need nothing.

Until CI-5, the images existed only on whatever machine ran `docker compose up --build`. One team member uses an
Apple Silicon Mac, where Docker builds `arm64` images by default, which cannot run on the cluster.

The shop with scraped data must never be publicly reachable. The images themselves contain no data: products,
images and customers live in volumes and the database.

Four things had to be decided: where the images are stored, who builds them, how versions are named, and who can
pull them.

## Options considered

### Where the images are stored

**GitHub Container Registry, GHCR (chosen)**

- Pro: in the same place as the code. A workflow pushes with the run's own `GITHUB_TOKEN`, so there is no account,
  password or secret to manage, which course rules would not let us give to AI tools anyway.
- Pro: free for public packages, which can be pulled without an account.
- Con: package names must be lowercase, while the owner is `MarKir13`, so the names are written out by hand.
- Con: new packages start as private; the owner has to make them public once.

**Docker Hub**

- Con: a separate account and an access token stored as a GitHub secret; anonymous pulls are rate-limited.

**No registry: build on every node**

- Con: `docker stack deploy` cannot build, every node would need the repository, and nodes could end up running
  different builds of the same commit.

### Who builds the published images

**Only CI, on GitHub's `amd64` runners (chosen)**

- Pro: the cluster's platform without emulation, the same way for every commit, from reviewed code on `main`.
- Pro: local builds stay native. `compose.yaml` sets no `platform:`, so the Mac keeps building fast `arm64` images
  for local use; they are never pushed.
- Con: nobody can publish a fix from a laptop; it has to go through a PR and `main`.

**`platform: linux/amd64` in `compose.yaml`, so every build is `amd64`**

- Con: on Apple Silicon every local build and run goes through emulation, several times slower, for images that
  never leave the laptop.

### How versions are named

**`sha-<7 characters of the commit>`, `main`, and the git tag `etap*` (chosen)**

- Pro: `sha-` tags never move, so "the image of commit X" is always the same image; `verify` and Stage 2
  deployments can pin one.
- Pro: `main` is the newest version for quick tests; `etap1` is the version handed in.
- Con: a new `sha-` tag on every merge. Old ones pile up in the package until someone deletes them.

**`latest`**

- Con: nobody can tell what it points to. `metadata-action` would add it on tag pushes by default, so it is turned
  off explicitly.

`provenance: false` keeps one plain image per tag. By default `build-push-action` attaches a record of how the image
was built, which GHCR lists as a second platform "unknown/unknown". Nobody in our setup checks that record, while
the extra entry confuses anyone reading the package page. The `sha-` tag and the
`org.opencontainers.image.source` label still say which commit and repository an image comes from.

### Who can pull them

**Public packages (chosen)**

- Pro: cluster nodes pull without credentials, so no registry login has to be set up on the cluster.
- Pro: the repository is public already, so the images reveal nothing that the repository does not.
- Con: anyone can download the images. They contain only our tracked code and the official base images; no data,
  `.env` or keys (checked once by listing their files).

**Private packages**

- Con: every node needs a GitHub token with `read:packages`, which is a cluster credential to create, store and
  rotate.

## Decision

- `.github/workflows/publish.yml` builds `ghcr.io/markir13/u-cioci-masali/shop` from `shop/` and
  `ghcr.io/markir13/u-cioci-masali/proxy` from `deploy/proxy/`, for `linux/amd64`, with `provenance: false`.
- It pushes on every push to `main` and on tags `etap*`. Pull requests that change the images only build them.
- Tags are `sha-<7 characters>`, `main` and the git tag name; no `latest`.
- After a push to `main`, `verify` pulls both `sha-` images without logging in, checks they are `linux/amd64`, starts
  the stack from them and runs the smoke test.
- Both packages are public.
- `compose.yaml` takes the images from `SHOP_IMAGE` and `PROXY_IMAGE`, defaulting to the local
  `ciocia-shop:local` and `ciocia-proxy:local`, and sets no `platform:`.

## Consequences

- The README start for the lecturer is unchanged: without the variables, `up -d --build` builds locally.
- Stage 2 sets `SHOP_IMAGE` and `PROXY_IMAGE` to a `sha-` or `etap1` tag. It still needs its own answer for the
  `shop-data` volume and start-up ordering, which Swarm handles differently.
- If someone makes a package private, `verify` turns red on the next push to `main`.
- Old `sha-` tags have to be deleted by hand from the package settings if the list gets too long.
- An image built on a laptop must never be pushed to these names; only `publish.yml` pushes.
