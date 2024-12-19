from django.http import HttpResponseRedirect
from django.utils.translation import gettext_lazy

from corehq.apps.domain.decorators import require_superuser
from corehq.apps.hqwebapp.views import BaseSectionPageView
from corehq.util import reverse


@require_superuser
def default(request):
    from ..reports import UserListReport
    return HttpResponseRedirect(UserListReport.get_url())


def get_breadcrumbs(current_title, current_urlname):
    return {
        'current_page': {
            'url': reverse(current_urlname),
            'page_name': current_title,
        },
        'section': {
            'url': reverse('default_admin_report'),
            'title': 'Admin',
        },
    }


class BaseAdminSectionView(BaseSectionPageView):
    section_name = gettext_lazy("Admin")

    @property
    def section_url(self):
        return reverse('default_admin_report')

    @property
    def page_url(self):
        return reverse(self.urlname)
