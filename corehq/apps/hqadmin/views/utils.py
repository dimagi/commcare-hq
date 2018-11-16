from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals


from django.http import (
    HttpResponseRedirect,
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseNotFound,
    JsonResponse,
    StreamingHttpResponse,
)
from django.utils.translation import ugettext_lazy

from corehq.apps.domain.decorators import (
    require_superuser, require_superuser_or_contractor,
    login_or_basic, domain_admin_required,
    check_lockout)
from corehq.apps.hqwebapp.views import BaseSectionPageView
from corehq.apps.hqwebapp.decorators import use_datatables, use_jquery_ui, \
    use_nvd3_v3
from corehq.form_processor.serializers import XFormInstanceSQLRawDocSerializer, \
    CommCareCaseSQLRawDocSerializer
from corehq.util import reverse
from corehq.util.supervisord.api import (
    PillowtopSupervisorApi,
    SupervisorException,
    all_pillows_supervisor_status,
    pillow_supervisor_status
)
from corehq.apps.hqadmin.forms import (
    AuthenticateAsForm, EmailForm, SuperuserManagementForm,
    ReprocessMessagingCaseUpdatesForm,
    DisableTwoFactorForm, DisableUserForm)


@require_superuser
def default(request):
    return HttpResponseRedirect(reverse('admin_report_dispatcher', args=('domains',)))


def get_hqadmin_base_context(request):
    return {
        "domain": None,
    }


class BaseAdminSectionView(BaseSectionPageView):
    section_name = ugettext_lazy("Admin")

    @property
    def section_url(self):
        return reverse('default_admin_report')

    @property
    def page_url(self):
        return reverse(self.urlname)
