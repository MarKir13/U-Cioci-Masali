# 0009. What a backup contains, and what the settings export is

- Status: Accepted
- Date: 2026-11-14
- Authors: Mateusz Radziul

## Context

D4 asks for scripts in `deploy/` that back up the database, the product images and the configuration, and
restore them onto a clean environment in at most 10 minutes. It also asks for a settings export in the
repository that restores the shop configuration and holds no customer data or secrets (issue #74).

The state of a running shop is in two named volumes:

- `db-data`: the MariaDB database. Products, categories, CMS pages, settings, customers, orders, the admin
  account and the installed modules are all rows here.
- `shop-data`, mounted at `/var/www/html`: PrestaShop itself, our theme and modules (copied from the image on
  every start by `sync-code.sh`), the images in `img/`, the cache, and two files written for one install:
  `app/config/parameters.php` (database password, cookie keys) and `.htaccess` (rewrite rules that name the
  shop domain with its port, as in `RewriteCond %{HTTP_HOST} ^localhost:8443$`).

Three things had to be decided: which files go into the archive, what happens to `parameters.php`, and what
counts as the settings export.

## Options considered

### Files in the archive

**The whole `shop-data` volume**

- Pro: one `tar` of one folder, nothing to choose.
- Con: most of it is PrestaShop and our code, which the image already supplies.
- Con: it carries `parameters.php` and `.htaccess` of the old install into the new one (see below).

**The database, `img/` and the banner slides (chosen)**

Only what cannot be rebuilt from the repository and the image. `modules/ps_imageslider/images/` is included
because the slider keeps its pictures there, outside `img/`, and a slide changed in the back office exists
nowhere else.

- Pro: the archive is as small as it can be without losing anything.
- Con: a new kind of file that lives only in the volume has to be added to both scripts by hand.

**The database and the original images only, thumbnails regenerated on restore**

- Pro: a smaller archive.
- Con: PrestaShop would have to resize every image into every thumbnail size during the restore, which has a
  10 minute limit. Copying the thumbnails is faster and cannot fail halfway.

### `app/config/parameters.php`

**Back it up and restore it**

- Pro: the restored shop is an exact copy, cookie keys included, so open sessions keep working.
- Con: the file holds the database password. The new environment's `db` container has the password from its
  own `deploy/.env`, so a restored file with another password stops the shop from connecting.
- Con: a secret ends up in an archive that people copy between machines.

**Leave it out; the new environment keeps its own (chosen)**

- Pro: no secret of the install in the archive, and the shop always matches its own `db` container.
- Pro: logging in does not depend on it. PrestaShop 8 stores customer and employee passwords as bcrypt hashes
  in the database. Tested: after a restore onto a fresh install with new cookie keys, customers created before
  the backup log in.
- Con: cookies from before the restore are invalid, so everyone logs in again.
- Con: a password stored in the old format (`md5` of the cookie key and the password, which `Tools::hash()`
  still produces) would stop working. The registration form and the installer do not use it, so our shop has
  none. Code that creates customers must not use `Tools::hash()`.

`.htaccess` is left out for the same reason: it belongs to one install and names its domain.

### Settings export

**`shop/config/shop-settings.php` and the setup scripts of ADR 0005 (chosen)**

- Pro: already in the repository, reviewed in PRs, with no customer data and no secrets.
- Pro: it restores the configuration by itself on a clean install, and with two commands on a running shop.
- Con: a setting changed only in the back office is not in it. That is already the rule of ADR 0005.

**A dump of chosen `ps_configuration` rows in the repository**

- Con: a second source of the same values, which drifts from `shop-settings.php`.
- Con: carriers, tax rules, CMS pages and module settings are in other tables, so it would not restore the
  configuration alone. `ps_configuration` also holds values that must not be published, so the list of rows
  would have to be kept by hand.

**A database dump without the customer tables**

- Con: a large file that nobody can review, and hard to prove free of customer data (the reason ADR 0005
  rejected it).

## Decision

`deploy/backup.sh` writes one `tar.gz` into `deploy/backups/` with `db.sql` (the whole database, from
`mariadb-dump --single-transaction` run in the `db` container with that container's own credentials), `img/`,
`modules/ps_imageslider/images/` and `manifest.txt` (date, git commit, PrestaShop version, number of products,
shop domain). `parameters.php` and `.htaccess` are not in it.

`deploy/restore.sh` works on a running, installed shop. After a confirmation it replaces the database and the
images, sets the shop domain in the database to `PS_DOMAIN` of the running shop container, and restarts `shop`
and `proxy`. The environment keeps its own `parameters.php` and `.htaccess`.

The settings export is `shop/config/shop-settings.php` with the setup scripts. No second export is added.

## Consequences

- The archive holds customer data and password hashes, and after #69 the Webservice key. It stays on the
  machine: `backups/` and `*.tar.gz` are gitignored, and an archive must never be attached to a release.
- A backup can move between environments with different ports or hosts, because the restore sets the domain.
  The same holds for the Stage 2 cluster, but the scripts call `docker compose exec`, which has to be replaced
  there.
- Everything in the database comes from the backup, including values that the install took from the
  environment. After a restore the back office login is the one of the backed-up shop, not `ADMIN_MAIL` and
  `ADMIN_PASSWORD` of the new environment. Once #69 is merged, the restore has to run `40-webservice.sh` so
  that the Webservice key matches the new environment again.
- The restore expects the same code as the backup. It prints a note when the commit in the manifest differs
  from the current checkout, and does not stop.
- The restore drops and recreates the database before loading the dump, so no table of the current install
  is left next to the backup's.
- Measured on the demo data (19 products): backup 11 s, restore 31 s. The time with the full data has to be
  measured after #71 and recorded in the PR; if packing the images is too slow, lower the gzip level.
