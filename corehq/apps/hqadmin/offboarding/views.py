from dataclasses import dataclass

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.utils.decorators import method_decorator
from django.utils.translation import gettext as _
from django.utils.text import Truncator
from django.utils.translation import gettext_lazy

from corehq.apps.domain.decorators import require_superuser
from corehq.apps.hqadmin.models import PlatformDeactivationLog
from corehq.apps.hqadmin.offboarding.clients import (
    OFFBOARDING_CLIENTS,
    OffboardingClientError,
    PlatformOffboardingClient,
    get_client,
    normalize_email,
)
from corehq.apps.hqadmin.views.users import UserAdministration
from corehq.apps.hqwebapp.decorators import use_bootstrap5
from corehq.apps.users.util import is_dimagi_email
from corehq.util.htmx_action import (
    HqHtmxActionMixin,
    HtmxResponseException,
    hq_hx_action,
)

ROW_TEMPLATE = 'hqadmin/offboarding/partials/platform_row.html'
# RFC 5321 caps a deliverable address at 254 characters; Django's validator
# allows 320, which would overflow PlatformDeactivationLog.target_email.
MAX_EMAIL_LENGTH = 254
MAX_LABEL_LENGTH = PlatformDeactivationLog._meta.get_field('account_label').max_length


@dataclass
class PlatformRow:
    """
    Everything the row partial needs to render one platform.

    ``state`` is one of:

    - ``loading``: placeholder that triggers its own lookup on load
    - ``not_configured``: no credentials on this environment
    - ``error``: the lookup failed; ``message`` says why, row offers Retry
    - ``not_found``: the platform has no account for the email
    - ``inactive``: account exists but is already deactivated
    - ``found``: active account, selectable
    - ``done``: deactivated/removed in this request
    - ``failed``: the offboard call failed; ``message`` says why
    """
    client: PlatformOffboardingClient
    state: str
    label: str = ''
    message: str = ''


def validate_target_email(raw_email):
    """
    Normalise the submitted email and return ``(email, error_message)``.
    ``error_message`` is ``None`` when the email is acceptable; an empty
    submission yields ``('', None)`` so the page can render its blank state.
    """
    email = normalize_email(raw_email)
    if not email:
        return '', None
    try:
        validate_email(email)
    except ValidationError:
        return email, _("Enter a valid email address.")
    if len(email) > MAX_EMAIL_LENGTH:
        return email, _("Enter a valid email address.")
    return email, None


def is_protected_email(email):
    """True for addresses on ``settings.OFFBOARDING_PROTECTED_EMAILS``, which the tool never touches."""
    email = normalize_email(email)
    protected = {normalize_email(address) for address in settings.OFFBOARDING_PROTECTED_EMAILS}
    return bool(email) and email in protected


def _lookup(client, email):
    """Return ``(row, account)``; ``account`` is only set for a selectable row."""
    if not client.is_configured:
        return PlatformRow(client, 'not_configured'), None
    try:
        account = client.find_account(email)
    except OffboardingClientError as err:
        return PlatformRow(client, 'error', message=str(err)), None
    if account is None:
        return PlatformRow(client, 'not_found'), None
    if not account.is_active:
        return PlatformRow(client, 'inactive', label=account.label), None
    return PlatformRow(client, 'found', label=account.label), account


def lookup_row(client, email):
    return _lookup(client, email)[0]


def execute_row(client, email, performed_by):
    """
    Re-run the lookup (so we act on a fresh platform-side id and never
    re-deactivate an already inactive account) and then offboard.

    Every call to ``offboard``, successful or not, is logged. If the
    re-lookup fails or no longer finds an active account, nothing is sent
    to the platform, so the lookup row is returned without a log entry.
    """
    row, account = _lookup(client, email)
    if account is None:
        return row
    try:
        message = client.offboard(account)
    except OffboardingClientError as err:
        _log_attempt(client, email, account, performed_by, succeeded=False, detail=str(err))
        return PlatformRow(client, 'failed', label=account.label, message=str(err))
    _log_attempt(client, email, account, performed_by, succeeded=True, detail=message)
    return PlatformRow(client, 'done', label=account.label, message=message)


def _log_attempt(client, email, account, performed_by, succeeded, detail):
    # Labels are built from platform-supplied names; never let an overlong
    # one fail the write after the account has already been offboarded.
    label = Truncator(account.label).chars(MAX_LABEL_LENGTH)
    PlatformDeactivationLog.objects.create(
        performed_by=performed_by,
        target_email=email,
        platform=client.slug,
        account_label=label,
        succeeded=succeeded,
        detail=detail,
    )


@method_decorator(use_bootstrap5, name='dispatch')
@method_decorator(require_superuser, name='dispatch')
class ExternalPlatformOffboardingView(HqHtmxActionMixin, UserAdministration):
    urlname = 'offboard_external_platforms'
    page_title = gettext_lazy("Offboard staff from external platforms")
    template_name = 'hqadmin/offboarding/external_platforms.html'

    @property
    def page_context(self):
        email, error = validate_target_email(self.request.GET.get('email', ''))
        protected = is_protected_email(email)
        show_results = bool(email) and error is None and not protected
        return {
            'email': email,
            'email_error': error,
            'is_protected_email': protected,
            'is_dimagi_email': is_dimagi_email(email),
            'rows': [PlatformRow(client, 'loading') for client in OFFBOARDING_CLIENTS] if show_results else [],
            'platforms': {
                client.slug: {
                    'name': client.name,
                    'verb': str(client.action_verb),
                    'reversible': client.is_reversible,
                }
                for client in OFFBOARDING_CLIENTS
            },
        }

    @staticmethod
    def _get_email(params):
        email, error = validate_target_email(params.get('email', ''))
        if not email or error:
            raise HtmxResponseException(error or _("An email address is required."), status_code=400)
        if is_protected_email(email):
            raise HtmxResponseException(
                _("'{}' is protected and cannot be offboarded with this tool.").format(email), status_code=403)
        return email

    @staticmethod
    def _get_client(slug):
        client = get_client(slug)
        if client is None:
            raise HtmxResponseException(_("Unknown platform '{}'.").format(slug), status_code=400)
        return client

    @hq_hx_action('get')
    def lookup(self, request, *args, **kwargs):
        email = self._get_email(request.GET)
        client = self._get_client(request.GET.get('platform'))
        return self.render_htmx_partial_response(request, ROW_TEMPLATE, {
            'row': lookup_row(client, email),
            'email': email,
        })

    @hq_hx_action('post')
    def execute(self, request, *args, **kwargs):
        email = self._get_email(request.POST)
        selected = {self._get_client(slug) for slug in request.POST.getlist('platforms')}
        if not selected:
            raise HtmxResponseException(_("Select at least one platform."), status_code=400)
        rows = [
            execute_row(client, email, request.user.username)
            if client in selected else PlatformRow(client, 'loading')
            for client in OFFBOARDING_CLIENTS
        ]
        return HttpResponse(''.join(
            render_to_string(ROW_TEMPLATE, {'row': row, 'email': email}, request=request)
            for row in rows
        ))
