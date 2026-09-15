import logging
from dataclasses import dataclass, field

import requests
from django.conf import settings
from django.utils.translation import gettext_lazy

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 15
MAX_ERROR_DETAIL = 200


class OffboardingClientError(Exception):
    """An API call to a platform failed. ``str(err)`` is safe to display."""


@dataclass(frozen=True)
class AccountInfo:
    account_id: str
    label: str
    is_active: bool = True
    data: dict = field(default_factory=dict)


def normalize_email(email):
    return (email or '').strip().lower()


class PlatformOffboardingClient:
    """
    Base class for platform clients. Subclasses set the class attributes
    and implement ``find_account`` and ``offboard``.

    Configuration comes from ``settings.OFFBOARDING_PLATFORMS[slug]``,
    merged over ``default_config``, so deployments only need to supply
    the credentials named in ``required_config``.
    """
    slug = None
    name = None
    action_verb = gettext_lazy("Deactivate")
    is_reversible = True
    default_config = {}
    required_config = ()

    @property
    def config(self):
        configured = settings.OFFBOARDING_PLATFORMS.get(self.slug) or {}
        return {**self.default_config, **{k: v for k, v in configured.items() if v is not None}}

    @property
    def is_configured(self):
        config = self.config
        return all(config.get(key) for key in self.required_config)

    def find_account(self, email):
        raise NotImplementedError

    def offboard(self, account):
        raise NotImplementedError

    def _request(self, method, url, expected_statuses=(200, 204), **kwargs):
        kwargs.setdefault('timeout', REQUEST_TIMEOUT)
        try:
            response = requests.request(method, url, **kwargs)
        except requests.RequestException as err:
            logger.warning("%s offboarding request failed: %s %s: %r", self.name, method, url, err)
            raise OffboardingClientError(
                f"{self.name}: could not reach the API ({type(err).__name__})"
            ) from err
        if response.status_code not in expected_statuses:
            detail = response.text.strip().replace('\n', ' ')
            if len(detail) > MAX_ERROR_DETAIL:
                detail = detail[:MAX_ERROR_DETAIL] + '…'
            logger.warning(
                "%s offboarding request returned HTTP %s: %s %s: %s",
                self.name, response.status_code, method, url, detail,
            )
            raise OffboardingClientError(
                f"{self.name} returned HTTP {response.status_code}: {detail}"
            )
        return response
