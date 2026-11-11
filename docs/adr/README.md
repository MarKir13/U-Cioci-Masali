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
