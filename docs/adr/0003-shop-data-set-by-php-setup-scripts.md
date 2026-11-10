# 0003. Shop content and settings set by PHP setup scripts

- Status: Accepted
- Date: 2026-11-10
- Authors: Piotr Bortnowski

## Context

PrestaShop keeps content and settings in the database: CMS pages, footer link blocks, store
details, enabled modules, carriers, payment settings. The automatic install fills it with English
demo data (pages "Delivery", "Legal Notice", footer blocks "Products" and "Our company", the shop
name "PrestaShop"), even though the shop is installed in Polish.

Anything changed in the back office stays in the local database volume only. It disappears on
`docker compose ... down -v`, it is missing on every teammate's machine, in CI and on the Stage 2
cluster, and the lecturer starts the shop from a clean clone with one command (W3). The course
requires real content for the CMS pages (W3), and the acceptance includes live changes such as
"change the free delivery threshold to 1500 PLN", so the values must be easy to find in the
repository.

The first users are issue #27 (CMS pages, footer links, store details, demo content) and #47
(currency, carriers, payments, e-mail). Categories and the main menu will need the same thing.
Two questions had to be decided: how the data gets into the database, and when that happens.

## Options considered

### How the data gets into the database

**PHP script that uses PrestaShop's own classes (chosen)**

The script loads `config/config.inc.php` and works with `CMS`, `Configuration`, `Meta`, `Module`
and the `LinkBlock` model of `ps_linklist`.

- Pro: the classes write the `_lang` and `_shop` tables, check fields (for example clean HTML in
  CMS content) and clear their caches, the same way the back office does.
- Pro: records can be found by a stable key such as `link_rewrite`, so the script can update in
  place and be run again without creating duplicates.
- Pro: runs inside the shop container with the shop's own database connection, so it needs no
  credentials of its own.
- Con: tied to PrestaShop's PHP classes, which are not a stable public API. We pin 8.2.8, but an
  upgrade means testing the script again.
- Con: a few details need direct SQL anyway. `ps_linklist` orders blocks by
  `link_block_shop.position`, which its model does not set.

**SQL file run with the `mysql` client**

- Pro: short and needs only the database container.
- Con: has to know table prefixes, `_lang` and `_shop` tables and IDs, and skips all validation.
- Con: breaks silently if PrestaShop or a module changes its schema.

**Webservice API**

- Con: needs an API key in the setup, against our rule of keeping credentials out of the repository
  and out of AI tools.
- Con: does not cover module tables such as `ps_linklist`, nor most module settings.

**PrestaShop console (`bin/console`)**

- Pro: official and stable for what it covers.
- Con: it covers configuration values (`prestashop:config`), modules and the theme, but not CMS
  pages, link blocks or carriers. It can still be used from a setup script where it fits, as
  `10-enable-theme.sh` already does.

**Database dump of a shop configured by hand**

- Con: a large file that nobody can review in a PR, tied to IDs, and it would also carry customers,
  orders and the admin password hash.

### When it runs

**Once after the automatic install, with a documented command to run it again (chosen)**

The image runs `/tmp/post-install-scripts/*` in name order right after installing.

- Pro: a clean install gets everything with no extra step.
- Pro: a change made in the back office for a quick test is not undone by the next restart.
- Pro: only the container that installs the shop runs it, so several shop containers on the
  Stage 2 cluster do not race to create the same records.
- Con: an existing install does not pick up a change by itself. It needs a rebuild and one
  `docker compose ... exec` command, or a reinstall.

**On every start (`/tmp/init-scripts/`)**

- Pro: `up -d --build` alone applies a change.
- Con: every restart overwrites back office edits, which is surprising during a demo, and every
  start takes longer.
- Con: on a cluster every shop container would run it at the same time.

## Decision

Setup scripts live in `shop/scripts/setup/` and are copied to `/opt/ciocia/setup/` in the image,
outside the web root:

- `bootstrap.php` loads PrestaShop and holds small helpers;
- `values.php` holds the shop details and the delivery and payment values (free delivery
  threshold, carriers and fees, weight limit, bank details), all fictional;
- one PHP script per area: `shop-content.php` for #27; #47 adds its own next to it;
- page text in `cms/<link_rewrite>.html`, with `{{name}}` placeholders filled from `values.php`, so
  the "Dostawa" and "Formy płatności" pages state the same values that the configuration uses.

Each script has a small wrapper in `shop/scripts/post-install/` (`20-shop-content.sh`) that runs it
as `www-data`; the number sets the order after `10-enable-theme.sh`. Scripts must be idempotent:
find each record by a stable key, update it in place, create it only if missing, and delete only
records they know (such as the installer's demo pages by their `link_rewrite`).

## Consequences

- Content and settings are reviewed in PRs like code. The back office is fine for trying something
  out, but the change belongs in the scripts.
- To apply a change to a running shop: `up -d --build`, then
  `docker compose -f deploy/compose.yaml exec shop sh /tmp/post-install-scripts/20-shop-content.sh`.
  Running the script overwrites the records it owns and nothing else.
- The installer also adds English. The scripts give it the Polish text, so no installer English
  shows up if someone switches language.
- Nothing may rely on fixed CMS page IDs. The script sets settings that point to a page, such as
  `PS_CONDITIONS_CMS_ID` for the terms and conditions, from the IDs it gets.
- The image does not stop when a post-install script fails. The script prints `[setup] FAILED:`
  and the reason to the shop log, so check `logs shop` after a clean install.
- Upgrading PrestaShop or `ps_linklist` means running the scripts again on a clean install and
  checking the storefront.
