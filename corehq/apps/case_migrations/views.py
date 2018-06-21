from __future__ import absolute_import
from __future__ import unicode_literals

from django.contrib import messages
from django.http import HttpResponseRedirect
from django.http.response import Http404
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext as _
from django.views.generic import FormView

from casexml.apps.case.xml import V2
from casexml.apps.phone.restore import RestoreContent, RestoreResponse
from casexml.apps.phone.xml import get_case_element, get_registration_element_for_case
from corehq.apps.domain.decorators import domain_admin_required, mobile_auth_or_formplayer
from corehq.apps.domain.views import BaseDomainView
from corehq.apps.locations.permissions import user_can_access_case, location_restricted_exception, location_safe
from corehq.form_processor.exceptions import CaseNotFound
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.toggles import WEBAPPS_CASE_MIGRATION
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


@location_safe
@mobile_auth_or_formplayer(require_user=False)
def migration_restore(request, domain, case_id):
    """Restore endpoint used in bulk case migrations

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

    user = getattr(request, 'couch_user', None)
    # if there is no user then the request is coming from formplayer so we trust it
    if user and not (request.can_access_all_locations or user_can_access_case(domain, user, case)):
        raise location_restricted_exception(request)

    with RestoreContent('Case[{}]'.format(case_id)) as content:
        content.append(get_registration_element_for_case(case))
        for case in get_case_hierarchy_for_restore(case):
            # Formplayer will be creating these cases for the first time, so
            # include create blocks
            content.append(get_case_element(case, ('create', 'update'), V2))
        payload = content.get_fileobj()

    return RestoreResponse(payload).get_http_response()
