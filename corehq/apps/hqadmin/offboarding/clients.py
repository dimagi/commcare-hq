import logging
from dataclasses import dataclass, field

import requests
from django.conf import settings
from django.utils.translation import gettext as _
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


class DatadogOffboardingClient(PlatformOffboardingClient):
    """
    Datadog Users API v2. Disabling is a ``DELETE`` on the user, which
    Datadog documents as "disable a user" and which an admin can undo.
    """
    slug = 'datadog'
    name = 'Datadog'
    default_config = {'site': 'datadoghq.com'}
    required_config = ('api_key', 'app_key')

    @property
    def _users_url(self):
        return f"https://api.{self.config['site']}/api/v2/users"

    @property
    def _headers(self):
        config = self.config
        return {
            'DD-API-KEY': config['api_key'],
            'DD-APPLICATION-KEY': config['app_key'],
            'Accept': 'application/json',
        }

    def find_account(self, email):
        email = normalize_email(email)
        response = self._request(
            'GET', self._users_url, headers=self._headers,
            params={'filter': email, 'page[size]': 100},
        )
        for user in response.json().get('data', []):
            attrs = user.get('attributes', {})
            if normalize_email(attrs.get('email')) == email:
                name = attrs.get('name') or attrs.get('handle') or email
                return AccountInfo(
                    account_id=user['id'],
                    label=f"{name} <{attrs.get('email')}>",
                    is_active=not attrs.get('disabled', False),
                )
        return None

    def offboard(self, account):
        self._request(
            'DELETE', f"{self._users_url}/{account.account_id}",
            headers=self._headers, expected_statuses=(204,),
        )
        return _("Disabled Datadog user {label}").format(label=account.label)


class SentryOffboardingClient(PlatformOffboardingClient):
    """
    Sentry Organization Members API. Sentry has no "disable member", so
    offboarding removes the member from the organization.
    """
    slug = 'sentry'
    name = 'Sentry'
    action_verb = gettext_lazy("Remove")
    is_reversible = False
    required_config = ('auth_token', 'org_slug')

    @property
    def default_config(self):
        return {'api_url': 'https://sentry.io/api/0/', 'org_slug': settings.SENTRY_ORGANIZATION_SLUG}

    @property
    def _members_url(self):
        config = self.config
        return f"{config['api_url'].rstrip('/')}/organizations/{config['org_slug']}/members/"

    @property
    def _headers(self):
        return {'Authorization': f"Bearer {self.config['auth_token']}"}

    def find_account(self, email):
        email = normalize_email(email)
        response = self._request(
            'GET', self._members_url, headers=self._headers,
            params={'query': f"email:{email}"},
        )
        for member in response.json():
            user = member.get('user') or {}
            emails = {normalize_email(member.get('email')), normalize_email(user.get('email'))}
            if email in emails:
                name = member.get('name') or user.get('name') or email
                label = f"{name} <{member.get('email') or email}>"
                if member.get('pending'):
                    label += " (pending invite)"
                return AccountInfo(account_id=str(member['id']), label=label)
        return None

    def offboard(self, account):
        self._request(
            'DELETE', f"{self._members_url}{account.account_id}/",
            headers=self._headers, expected_statuses=(204,),
        )
        return _("Removed {label} from the Sentry organization").format(label=account.label)
