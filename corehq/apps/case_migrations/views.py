from __future__ import absolute_import
from __future__ import unicode_literals

from django.contrib import messages
from django.http import HttpResponseRedirect
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext as _
from django.views.generic import FormView

from casexml.apps.case.xml import V2
from casexml.apps.phone.data_providers.case.clean_owners import CleanOwnerSyncPayload
from casexml.apps.phone.restore import RestoreContent, RestoreResponse, RestoreState, RestoreParams
from casexml.apps.phone.xml import get_registration_element
from corehq.apps.domain.decorators import domain_admin_required
from corehq.apps.domain.models import Domain
from corehq.apps.domain.views import BaseDomainView
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.toggles import WEBAPPS_CASE_MIGRATION
from corehq.util.timer import TimingContext
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


def get_related_case_ids(domain, case_id):
    from casexml.apps.case.templatetags.case_tags import get_case_hierarchy
    case = CaseAccessors(domain).get_case(case_id)
    child_cases = {c.case_id for c in get_case_hierarchy(case, {})['case_list']}
    return child_cases


@domain_admin_required
@WEBAPPS_CASE_MIGRATION.required_decorator()
def migration_restore(request, domain, case_id):
    """Restore endpoint used in bulk case migrations

    Accepts the provided case_id and returns a restore for the user containing:
    * Registration block
    * The passed in case and its full network of cases
    """
    domain_obj = Domain.get_by_name(domain)
    restore_user = request.couch_user
    restore_params = RestoreParams(device_id="case_migration", version=V2)
    restore_state = RestoreState(domain_obj, restore_user.to_ota_restore_user(domain), restore_params)
    restore_state.start_sync()
    timing_context = TimingContext('migration-restore-{}-{}'.format(domain, restore_user.username))
    case_ids = get_related_case_ids(domain, case_id)
    with RestoreContent(restore_user.username) as content:
        content.append(get_registration_element(restore_user))

        sync_payload = CleanOwnerSyncPayload(timing_context, case_ids, restore_state)
        sync_payload.extend_response(content)

        payload = content.get_fileobj()

    restore_state.finish_sync()
    return RestoreResponse(payload).get_http_response()
