# Architecture Decision Records

One file per decision: `NNNN-short-title.md` (e.g. `0001-container-architecture.md`), numbered in order.
An accepted ADR is not edited later. If the decision changes, write a new ADR and mark the old one
as "Superseded by NNNN".

## Index

- [0001. Results schema and validation with pydantic](0001-results-schema-and-validation.md)
- [0002. HTTPS through an nginx proxy with a self-signed certificate](0002-https-proxy-with-self-signed-certificate.md)
- [0003. CI checks and merge policy](0003-ci-checks-and-merge-policy.md)
- [0004. Crawl sources and category assignment](0004-crawl-sources-and-category-assignment.md)
- [0005. Shop content and settings set by PHP setup scripts](0005-shop-data-set-by-php-setup-scripts.md)
- [0006. How the shop images are built and distributed](0006-image-build-and-distribution.md)
- [0007. Products left out on purpose, and publishing the images](0007-rejected-products-and-image-publishing.md)
- [0008. Product import through the Webservice API](0008-product-import-through-the-webservice-api.md)
- [0009. Products with variants made from families of source products](0009-variants-as-combinations-of-source-families.md)
- [0010. One-command data init](0010-one-command-data-init.md)
- [0011. Omnibus price from our own module with a price history in the database](0011-omnibus-price-history-module.md)
- [0012. What a backup contains, and what the settings export is](0012-backup-contents-and-settings-export.md)
## Template

    # NNNN. Title

    - Status: Proposed | Accepted | Superseded by NNNN
    - Date: YYYY-MM-DD
    - Authors:

    ## Context
    What problem or constraint forces a decision?

    ## Options considered
    Each option with its pros and cons.

    ## Decision
    What we chose and why.

    ## Consequences
    What becomes easier or harder, what has to be done next.
