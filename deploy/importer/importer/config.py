"""Settings from the environment, passed in by deploy/compose.yaml (service `importer`)."""

import os
from dataclasses import dataclass, field


class ConfigError(Exception):
    """A setting is missing. __main__ logs the message and exits with code 2."""


@dataclass(frozen=True)
class Config:
    api_url: str  # the shop on the Compose network, plain HTTP
    shop_domain: str  # sent as the Host header: the shop's own domain (PS_DOMAIN), or PrestaShop answers 302
    # PS_WEBSERVICE_KEY from deploy/.env. repr=False keeps it out of repr(config), so printing or logging the
    # settings can never show it.
    key: str = field(repr=False)

    @classmethod
    def from_environment(cls) -> "Config":
        key = os.environ.get("PS_WEBSERVICE_KEY", "")
        if not key:
            raise ConfigError("PS_WEBSERVICE_KEY is not set: add it to deploy/.env (see deploy/.env.example)")
        https_port = os.environ.get("HTTPS_PORT", "8443")
        return cls(
            api_url=os.environ.get("SHOP_API_URL", "http://shop/api"),
            shop_domain=os.environ.get("SHOP_DOMAIN", f"localhost:{https_port}"),
            key=key,
        )
