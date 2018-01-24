from __future__ import absolute_import
from __future__ import unicode_literals

from django.contrib import messages
from django.http import HttpResponseRedirect
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext as _
from django.views.generic import FormView

from casexml.apps.case.xml import V2
from casexml.apps.phone.restore import RestoreContent, RestoreResponse
from casexml.apps.phone.xml import get_registration_element, get_case_element
from corehq.apps.domain.decorators import domain_admin_required, mobile_auth
from corehq.apps.domain.views import BaseDomainView
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


def get_case_and_descendants(domain, case_id):
    from casexml.apps.case.templatetags.case_tags import get_case_hierarchy
    case = CaseAccessors(domain).get_case(case_id)
    return [case for case in get_case_hierarchy(case, {})['case_list']
            if not case.closed]


@mobile_auth
@WEBAPPS_CASE_MIGRATION.required_decorator()
def migration_restore(request, domain, case_id):
    """Restore endpoint used in bulk case migrations

    Accepts the provided case_id and returns a restore for the user containing:
    * Registration block
    * The passed in case and its full network of cases
    """
    restore_user = request.couch_user

    with RestoreContent(restore_user.username) as content:
        content.append(get_registration_element(restore_user))
        for case in get_case_and_descendants(domain, case_id):
            # Formplayer will be creating these cases for the first time, so
            # include create blocks
            content.append(get_case_element(case, ('create', 'update'), V2))
        payload = content.get_fileobj()

    return RestoreResponse(payload).get_http_response()
