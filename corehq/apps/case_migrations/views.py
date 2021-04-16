from django.contrib import messages
from django.http import HttpResponseRedirect
from django.http.response import Http404
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext as _
from django.views.generic import FormView

from casexml.apps.case.xml import V2
from casexml.apps.phone.const import INITIAL_SYNC_CACHE_TIMEOUT
from casexml.apps.phone.restore import (
    CachedResponse,
    RestoreContent,
    RestoreResponse,
)
from casexml.apps.phone.restore_caching import RestorePayloadPathCache
from casexml.apps.phone.xml import (
    get_case_element,
    get_registration_element_for_case,
)

from corehq.apps.domain.auth import formplayer_auth
from corehq.apps.domain.decorators import domain_admin_required
from corehq.apps.domain.views.base import BaseDomainView
from corehq.apps.locations.fixtures import FlatLocationSerializer
from corehq.apps.locations.models import SQLLocation
from corehq.form_processor.exceptions import CaseNotFound
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.toggles import (
    ADD_LIMITED_FIXTURES_TO_CASE_RESTORE,
    WEBAPPS_CASE_MIGRATION,
)
from corehq.util import reverse

from .forms import MigrationForm
from .migration import perform_migration


@method_decorator(domain_admin_required, name='dispatch')
@method_decorator(WEBAPPS_CASE_MIGRATION.required_decorator(), name='dispatch')
class BaseMigrationView(BaseDomainView):
    section_name = "Case Migrations"

    @property
    def section_url(self):
        return reverse(MigrationView.urlname, args=(self.domain,))


class MigrationView(BaseMigrationView, FormView):
    """View to kick off a migration. Requires user to provide migration XML"""
    urlname = 'case_migration'
    template_name = 'case_migrations/migration.html'
    form_class = MigrationForm

    def form_valid(self, form):
        perform_migration(
            self.domain,
            form.cleaned_data['case_type'],
            form.cleaned_data['migration_xml'],
        )
        messages.add_message(self.request, messages.SUCCESS,
                             _('Migration submitted successfully!'))
        return HttpResponseRedirect(self.page_url)


def get_case_hierarchy_for_restore(case):
    from corehq.apps.reports.view_helpers import get_case_hierarchy
    return [
        c for c in get_case_hierarchy(case, {})['case_list']
        if not c.closed
    ]


@formplayer_auth
def migration_restore(request, domain, case_id):
    """Restore endpoint used in bulk case migrations.
    Also used by formplayer, to get case data, when responding to smsforms in HQ.

    Accepts the provided case_id and returns a restore for the user containing:
    * Registration block
    * The passed in case and its full network of cases
    """
    try:
        case = CaseAccessors(domain).get_case(case_id)
        if case.domain != domain or case.is_deleted:
            raise Http404
    except CaseNotFound:
        raise Http404

    return _get_case_restore_response(domain, case)


def _get_case_restore_response(domain, case):
    restore_payload_path = RestorePayloadPathCache(domain=domain, user_id=case.case_id, sync_log_id=None,
                                                   device_id=None)
    payload_file_path = restore_payload_path.get_value()
    cached_response = CachedResponse(payload_file_path)

    if cached_response:
        response = cached_response
    else:
        payload = _generate_payload(domain, case)
        _cache_payload(domain, case.case_id, payload, restore_payload_path)
        response = RestoreResponse(payload)
    return response.get_http_response()


def _generate_payload(domain, case):
    with RestoreContent('Case[{}]'.format(case.case_id)) as content:
        content.append(get_registration_element_for_case(case))
        for child_case in get_case_hierarchy_for_restore(case):
            # Formplayer will be creating these cases for the first time, so
            # include create blocks
            content.append(get_case_element(child_case, ('create', 'update'), V2))
        if ADD_LIMITED_FIXTURES_TO_CASE_RESTORE.enabled(domain):
            _add_limited_fixtures(domain, case.case_id, content)
        payload = content.get_fileobj()
    return payload


def _cache_payload(domain, case_id, payload, restore_payload_path):
    cached_response = CachedResponse.save_for_later(
        payload,
        INITIAL_SYNC_CACHE_TIMEOUT,
        domain,
        case_id,
    )
    restore_payload_path.set_value(cached_response.name, INITIAL_SYNC_CACHE_TIMEOUT)


def _add_limited_fixtures(domain, case_id, content):
    serializer = FlatLocationSerializer()
    content.extend(serializer.get_xml_nodes('locations', domain, case_id, SQLLocation.active_objects))
