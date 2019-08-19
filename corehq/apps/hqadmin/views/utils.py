from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals

from django.http import (
    HttpResponseRedirect,
)
from django.utils.translation import ugettext_lazy

from corehq.apps.domain.decorators import (
    require_superuser)
from corehq.apps.hqwebapp.views import BaseSectionPageView
from corehq.util import reverse


@require_superuser
def default(request):
    return HttpResponseRedirect(reverse('admin_report_dispatcher', args=('user_list',)))


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
